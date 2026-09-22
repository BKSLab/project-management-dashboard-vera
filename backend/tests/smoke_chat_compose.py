"""Локальная проверка чата через Nginx; временные пользователи/проект удаляются.

Запуск из корня репозитория (PowerShell):
Get-Content backend/tests/smoke_chat_compose.py -Raw | docker compose exec -T backend python -
"""

import asyncio
import json
from collections import deque
from uuid import uuid4

import httpx
from sqlalchemy import delete, select
from wsproto import ConnectionType, WSConnection
from wsproto.events import AcceptConnection, CloseConnection, Ping, Request, TextMessage

from src.core.settings import get_settings
from src.db.models import ChatAttachment, Project, ProjectChat, User
from src.db.session import async_session_factory, engine
from src.storage.chat_attachments import ChatAttachmentStorage
from src.utils.tokens import create_access_token


class Socket:
    """Настоящий TCP/WebSocket-клиент использует уже установленный wsproto."""

    async def connect(self, path, cookie):
        self.reader, self.writer = await asyncio.open_connection("nginx", 80)
        self.protocol = WSConnection(ConnectionType.CLIENT)
        self.frames = deque()
        self.text = ""
        self.writer.write(
            self.protocol.send(
                Request(
                    host="127.0.0.1:5173",
                    target=path,
                    extra_headers=[
                        (b"origin", b"http://127.0.0.1:5173"),
                        (b"cookie", cookie.encode()),
                    ],
                )
            )
        )
        await self.writer.drain()
        return self

    async def receive(self, kind):
        async with asyncio.timeout(15):
            while True:
                if not self.frames:
                    chunk = await self.reader.read(65536)
                    if not chunk:
                        raise RuntimeError("WebSocket неожиданно закрыт")
                    self.protocol.receive_data(chunk)
                    self.frames.extend(self.protocol.events())
                frame = self.frames.popleft()
                if isinstance(frame, AcceptConnection):
                    continue
                if isinstance(frame, Ping):
                    self.writer.write(self.protocol.send(frame.response()))
                    await self.writer.drain()
                if isinstance(frame, CloseConnection):
                    if kind == "close":
                        return {"code": frame.code}
                    raise RuntimeError(f"WebSocket закрыт с кодом {frame.code}")
                if isinstance(frame, TextMessage):
                    self.text += frame.data
                    if frame.message_finished:
                        data, self.text = json.loads(self.text), ""
                        if data.get("type") == kind:
                            return data

    async def send(self, data):
        self.writer.write(self.protocol.send(TextMessage(data=json.dumps(data))))
        await self.writer.drain()

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()


async def main():
    settings = get_settings()
    suffix = uuid4().hex[:7]
    key = f"SMK{suffix.upper()}"
    identities, sockets, storage_keys = [], [], []
    try:
        async with async_session_factory() as db:
            people = [
                User(
                    username=f"chat_smoke_{suffix}_{index}",
                    password_hash="!",
                    first_name="Smoke",
                    last_name=str(index),
                    is_active=True,
                )
                for index in (1, 2)
            ]
            db.add_all(people)
            await db.flush()
            identities = [person.id for person in people]
            usernames = [person.username for person in people]
            await db.commit()
        cookies = [
            f"{settings.auth.session_cookie_name}={create_access_token(user_id)}"
            for user_id in identities
        ]
        async with httpx.AsyncClient(base_url="http://nginx", timeout=20) as http:
            owner, member = {"Cookie": cookies[0]}, {"Cookie": cookies[1]}
            created = await http.post(
                "/api/v1/projects",
                headers=owner,
                json={
                    "key": key,
                    "name": "Временная проверка общего чата",
                    "member_usernames": [usernames[1]],
                    "color": "#7299cc",
                },
            )
            assert created.status_code == 201, f"Создание проекта: {created.status_code}"
            project_id = created.json()["id"]
            path = f"/api/v1/projects/{project_id}/chat"
            info = await http.get(path, headers=member)
            assert info.status_code == 200 and len(info.json()["members"]) == 2
            for cookie in cookies:
                socket = await Socket().connect(f"{path}/ws", cookie)
                sockets.append(socket)
                assert (await socket.receive("ready"))["data"]["can_write"]
            body = {
                "content": "Проверка отправки через Nginx и Redis",
                "client_message_id": str(uuid4()),
            }
            await sockets[0].send(
                {"type": "message.send", "request_id": str(uuid4()), "data": body}
            )
            ack = await sockets[0].receive("ack")
            delivered = await sockets[1].receive("message.created")
            assert ack["data"]["message"]["id"] == delivered["data"]["message"]["id"]
            retry = await http.post(f"{path}/messages", headers=owner, json=body)
            assert retry.status_code == 201 and retry.json()["id"] == ack["data"]["message"]["id"]
            assert len((await http.get(f"{path}/messages", headers=member)).json()["messages"]) == 1
            uploaded = await http.post(
                f"{path}/attachments",
                headers=owner,
                files={"file": ("smoke.txt", b"chat smoke", "text/plain")},
            )
            assert uploaded.status_code == 201
            file_id = uploaded.json()["id"]
            sent = await http.post(
                f"{path}/messages",
                headers=owner,
                json={"client_message_id": str(uuid4()), "attachment_ids": [file_id]},
            )
            assert sent.status_code == 201
            downloaded = await http.get(f"{path}/attachments/{file_id}/content", headers=member)
            assert downloaded.status_code == 200 and downloaded.content == b"chat smoke"
            async with async_session_factory() as db:
                storage_keys.extend(
                    (
                        await db.execute(
                            select(ChatAttachment.storage_key).where(ChatAttachment.id == file_id)
                        )
                    ).scalars()
                )
            # Удаление участника штатным API должно закрыть уже открытый сокет.
            removed = await http.delete(
                f"/api/v1/projects/{project_id}/members/{identities[1]}", headers=owner
            )
            assert removed.status_code == 204, f"Удаление участника: {removed.status_code}"
            assert (await sockets[1].receive("close"))["code"] == 4403
            assert (await http.get(path, headers=member)).status_code == 404
            deleted = await http.delete(f"/api/v1/projects/{project_id}", headers=owner)
            assert deleted.status_code == 204, f"Удаление проекта: {deleted.status_code}"
            assert (await http.get(path, headers=owner)).status_code == 404
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "checks": [
                            "project lifecycle",
                            "nginx websocket upgrade",
                            "two members",
                            "redis delivery",
                            "HTTP/WS idempotency",
                            "private file",
                            "live membership revocation",
                        ],
                    }
                )
            )
    finally:
        await asyncio.gather(*(socket.close() for socket in sockets), return_exceptions=True)
        if identities:
            async with async_session_factory() as db:
                projects = select(Project.id).where(
                    Project.owner_id == identities[0], Project.key == key
                )
                chats = select(ProjectChat.id).where(ProjectChat.project_id.in_(projects))
                storage_keys.extend(
                    (
                        await db.execute(
                            select(ChatAttachment.storage_key).where(
                                ChatAttachment.chat_id.in_(chats)
                            )
                        )
                    ).scalars()
                )
                await db.execute(
                    delete(Project).where(Project.owner_id == identities[0], Project.key == key)
                )
                await db.execute(delete(User).where(User.id.in_(identities)))
                await db.commit()
            storage = ChatAttachmentStorage(settings.app.uploads_path / "chat")
            for storage_key in set(storage_keys):
                await storage.delete(storage_key)
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
