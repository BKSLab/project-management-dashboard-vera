from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from pathlib import Path, PurePosixPath

from src.exceptions.task_attachments import TaskAttachmentStorageError


class TaskAttachmentStorage:
    """Безопасно хранит бинарные файлы задач в локальном каталоге."""

    def __init__(self, root: Path) -> None:
        self.root = root

    async def save(self, task_id: int, extension: str, content: bytes) -> str:
        """Атомарно сохраняет файл и возвращает относительный storage key.

        Args:
            task_id: Идентификатор задачи-владельца.
            extension: Проверенное расширение вместе с точкой.
            content: Бинарное содержимое файла.

        Returns:
            Относительный POSIX-путь внутри корня хранилища.

        Raises:
            TaskAttachmentStorageError: Если сохранить файл не удалось.
        """
        try:
            return await asyncio.to_thread(
                self._save_sync,
                task_id,
                extension,
                content,
            )
        except OSError as error:
            raise TaskAttachmentStorageError(str(error)) from error

    async def delete(self, storage_key: str) -> None:
        """Удаляет сохранённый файл, если он существует.

        Args:
            storage_key: Относительный ключ внутри хранилища.

        Raises:
            TaskAttachmentStorageError: Если удалить файл не удалось.
        """
        try:
            path = self.resolve(storage_key)
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except (OSError, ValueError) as error:
            raise TaskAttachmentStorageError(str(error)) from error

    async def delete_task_directory(self, task_id: int) -> None:
        """Удаляет каталог всех файлов задачи.

        Args:
            task_id: Идентификатор удалённой задачи.

        Raises:
            TaskAttachmentStorageError: Если очистить каталог не удалось.
        """
        try:
            root = self.root.resolve()
            target = (root / "tasks" / str(task_id)).resolve()
            if root not in target.parents:
                raise ValueError("Каталог задачи находится вне корня uploads.")
            await asyncio.to_thread(shutil.rmtree, target, True)
        except (OSError, ValueError) as error:
            raise TaskAttachmentStorageError(str(error)) from error

    def resolve(self, storage_key: str) -> Path:
        """Возвращает проверенный абсолютный путь по storage key.

        Args:
            storage_key: Относительный POSIX-путь файла.

        Returns:
            Абсолютный путь, находящийся внутри корня хранилища.

        Raises:
            TaskAttachmentStorageError: Если ключ небезопасен или файл отсутствует.
        """
        try:
            relative = PurePosixPath(storage_key)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Некорректный storage key.")
            root = self.root.resolve()
            target = (root / Path(*relative.parts)).resolve()
            if root not in target.parents or not target.is_file():
                raise ValueError("Файл отсутствует в локальном хранилище.")
            return target
        except (OSError, ValueError) as error:
            raise TaskAttachmentStorageError(str(error)) from error

    def _save_sync(self, task_id: int, extension: str, content: bytes) -> str:
        """Выполняет блокирующую атомарную запись вне event loop."""
        destination_dir = self.root / "tasks" / str(task_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{uuid.uuid4().hex}{extension}"
        destination = destination_dir / file_name
        temporary = destination_dir / f".{file_name}.tmp"
        try:
            temporary.write_bytes(content)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return PurePosixPath("tasks", str(task_id), file_name).as_posix()
