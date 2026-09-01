from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path, PurePosixPath

from src.exceptions.users import AvatarStorageError


class AvatarStorage:
    """Хранит фотографии профилей в локальном каталоге.

    У пользователя одна фотография: новая заменяет прежнюю, поэтому имя файла
    делается уникальным, а старый файл удаляется вызывающим сервисом.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    async def save(self, user_id: int, extension: str, content: bytes) -> str:
        """Сохраняет файл и возвращает относительный ключ.

        Args:
            user_id: Идентификатор владельца.
            extension: Проверенное расширение вместе с точкой.
            content: Бинарное содержимое файла.

        Returns:
            Относительный POSIX-путь внутри корня хранилища.

        Raises:
            AvatarStorageError: Если сохранить файл не удалось.
        """
        try:
            return await asyncio.to_thread(self._save_sync, user_id, extension, content)
        except OSError as error:
            raise AvatarStorageError(str(error)) from error

    async def read(self, storage_key: str) -> bytes:
        """Читает содержимое файла.

        Args:
            storage_key: Относительный ключ внутри хранилища.

        Returns:
            Бинарное содержимое файла.

        Raises:
            AvatarStorageError: Если прочитать файл не удалось.
        """
        try:
            path = self.resolve(storage_key)
            return await asyncio.to_thread(path.read_bytes)
        except (OSError, ValueError) as error:
            raise AvatarStorageError(str(error)) from error

    async def delete(self, storage_key: str) -> None:
        """Удаляет файл, если он существует.

        Args:
            storage_key: Относительный ключ внутри хранилища.

        Raises:
            AvatarStorageError: Если удалить файл не удалось.
        """
        try:
            path = self.resolve(storage_key)
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except (OSError, ValueError) as error:
            raise AvatarStorageError(str(error)) from error

    async def delete_user_directory(self, user_id: int) -> None:
        """Удаляет каталог всех файлов пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Raises:
            AvatarStorageError: Если удалить каталог не удалось.
        """
        try:
            directory = self.root / str(user_id)
            await asyncio.to_thread(shutil.rmtree, directory, True)
        except OSError as error:
            raise AvatarStorageError(str(error)) from error

    def resolve(self, storage_key: str) -> Path:
        """Возвращает абсолютный путь, не выпуская за пределы корня.

        Args:
            storage_key: Относительный ключ внутри хранилища.

        Returns:
            Абсолютный путь к файлу.

        Raises:
            ValueError: Если ключ пытается выйти за корень хранилища.
        """
        candidate = PurePosixPath(storage_key)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"Недопустимый ключ хранилища: {storage_key!r}.")
        root = self.root.resolve()
        path = (root / Path(*candidate.parts)).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Ключ выходит за пределы хранилища: {storage_key!r}.")
        return path

    def _save_sync(self, user_id: int, extension: str, content: bytes) -> str:
        """Записывает файл через временный, чтобы не оставить недописанный файл."""
        directory = self.root / str(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}{extension}"
        target = directory / name
        temporary = target.with_suffix(f"{target.suffix}.part")
        temporary.write_bytes(content)
        temporary.replace(target)
        return str(PurePosixPath(str(user_id)) / name)
