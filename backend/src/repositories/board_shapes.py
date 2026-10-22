import logging
from typing import Any, Literal

from sqlalchemy import Result, case, delete, func, literal, null, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.board_shapes import BoardShape
from src.exceptions.board_shapes import BoardShapesRepositoryError

logger = logging.getLogger(__name__)

RefTargetType = Literal["sticker", "shape"]


class BoardShapesRepository:
    """Репозиторий фигур доски и привязок стрелок."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def _fail(self, message: str) -> BoardShapesRepositoryError:
        """Откатывает сессию и готовит ошибку слоя репозитория."""
        await self.db_session.rollback()
        logger.error("❌ %s", message, exc_info=True)
        return BoardShapesRepositoryError(message)

    async def list_by_board(self, board_id: int) -> list[BoardShape]:
        """Возвращает фигуры доски снизу вверх по слоям."""
        try:
            result: Result = await self.db_session.execute(
                select(BoardShape)
                .where(BoardShape.board_id == board_id)
                .order_by(BoardShape.z_index, BoardShape.id)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise await self._fail(f"Ошибка получения фигур доски id={board_id}.") from error

    async def list_by_ids(
        self,
        *,
        board_id: int,
        shape_ids: set[int],
        for_update: bool = False,
        for_share: bool = False,
    ) -> list[BoardShape]:
        """Возвращает фигуры доски из набора id.

        Args:
            board_id: Доска фигур; чужие фигуры не возвращаются.
            shape_ids: Нужные фигуры.
            for_update: Заблокировать строки до конца транзакции для изменения.
            for_share: Заблокировать строки от удаления, пока на них ставится привязка.
        """
        if not shape_ids:
            return []
        try:
            statement = (
                select(BoardShape)
                .where(BoardShape.board_id == board_id, BoardShape.id.in_(shape_ids))
                .order_by(BoardShape.id)
                .execution_options(populate_existing=True)
            )
            if for_update:
                statement = statement.with_for_update()
            elif for_share:
                statement = statement.with_for_update(read=True)
            result: Result = await self.db_session.execute(statement)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise await self._fail(f"Ошибка получения фигур доски id={board_id}.") from error

    async def count_by_board(self, board_id: int) -> int:
        """Считает фигуры доски для проверки лимита."""
        try:
            result: Result = await self.db_session.execute(
                select(func.count(BoardShape.id)).where(BoardShape.board_id == board_id)
            )
            return int(result.scalar_one())
        except (SQLAlchemyError, Exception) as error:
            raise await self._fail(f"Ошибка подсчёта фигур доски id={board_id}.") from error

    async def insert(self, *, data: dict[str, Any]) -> BoardShape:
        """Вставляет фигуру; серверные поля приходят из RETURNING."""
        try:
            shape = BoardShape(**data, revision=1)
            self.db_session.add(shape)
            await self.db_session.flush()
            return shape
        except (SQLAlchemyError, Exception) as error:
            raise await self._fail("Ошибка создания фигуры доски.") from error

    async def update_fields(
        self,
        *,
        board_id: int,
        shape_id: int,
        changes: dict[str, Any],
        expected_revision: int | None = None,
    ) -> BoardShape | None:
        """Меняет фигуру одним запросом и повышает её ревизию.

        Args:
            expected_revision: Если передана — запись меняется только при
                совпадении; ``None`` — last-write-wins.

        Returns:
            Изменённая фигура или ``None``, если её нет или ревизия устарела.
        """
        try:
            statement = update(BoardShape).where(
                BoardShape.id == shape_id, BoardShape.board_id == board_id
            )
            if expected_revision is not None:
                statement = statement.where(BoardShape.revision == expected_revision)
            result: Result = await self.db_session.execute(
                statement.values(**changes, revision=BoardShape.revision + 1, updated_at=func.now())
                .returning(BoardShape)
                .execution_options(populate_existing=True)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            raise await self._fail(f"Ошибка изменения фигуры id={shape_id}.") from error

    async def delete(
        self, *, board_id: int, shape_id: int, expected_revision: int | None = None
    ) -> bool:
        """Удаляет фигуру; при переданной ревизии — только совпавшую."""
        try:
            statement = delete(BoardShape).where(
                BoardShape.id == shape_id, BoardShape.board_id == board_id
            )
            if expected_revision is not None:
                statement = statement.where(BoardShape.revision == expected_revision)
            result: Result = await self.db_session.execute(statement.returning(BoardShape.id))
            return result.scalar_one_or_none() is not None
        except (SQLAlchemyError, Exception) as error:
            raise await self._fail(f"Ошибка удаления фигуры id={shape_id}.") from error

    async def detach_refs(
        self, *, board_id: int, target_type: RefTargetType, target_id: int
    ) -> list[BoardShape]:
        """Отцепляет от удалённого объекта все стрелки доски одним запросом.

        Точки стрелок остаются: стрелка «отцепляется», а не пропадает.
        """
        target = {"type": target_type, "id": target_id}
        start_match = BoardShape.start_ref.contains(target)
        end_match = BoardShape.end_ref.contains(target)
        try:
            result: Result = await self.db_session.execute(
                update(BoardShape)
                .where(BoardShape.board_id == board_id, or_(start_match, end_match))
                .values(
                    start_ref=case((start_match, null()), else_=BoardShape.start_ref),
                    end_ref=case((end_match, null()), else_=BoardShape.end_ref),
                    revision=BoardShape.revision + 1,
                    updated_at=func.now(),
                )
                .returning(BoardShape)
                .execution_options(populate_existing=True)
            )
            detached = list(result.scalars().all())
            if detached:
                logger.info(
                    "💾 Отцеплено стрелок от %s id=%s: %s.", target_type, target_id, len(detached)
                )
            return detached
        except (SQLAlchemyError, Exception) as error:
            raise await self._fail(
                f"Ошибка отцепления стрелок от {target_type} id={target_id}."
            ) from error

    async def retarget_shape_refs(
        self, *, board_id: int, shape_id: int, sticker_id: int
    ) -> list[BoardShape]:
        """Перецепляет стрелки с фигуры на стикер, сохраняя точку крепления."""
        target = {"type": "shape", "id": shape_id}
        replacement = literal({"type": "sticker", "id": sticker_id}, type_=JSONB)
        start_match = BoardShape.start_ref.contains(target)
        end_match = BoardShape.end_ref.contains(target)
        try:
            result: Result = await self.db_session.execute(
                update(BoardShape)
                .where(BoardShape.board_id == board_id, or_(start_match, end_match))
                .values(
                    start_ref=case(
                        (
                            start_match,
                            BoardShape.start_ref.op("||", return_type=JSONB)(replacement),
                        ),
                        else_=BoardShape.start_ref,
                    ),
                    end_ref=case(
                        (end_match, BoardShape.end_ref.op("||", return_type=JSONB)(replacement)),
                        else_=BoardShape.end_ref,
                    ),
                    revision=BoardShape.revision + 1,
                    updated_at=func.now(),
                )
                .returning(BoardShape)
                .execution_options(populate_existing=True)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            raise await self._fail(f"Ошибка перецепки стрелок с фигуры id={shape_id}.") from error
