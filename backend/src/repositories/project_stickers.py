import logging
from typing import Any

from sqlalchemy import Result, delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.project_stickers import ProjectSticker, ProjectStickerTaskLink
from src.exceptions.project_stickers import ProjectStickersRepositoryError

logger = logging.getLogger(__name__)


class ProjectStickersRepository:
    """Репозиторий стикеров проекта и их связей с задачами."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    @staticmethod
    def _with_task_links(statement):
        """Загружает связи задач и обновляет уже заполненную identity map."""
        return statement.options(selectinload(ProjectSticker.task_links)).execution_options(
            populate_existing=True
        )

    async def list_by_project_id(self, project_id: int) -> list[ProjectSticker]:
        """Возвращает все стикеры проекта от новых к старым."""
        try:
            statement = self._with_task_links(
                select(ProjectSticker)
                .where(ProjectSticker.project_id == project_id)
                .order_by(ProjectSticker.created_at.desc(), ProjectSticker.id.desc())
            )
            result: Result = await self.db_session.execute(statement)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить стикеры проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise ProjectStickersRepositoryError(
                f"Ошибка получения стикеров проекта id={project_id}."
            ) from error

    async def get_by_id(self, *, project_id: int, sticker_id: int) -> ProjectSticker | None:
        """Возвращает стикер только внутри указанного проекта."""
        try:
            statement = self._with_task_links(
                select(ProjectSticker).where(
                    ProjectSticker.id == sticker_id,
                    ProjectSticker.project_id == project_id,
                )
            )
            result: Result = await self.db_session.execute(statement)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить стикер id=%s.", sticker_id, exc_info=True)
            raise ProjectStickersRepositoryError(
                f"Ошибка получения стикера id={sticker_id}."
            ) from error

    async def insert(self, *, data: dict[str, Any]) -> int:
        """Вставляет стикер и возвращает его идентификатор.

        Связи с задачами и чтение готовой карточки — отдельные операции:
        порядок и транзакция принадлежат сервису.

        Args:
            data: Поля нового стикера.

        Returns:
            Идентификатор созданного стикера.

        Raises:
            ProjectStickersRepositoryError: Если вставка не удалась.
        """
        try:
            sticker = ProjectSticker(**data, revision=1)
            self.db_session.add(sticker)
            await self.db_session.flush()
            return sticker.id
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось создать стикер проекта.", exc_info=True)
            raise ProjectStickersRepositoryError("Ошибка создания стикера проекта.") from error

    async def replace_task_links(self, *, sticker_id: int, task_ids: list[int]) -> None:
        """Заменяет набор связей стикера с задачами.

        Args:
            sticker_id: Идентификатор стикера.
            task_ids: Новый набор задач.

        Raises:
            ProjectStickersRepositoryError: Если изменить связи не удалось.
        """
        try:
            await self.db_session.execute(
                delete(ProjectStickerTaskLink).where(
                    ProjectStickerTaskLink.sticker_id == sticker_id
                )
            )
            if task_ids:
                self.db_session.add_all(
                    [
                        ProjectStickerTaskLink(sticker_id=sticker_id, task_id=task_id)
                        for task_id in task_ids
                    ]
                )
            await self.db_session.flush()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось изменить связи стикера id=%s.", sticker_id, exc_info=True)
            raise ProjectStickersRepositoryError(
                f"Ошибка изменения связей стикера id={sticker_id}."
            ) from error

    async def update_fields(
        self,
        *,
        project_id: int,
        sticker_id: int,
        expected_revision: int,
        changes: dict[str, Any],
    ) -> bool:
        """Обновляет совпавшую ревизию стикера одним запросом.

        Совпадение ревизии проверяется самим `UPDATE`: отдельная проверка
        перед записью оставляла бы окно для параллельной правки.

        Args:
            project_id: Проект стикера.
            sticker_id: Идентификатор стикера.
            expected_revision: Ревизия, которую видел клиент.
            changes: Изменяемые поля.

        Returns:
            ``True``, если ревизия совпала и запись изменена.

        Raises:
            ProjectStickersRepositoryError: Если обновление не удалось.
        """
        try:
            statement = (
                update(ProjectSticker)
                .where(
                    ProjectSticker.id == sticker_id,
                    ProjectSticker.project_id == project_id,
                    ProjectSticker.revision == expected_revision,
                )
                .values(
                    **changes,
                    revision=ProjectSticker.revision + 1,
                    updated_at=func.now(),
                )
                .returning(ProjectSticker.id)
            )
            result: Result = await self.db_session.execute(statement)
            return result.scalar_one_or_none() is not None
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось изменить стикер id=%s.", sticker_id, exc_info=True)
            raise ProjectStickersRepositoryError(
                f"Ошибка изменения стикера id={sticker_id}."
            ) from error

    async def delete(
        self,
        *,
        project_id: int,
        sticker_id: int,
        expected_revision: int,
    ) -> bool:
        """Удаляет только совпавшую ревизию стикера; task links каскадируются."""
        try:
            statement = (
                delete(ProjectSticker)
                .where(
                    ProjectSticker.id == sticker_id,
                    ProjectSticker.project_id == project_id,
                    ProjectSticker.revision == expected_revision,
                )
                .returning(ProjectSticker.id)
            )
            result: Result = await self.db_session.execute(statement)
            return result.scalar_one_or_none() is not None
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить стикер id=%s.", sticker_id, exc_info=True)
            raise ProjectStickersRepositoryError(
                f"Ошибка удаления стикера id={sticker_id}."
            ) from error

    async def update_position(
        self,
        *,
        project_id: int,
        sticker_id: int,
        canvas_x: float,
        canvas_y: float,
        width: float | None = None,
        height: float | None = None,
    ) -> bool:
        """Перемещает стикер, не меняя ревизию и дату его содержимого.

        Args:
            project_id: Проект стикера.
            sticker_id: Идентификатор стикера.
            canvas_x: Новая координата по горизонтали.
            canvas_y: Новая координата по вертикали.

        Returns:
            ``True``, если стикер найден и перемещён.

        Raises:
            ProjectStickersRepositoryError: Если перемещение не удалось.
        """
        try:
            values: dict[str, Any] = {
                "canvas_x": canvas_x,
                "canvas_y": canvas_y,
                "updated_at": ProjectSticker.updated_at,
            }
            if width is not None:
                values["width"] = width
            if height is not None:
                values["height"] = height
            statement = (
                update(ProjectSticker)
                .where(
                    ProjectSticker.id == sticker_id,
                    ProjectSticker.project_id == project_id,
                )
                .values(**values)
                .returning(ProjectSticker.id)
            )
            result: Result = await self.db_session.execute(statement)
            return result.scalar_one_or_none() is not None
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось переместить стикер id=%s.", sticker_id, exc_info=True)
            raise ProjectStickersRepositoryError(
                f"Ошибка перемещения стикера id={sticker_id}."
            ) from error
