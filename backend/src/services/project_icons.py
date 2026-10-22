"""Своя картинка-иконка проекта.

Картинка проверяется по сигнатуре содержимого, а не по имени и заявленному
типу: SVG и всё, что браузер может исполнить, не принимается. Файл уходит в
то же хранилище, что вложения; ссылка на него хранится в проекте и наружу не
отдаётся — картинку отдаёт эндпоинт трекера после проверки доступа.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import PurePosixPath

from src.exceptions.projects import (
    ProjectIconImageInvalidError,
    ProjectIconImageNotFoundError,
    ProjectIconImageTooLargeError,
    ProjectIconStorageError,
    ProjectNotFoundError,
    ProjectsRepositoryError,
    ProjectsServiceError,
)
from src.exceptions.storage import TaskAttachmentStorageError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.repositories.projects import ProjectsRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.projects import ProjectSchema
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)

MAX_ICON_IMAGE_SIZE = 2 * 1024 * 1024

# Сигнатура → (MIME, расширение). Только растровые форматы без скриптов.
_SIGNATURES: tuple[tuple[bytes, int, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", 0, "image/png", ".png"),
    (b"\xff\xd8\xff", 0, "image/jpeg", ".jpg"),
)


def detect_image_type(content: bytes) -> tuple[str, str] | None:
    """Определяет PNG, JPEG или WebP по первым байтам.

    Returns:
        Пара (MIME, расширение) либо ``None`` для любого другого содержимого.
    """
    for signature, offset, mime, extension in _SIGNATURES:
        if content[offset : offset + len(signature)] == signature:
            return mime, extension
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


@dataclass(frozen=True, slots=True)
class ProjectIconImage:
    """Локальное изображение проекта и его MIME-тип."""

    content: bytes
    content_type: str


class ProjectIconsService:
    """Загружает, отдаёт и убирает свою картинку проекта."""

    def __init__(
        self,
        *,
        projects_repository: ProjectsRepository,
        unit_of_work: UnitOfWork,
        storage: TaskAttachmentStorage,
    ) -> None:
        self.projects_repository = projects_repository
        self.unit_of_work = unit_of_work
        self.storage = storage

    async def upload(
        self,
        *,
        project_id: int,
        content: bytes,
    ) -> ProjectSchema:
        """Проверяет и сохраняет картинку, заменяя прежнюю.

        Args:
            project_id: Проект, право менять который уже проверено.
            content: Содержимое загруженного файла.

        Returns:
            Проект с новой версией картинки.

        Raises:
            ProjectIconImageTooLargeError: Больше 2 МБ.
            ProjectIconImageInvalidError: Пустой файл или не PNG/JPEG/WebP.
            ProjectNotFoundError: Проекта нет.
            ProjectIconStorageError: Хранилище не приняло файл.
            ProjectsServiceError: Ошибка базы данных.
        """
        if len(content) > MAX_ICON_IMAGE_SIZE:
            raise ProjectIconImageTooLargeError()
        detected = detect_image_type(content)
        if not content or detected is None:
            raise ProjectIconImageInvalidError("Содержимое не похоже на PNG, JPEG или WebP.")
        content_type, extension = detected
        key: str | None = None
        try:
            project = await self._require(project_id)
            key = await self.storage.save_in(
                PurePosixPath("projects", str(project_id)), extension, content
            )
            previous = project.icon_image_key
            updated = await self.projects_repository.update(
                project=project,
                data={"icon_image_key": key, "icon_image_content_type": content_type},
            )
            response = self._schema(updated)
            await self.unit_of_work.commit()
        except TaskAttachmentStorageError as error:
            logger.error("❌ Картинка проекта id=%s не сохранена.", project_id, exc_info=True)
            await self.unit_of_work.rollback()
            raise ProjectIconStorageError(str(error)) from error
        except (ProjectsRepositoryError, UnitOfWorkRepositoryError) as error:
            logger.error("❌ Ошибка сохранения картинки проекта id=%s.", project_id, exc_info=True)
            await self.unit_of_work.rollback()
            # Не оставляем новый локальный файл после отката записи проекта.
            await self._forget(key)
            raise ProjectsServiceError(str(error)) from error
        except ProjectsServiceError:
            await self.unit_of_work.rollback()
            raise
        await self._forget(previous)
        logger.info("✅ Картинка проекта id=%s обновлена.", project_id)
        return response

    async def remove(
        self, *, project_id: int
    ) -> ProjectSchema:
        """Убирает свою картинку; проект снова показывает иконку или точку.

        Raises:
            ProjectNotFoundError: Проекта нет.
            ProjectsServiceError: Ошибка базы данных.
        """
        try:
            project = await self._require(project_id)
            previous = project.icon_image_key
            updated = await self.projects_repository.update(
                project=project, data={"icon_image_key": None, "icon_image_content_type": None}
            )
            response = self._schema(updated)
            await self.unit_of_work.commit()
        except (ProjectsRepositoryError, UnitOfWorkRepositoryError) as error:
            logger.error("❌ Ошибка удаления картинки проекта id=%s.", project_id, exc_info=True)
            await self.unit_of_work.rollback()
            raise ProjectsServiceError(str(error)) from error
        except ProjectsServiceError:
            await self.unit_of_work.rollback()
            raise
        await self._forget(previous)
        return response

    async def get(self, project_id: int) -> ProjectIconImage:
        """Находит картинку проекта для выдачи.

        Raises:
            ProjectNotFoundError: Проекта нет.
            ProjectIconImageNotFoundError: Картинка не загружена или пропала с диска.
            ProjectIconStorageError: Хранилище не настроено для ссылки.
            ProjectsServiceError: Ошибка базы данных.
        """
        try:
            project = await self.projects_repository.get_by_id(project_id=project_id)
        except ProjectsRepositoryError as error:
            raise ProjectsServiceError(str(error)) from error
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)
        if not project.icon_image_key or not project.icon_image_content_type:
            raise ProjectIconImageNotFoundError(project_id=project_id)
        try:
            path = self.storage.resolve(project.icon_image_key)
            content = await asyncio.to_thread(path.read_bytes)
            if len(content) > MAX_ICON_IMAGE_SIZE:
                raise ProjectIconStorageError("Stored project icon exceeds its size limit.")
        except TaskAttachmentStorageError as error:
            raise ProjectIconImageNotFoundError(project_id=project_id) from error
        except OSError as error:
            raise ProjectIconStorageError(str(error)) from error
        return ProjectIconImage(content=content, content_type=project.icon_image_content_type)

    async def _require(self, project_id: int):
        project = await self.projects_repository.get_by_id(project_id=project_id, for_update=True)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)
        return project

    async def _forget(self, key: str | None) -> None:
        """Убирает прежний локальный файл после замены или удаления картинки."""
        if not key:
            return
        try:
            await self.storage.delete(key)
        except TaskAttachmentStorageError:
            logger.warning("⚠️ Прежняя картинка проекта требует очистки.", exc_info=True)

    @staticmethod
    def _schema(project) -> ProjectSchema:
        return ProjectSchema.model_validate(project)
