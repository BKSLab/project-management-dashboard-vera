"""Компенсация файлов и отложенное удаление вокруг транзакции инструмента."""

import logging
from pathlib import Path

from src.exceptions.storage import TaskAttachmentStorageError
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)


class AgentToolFileStorage(TaskAttachmentStorage):
    """Удаляет существующие файлы только после общего commit действия."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.created: list[str] = []
        self.deleted: list[str] = []
        self.deleted_tasks: list[int] = []

    async def save(self, task_id: int, extension: str, content: bytes) -> str:
        """Записывает новый файл с компенсацией при откате БД."""
        key = await super().save(task_id, extension, content)
        self.created.append(key)
        return key

    async def delete(self, storage_key: str) -> None:
        """Откладывает физическое удаление до commit внешней транзакции."""
        self.deleted.append(storage_key)

    async def delete_task_directory(self, task_id: int) -> None:
        """Откладывает очистку каталога удалённой задачи."""
        self.deleted_tasks.append(task_id)

    async def finish(self, *, committed: bool) -> None:
        """Удаляет запланированные файлы или компенсирует новые после отката."""
        for key in self.deleted if committed else self.created:
            try:
                await super().delete(key)
            except TaskAttachmentStorageError:
                logger.warning("⚠️ Файл действия требует очистки: %s.", key, exc_info=True)
        if committed:
            for task_id in self.deleted_tasks:
                try:
                    await super().delete_task_directory(task_id)
                except TaskAttachmentStorageError:
                    logger.warning(
                        "⚠️ Каталог удалённой задачи требует очистки: %s.", task_id, exc_info=True
                    )
