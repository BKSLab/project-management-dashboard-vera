"""Пакетная сборка актуальных read models без SQL в сервисном слое."""

from collections import defaultdict
from urllib.parse import quote

from src.schemas.project_chats import (
    ChatAttachmentView,
    ChatEntityView,
    ChatMessageView,
    ChatReplyView,
    ChatUser,
)
from src.services.chat_scope import ChatScope


def public_user(row) -> ChatUser:
    """Оставляет в общей переписке только публичное имя участника."""
    return ChatUser(
        id=row["id"],
        username=row["username"],
        display_name=" ".join(filter(None, [row["last_name"], row["first_name"]]))
        or row["username"],
    )


def entity_view(row) -> ChatEntityView:
    """Строит локальную ссылку и подпись из текущих полей объекта."""
    kind, key, entity_id, extra = (
        row["entity_type"],
        quote(row["project_key"], safe=""),
        row["entity_id"],
        row["extra"],
    )
    base = f"/projects/{key}"
    href = {
        "TASK": f"{base}/tasks?task={entity_id}",
        "DOCUMENT": f"{base}/docs/{quote(extra or '', safe='')}",
        "RISK": f"{base}/risks?risk={entity_id}",
        "MILESTONE": f"{base}/calendar?anchor={extra or ''}&milestone={entity_id}",
        "WBS_NODE": f"{base}/structure?wbs={entity_id}",
    }[kind]
    return ChatEntityView(
        entity_type=kind,
        entity_id=entity_id,
        title=row["title"],
        status=row["status"],
        subtitle=f"{row['project_key']}-{extra}"
        if kind == "TASK"
        else extra
        if kind == "MILESTONE"
        else None,
        href=href,
    )


class ChatPresenter:
    """Количество запросов зависит от страницы, а не от числа сообщений."""

    async def messages(self, db: ChatScope, rows: list) -> list[ChatMessageView]:
        """Гидратирует ссылки, авторов, ответы, вложения и реакции пакетом."""
        if not rows:
            return []
        ids = [row.id for row in rows]
        replies = await db.messages.get_many(
            rows[0].chat_id,
            list({row.reply_to_message_id for row in rows if row.reply_to_message_id}),
        )
        refs = await db.entities.get_many(ids)
        mentions = await db.mentions.get_many(ids)
        files = await db.attachments.get_many(ids)
        reactions = await db.reactions.get_many(ids)
        user_ids = {row.author_user_id for row in [*rows, *replies] if row.author_user_id} | {
            row.user_id for row in mentions
        }
        users = {
            row["id"]: public_user(row) for row in await db.participants.get_users(list(user_ids))
        }
        ref_keys = list({(row.entity_type, row.entity_id) for row in refs})
        entity_rows = (
            await db.entity_lookup.find(
                rows[0].project_id, refs=ref_keys, limit=max(len(ref_keys), 1)
            )
            if ref_keys
            else []
        )
        entities = {(row["entity_type"], row["entity_id"]): entity_view(row) for row in entity_rows}
        refs_by_message, mentions_by_message, files_by_message, reactions_by_message = (
            defaultdict(list),
            defaultdict(list),
            defaultdict(list),
            defaultdict(lambda: defaultdict(list)),
        )
        for row in refs:
            refs_by_message[row.message_id].append(
                entities.get((row.entity_type, row.entity_id))
                or ChatEntityView(
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    title="Объект больше недоступен",
                    available=False,
                )
            )
        for row in mentions:
            if row.user_id in users:
                mentions_by_message[row.message_id].append(users[row.user_id])
        for row in files:
            files_by_message[row.message_id].append(ChatAttachmentView.model_validate(row))
        for row in reactions:
            reactions_by_message[row.message_id][row.reaction].append(row.user_id)
        reply_map = {row.id: row for row in replies}
        result = []
        for row in rows:
            deleted = row.deleted_at is not None
            reply = reply_map.get(row.reply_to_message_id)
            result.append(
                ChatMessageView(
                    id=row.id,
                    chat_id=row.chat_id,
                    project_id=row.project_id,
                    seq=row.seq,
                    author=users.get(row.author_user_id),
                    client_message_id=row.client_message_id,
                    content="" if deleted else row.content,
                    revision=row.revision,
                    created_at=row.created_at,
                    edited_at=row.edited_at,
                    deleted_at=row.deleted_at,
                    reply=ChatReplyView(
                        id=reply.id,
                        seq=reply.seq,
                        author=users.get(reply.author_user_id),
                        content="Сообщение удалено" if reply.deleted_at else reply.content[:240],
                        deleted=reply.deleted_at is not None,
                    )
                    if reply
                    else None,
                    mentions=[] if deleted else mentions_by_message[row.id],
                    entities=[] if deleted else refs_by_message[row.id],
                    attachments=[] if deleted else files_by_message[row.id],
                    reactions=[]
                    if deleted
                    else [
                        {"reaction": reaction, "user_ids": user_ids}
                        for reaction, user_ids in reactions_by_message[row.id].items()
                    ],
                )
            )
        return result
