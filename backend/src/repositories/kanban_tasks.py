import logging

from sqlalchemy import Result, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.kanban_tasks import KanbanTask
from src.exceptions.kanban_tasks import (
    KanbanTasksRepositoryError,
    KanbanTaskWbsLinkAlreadyExistsRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name
from src.utils.fts import (
    EXCERPT_HEADLINE_OPTIONS,
    HIGHLIGHT_START,
    TITLE_HEADLINE_OPTIONS,
    build_ts_query,
)

logger = logging.getLogger(__name__)


class KanbanTasksRepository:
    """Репозиторий карточек канбан-доски."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(
        self,
        stage_id: int | None = None,
        task_ids: set[int] | None = None,
    ) -> list[KanbanTask]:
        """Возвращает задачи с опциональной фильтрацией по стадии и id.

        Args:
            stage_id: Опциональный идентификатор стадии.
            task_ids: Опциональный набор идентификаторов задач.

        Returns:
            Задачи в сохранённом порядке.

        Raises:
            KanbanTasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(KanbanTask).order_by(KanbanTask.position)
            if stage_id is not None:
                stmt = stmt.where(KanbanTask.stage_id == stage_id)
            if task_ids is not None:
                if not task_ids:
                    return []
                stmt = stmt.where(KanbanTask.id.in_(task_ids))
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить задачи канбана.", exc_info=True)
            raise KanbanTasksRepositoryError("Ошибка получения списка задач.") from error

    async def get_by_id(self, task_id: int) -> KanbanTask | None:
        """Возвращает задачу по идентификатору.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            Найденная задача или ``None``.

        Raises:
            KanbanTasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(KanbanTask).where(KanbanTask.id == task_id)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить задачу id=%s.", task_id, exc_info=True)
            raise KanbanTasksRepositoryError(f"Ошибка получения задачи id={task_id}.") from error

    async def get_by_ids(self, task_ids: set[int]) -> list[KanbanTask]:
        """Возвращает задачи по набору идентификаторов.

        Args:
            task_ids: Идентификаторы задач.

        Returns:
            Найденные задачи.

        Raises:
            KanbanTasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not task_ids:
            return []
        try:
            result: Result = await self.db_session.execute(
                select(KanbanTask).where(KanbanTask.id.in_(task_ids))
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить набор задач.", exc_info=True)
            raise KanbanTasksRepositoryError("Ошибка получения набора задач.") from error

    async def get_by_wbs_item_id(self, wbs_item_id: int) -> KanbanTask | None:
        """Возвращает задачу, связанную с узлом ИСР.

        Args:
            wbs_item_id: Идентификатор узла ИСР.

        Returns:
            Связанная задача или ``None``.

        Raises:
            KanbanTasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(KanbanTask).where(KanbanTask.wbs_item_id == wbs_item_id)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить задачу узла ИСР id=%s.", wbs_item_id, exc_info=True
            )
            raise KanbanTasksRepositoryError(
                f"Ошибка получения задачи узла ИСР id={wbs_item_id}."
            ) from error

    async def search_ids(self, search: str) -> set[int]:
        """Возвращает id задач, совпавших по FTS заголовка или описания.

        Args:
            search: Полнотекстовый запрос.

        Returns:
            Идентификаторы найденных задач.

        Raises:
            KanbanTasksRepositoryError: Если поиск завершился ошибкой.
        """
        try:
            ts_query = build_ts_query(search)
            result: Result = await self.db_session.execute(
                select(KanbanTask.id).where(KanbanTask.search_vector.op("@@")(ts_query))
            )
            return set(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось выполнить FTS-поиск задач.", exc_info=True)
            raise KanbanTasksRepositoryError("Ошибка полнотекстового поиска задач.") from error

    async def get_ids_by_wbs_item_ids(self, wbs_item_ids: set[int]) -> set[int]:
        """Возвращает id задач, связанных с указанными узлами ИСР.

        Args:
            wbs_item_ids: Идентификаторы узлов ИСР.

        Returns:
            Идентификаторы связанных задач.

        Raises:
            KanbanTasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not wbs_item_ids:
            return set()
        try:
            result: Result = await self.db_session.execute(
                select(KanbanTask.id).where(KanbanTask.wbs_item_id.in_(wbs_item_ids))
            )
            return set(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить задачи по узлам ИСР.", exc_info=True)
            raise KanbanTasksRepositoryError("Ошибка получения задач по узлам ИСР.") from error

    async def get_count_by_stage(self, stage_id: int) -> int:
        """Возвращает количество задач в указанной стадии.

        Args:
            stage_id: Идентификатор стадии.

        Returns:
            Количество задач.

        Raises:
            KanbanTasksRepositoryError: Если подсчёт завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(func.count()).select_from(KanbanTask).where(KanbanTask.stage_id == stage_id)
            )
            return result.scalar_one()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подсчитать задачи стадии id=%s.", stage_id, exc_info=True)
            raise KanbanTasksRepositoryError(
                f"Ошибка подсчёта задач стадии id={stage_id}."
            ) from error

    async def get_max_position_by_stage(self, stage_id: int) -> float:
        """Возвращает наибольшую позицию задачи в указанной стадии.

        Args:
            stage_id: Идентификатор стадии.

        Returns:
            Наибольшая позиция или ``0.0`` для пустой стадии.

        Raises:
            KanbanTasksRepositoryError: Если запрос завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(func.coalesce(func.max(KanbanTask.position), 0.0)).where(
                    KanbanTask.stage_id == stage_id
                )
            )
            return float(result.scalar_one())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить максимальную позицию стадии id=%s.",
                stage_id,
                exc_info=True,
            )
            raise KanbanTasksRepositoryError(
                f"Ошибка получения позиции задач стадии id={stage_id}."
            ) from error

    async def get_search_highlights(
        self,
        task_ids: list[int],
        search: str,
    ) -> dict[int, dict[str, str]]:
        """Возвращает подсвеченные совпадения в заголовках и описаниях задач.

        Args:
            task_ids: Идентификаторы отображаемых задач.
            search: Полнотекстовый запрос.

        Returns:
            Поисковый контекст по идентификаторам задач.

        Raises:
            KanbanTasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not task_ids or not search.strip():
            return {}
        try:
            ts_query = build_ts_query(search)
            title_vector = func.to_tsvector("russian", func.coalesce(KanbanTask.title, ""))
            description_vector = func.to_tsvector(
                "russian", func.coalesce(KanbanTask.description_md, "")
            )
            stmt = select(
                KanbanTask.id,
                title_vector.op("@@")(ts_query).label("title_matches"),
                description_vector.op("@@")(ts_query).label("description_matches"),
                func.ts_headline(
                    "russian", KanbanTask.title, ts_query, TITLE_HEADLINE_OPTIONS
                ).label("title_headline"),
                func.ts_headline(
                    "russian",
                    func.coalesce(KanbanTask.description_md, ""),
                    ts_query,
                    EXCERPT_HEADLINE_OPTIONS,
                ).label("description_headline"),
            ).where(KanbanTask.id.in_(task_ids))
            rows = (await self.db_session.execute(stmt)).mappings().all()

            highlights: dict[int, dict[str, str]] = {}
            for row in rows:
                data: dict[str, str] = {}
                if HIGHLIGHT_START in row["title_headline"]:
                    data["search_title"] = row["title_headline"]
                if row["title_matches"]:
                    data["search_match_source"] = "title"
                elif row["description_matches"]:
                    data["search_match_source"] = "description"
                    data["search_excerpt"] = row["description_headline"]
                if data:
                    highlights[row["id"]] = data
            return highlights
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подготовить подсветку задач.", exc_info=True)
            raise KanbanTasksRepositoryError("Ошибка подсветки результатов задач.") from error

    async def save(self, data: dict) -> KanbanTask:
        """Создаёт задачу и возвращает сохранённую модель.

        Args:
            data: Поля новой задачи.

        Returns:
            Сохранённая задача.

        Raises:
            KanbanTaskWbsLinkAlreadyExistsRepositoryError: Если узел ИСР уже связан с задачей.
            KanbanTasksRepositoryError: Если сохранить задачу не удалось.
        """
        try:
            task = KanbanTask(**data)
            self.db_session.add(task)
            await self.db_session.commit()
            await self.db_session.refresh(task)
            return task
        except IntegrityError as error:
            await self.db_session.rollback()
            constraint_name = get_integrity_constraint_name(error)
            if constraint_name in {
                "kanban_tasks_wbs_item_id_key",
                "uq_kanban_tasks_wbs_item_id",
            }:
                wbs_item_id = data.get("wbs_item_id")
                if wbs_item_id is not None:
                    logger.warning("⚠️ Узел ИСР id=%s уже связан с задачей.", wbs_item_id)
                    raise KanbanTaskWbsLinkAlreadyExistsRepositoryError(
                        wbs_item_id=wbs_item_id
                    ) from error
            logger.error("❌ Ограничение БД не позволило сохранить задачу.", exc_info=True)
            raise KanbanTasksRepositoryError(
                "Ошибка ограничения БД при сохранении задачи."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить задачу.", exc_info=True)
            raise KanbanTasksRepositoryError("Ошибка сохранения задачи.") from error

    async def update(self, task: KanbanTask, data: dict) -> KanbanTask:
        """Обновляет задачу и возвращает сохранённую модель.

        Args:
            task: Изменяемая ORM-модель задачи.
            data: Новые значения полей.

        Returns:
            Обновлённая задача.

        Raises:
            KanbanTasksRepositoryError: Если обновить задачу не удалось.
        """
        try:
            for field, value in data.items():
                setattr(task, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(task)
            return task
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить задачу id=%s.", task.id, exc_info=True)
            raise KanbanTasksRepositoryError(f"Ошибка обновления задачи id={task.id}.") from error

    async def delete(self, task: KanbanTask) -> None:
        """Удаляет задачу.

        Args:
            task: Удаляемая ORM-модель задачи.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            KanbanTasksRepositoryError: Если удалить задачу не удалось.
        """
        try:
            await self.db_session.delete(task)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить задачу id=%s.", task.id, exc_info=True)
            raise KanbanTasksRepositoryError(f"Ошибка удаления задачи id={task.id}.") from error
