"""Приватные загрузки и копирование выбранного участником файла в задачу."""

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from src.exceptions.access import AccessServiceError
from src.exceptions.agent_files import (
    AgentFileConflictError,
    AgentFileNotFoundError,
    AgentFilesServiceError,
    AgentFileValidationError,
)
from src.exceptions.base import RepositoryError
from src.exceptions.storage import TaskAttachmentStorageError
from src.exceptions.task_attachments import TaskAttachmentsServiceError
from src.schemas.agent_files import AgentFileSchema
from src.services.agent_tool_scope import AgentProjectToolScopeFactory
from src.services.task_attachments import TaskAttachmentsService


class AgentFilesService:
    """Сохраняет загрузку в личном диалоге с общей валидацией вложений."""

    max_file_size = TaskAttachmentsService.MAX_FILE_SIZE

    def __init__(self, *, scope: AgentProjectToolScopeFactory) -> None:
        self.scope = scope

    async def upload(
        self,
        *,
        project_id: int,
        user_id: int,
        conversation_id: int,
        file_name: str,
        content_type: str | None,
        content: bytes,
    ) -> AgentFileSchema:
        """Проверяет диалог, сохраняет файл и компенсирует запись при откате."""
        async with self._scope() as db:
            await self._require(db, project_id, user_id, conversation_id)
            if await db.uploads.count(conversation_id) >= 20:
                raise AgentFileConflictError("Лимит загрузок диалога достигнут.")
            name, extension, mime = db.attachments.validate_file(
                file_name=file_name, content_type=content_type, content=content
            )
            key = await db.upload_storage.save(conversation_id, extension, content)
            row = await db.uploads.save(
                dict(
                    id=uuid4(),
                    conversation_id=conversation_id,
                    original_name=name,
                    content_type=mime,
                    size=len(content),
                    storage_key=key,
                )
            )
            response = AgentFileSchema.model_validate(row)
            await db.unit_of_work.commit()
            return response

    async def delete_draft(
        self, *, project_id: int, user_id: int, conversation_id: int, file_id: UUID
    ) -> None:
        """Удаляет неотправленный файл, сериализуясь с отправкой вопроса."""
        async with self._scope() as db:
            await self._require(db, project_id, user_id, conversation_id)
            row = await db.uploads.get(file_id)
            if row is None or row.conversation_id != conversation_id:
                raise AgentFileNotFoundError("Загрузка недоступна.")
            if row.message_id is not None:
                raise AgentFileConflictError("Файл уже отправлен в сообщении.")
            await db.upload_storage.delete(row.storage_key)
            await db.uploads.delete(row.id)
            await db.unit_of_work.commit()

    @staticmethod
    async def _require(db, project_id, user_id, conversation_id) -> None:
        await db.access.ensure_project_access(project_id=project_id, user_id=user_id)
        if (
            await db.conversations.get_owned(conversation_id, project_id, user_id, lock=True)
            is None
        ):
            raise AgentFileNotFoundError("Диалог недоступен.")

    @asynccontextmanager
    async def _scope(self):
        try:
            async with self.scope() as db:
                yield db
        except AccessServiceError as error:
            raise AgentFileNotFoundError(str(error)) from error
        except TaskAttachmentsServiceError as error:
            raise AgentFileValidationError(str(error)) from error
        except (RepositoryError, TaskAttachmentStorageError) as error:
            raise AgentFilesServiceError(str(error)) from error


async def uploaded_content(
    db, *, file_id: UUID, project_id: int, user_id: int
) -> tuple[AgentFileSchema, bytes]:
    """Возвращает байты только отправленного файла собственного диалога проекта."""
    row = await db.uploads.get(file_id)
    if row is None or row.message_id is None:
        raise AgentFileNotFoundError("Файл ещё не отправлен участником.")
    if await db.conversations.get_owned(row.conversation_id, project_id, user_id) is None:
        raise AgentFileNotFoundError("Файл принадлежит другому участнику или проекту.")
    path = db.upload_storage.resolve(row.storage_key)
    try:
        # Ограничиваем и повторное чтение с диска, если файл был изменён извне.
        def read() -> bytes:
            with path.open("rb") as stream:
                return stream.read(TaskAttachmentsService.MAX_FILE_SIZE + 1)

        content = await asyncio.to_thread(read)
    except OSError as error:
        raise AgentFilesServiceError("Не удалось прочитать загрузку.") from error
    return AgentFileSchema.model_validate(row), content
