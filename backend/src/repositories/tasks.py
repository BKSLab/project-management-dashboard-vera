import logging
from datetime import date

from sqlalchemy import Result, Row, and_, case, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.db.models.tasks import Task
from src.exceptions.tasks import (
    TaskNumberAlreadyExistsRepositoryError,
    TasksRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name
from src.utils.fts import (
    EXCERPT_HEADLINE_OPTIONS,
    HIGHLIGHT_START,
    TITLE_HEADLINE_OPTIONS,
    build_ts_query,
)

logger = logging.getLogger(__name__)

TASK_NUMBER_CONSTRAINTS = frozenset({"uq_tasks_project_number"})


class TasksRepository:
    """Репозиторий задач проекта."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_project(
        self,
        project_id: int,
        stage_id: int | None = None,
        task_ids: set[int] | None = None,
    ) -> list[Task]:
        """Возвращает задачи проекта с опциональными фильтрами.

        Args:
            project_id: Идентификатор проекта.
            stage_id: Опциональный идентификатор стадии.
            task_ids: Опциональный набор идентификаторов задач.

        Returns:
            Задачи проекта в сохранённом порядке.

        Raises:
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = (
                select(Task).where(Task.project_id == project_id).order_by(Task.position, Task.id)
            )
            if stage_id is not None:
                stmt = stmt.where(Task.stage_id == stage_id)
            if task_ids is not None:
                if not task_ids:
                    return []
                stmt = stmt.where(Task.id.in_(task_ids))
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить задачи проекта id=%s.", project_id, exc_info=True)
            raise TasksRepositoryError(
                f"Ошибка получения задач проекта id={project_id}."
            ) from error

    async def get_by_id(self, task_id: int) -> Task | None:
        """Возвращает задачу по идентификатору.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            Найденная задача или ``None``.

        Raises:
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(select(Task).where(Task.id == task_id))
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить задачу id=%s.", task_id, exc_info=True)
            raise TasksRepositoryError(f"Ошибка получения задачи id={task_id}.") from error

    async def get_by_ids(self, task_ids: set[int]) -> list[Task]:
        """Возвращает задачи по набору идентификаторов.

        Args:
            task_ids: Идентификаторы задач.

        Returns:
            Найденные задачи.

        Raises:
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not task_ids:
            return []
        try:
            result: Result = await self.db_session.execute(
                select(Task).where(Task.id.in_(task_ids))
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить набор задач.", exc_info=True)
            raise TasksRepositoryError("Ошибка получения набора задач.") from error

    async def get_next_number(self, project_id: int) -> int:
        """Возвращает следующий свободный номер задачи в проекте.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Номер для новой задачи, начиная с ``1``.

        Raises:
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(func.coalesce(func.max(Task.number), 0) + 1).where(
                    Task.project_id == project_id
                )
            )
            return int(result.scalar_one())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить номер задачи проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise TasksRepositoryError(
                f"Ошибка получения номера задачи проекта id={project_id}."
            ) from error

    async def get_count_by_stage(self, stage_id: int) -> int:
        """Возвращает количество задач в указанной стадии.

        Args:
            stage_id: Идентификатор стадии.

        Returns:
            Количество задач.

        Raises:
            TasksRepositoryError: Если подсчёт завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(func.count()).select_from(Task).where(Task.stage_id == stage_id)
            )
            return int(result.scalar_one())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подсчитать задачи стадии id=%s.", stage_id, exc_info=True)
            raise TasksRepositoryError(f"Ошибка подсчёта задач стадии id={stage_id}.") from error

    async def get_max_position_by_stage(self, stage_id: int) -> float:
        """Возвращает наибольшую позицию задачи в указанной стадии.

        Args:
            stage_id: Идентификатор стадии.

        Returns:
            Наибольшая позиция или ``0.0`` для пустой стадии.

        Raises:
            TasksRepositoryError: Если запрос завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(func.coalesce(func.max(Task.position), 0.0)).where(Task.stage_id == stage_id)
            )
            return float(result.scalar_one())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить максимальную позицию стадии id=%s.",
                stage_id,
                exc_info=True,
            )
            raise TasksRepositoryError(
                f"Ошибка получения позиции задач стадии id={stage_id}."
            ) from error

    async def search_ids(self, project_id: int, search: str) -> set[int]:
        """Возвращает id задач проекта, совпавших по FTS или номеру.

        Args:
            project_id: Идентификатор проекта.
            search: Поисковый запрос.

        Returns:
            Идентификаторы найденных задач.

        Raises:
            TasksRepositoryError: Если поиск завершился ошибкой.
        """
        try:
            ts_query = build_ts_query(search)
            condition = Task.search_vector.op("@@")(ts_query)
            number = _extract_task_number(search)
            if number is not None:
                condition = or_(condition, Task.number == number)
            result: Result = await self.db_session.execute(
                select(Task.id).where(and_(Task.project_id == project_id, condition))
            )
            return set(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось выполнить поиск задач.", exc_info=True)
            raise TasksRepositoryError("Ошибка поиска задач.") from error

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
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not task_ids or not search.strip():
            return {}
        try:
            ts_query = build_ts_query(search)
            title_vector = func.to_tsvector("russian", func.coalesce(Task.title, ""))
            description_vector = func.to_tsvector("russian", func.coalesce(Task.description_md, ""))
            stmt = select(
                Task.id,
                title_vector.op("@@")(ts_query).label("title_matches"),
                description_vector.op("@@")(ts_query).label("description_matches"),
                func.ts_headline("russian", Task.title, ts_query, TITLE_HEADLINE_OPTIONS).label(
                    "title_headline"
                ),
                func.ts_headline(
                    "russian",
                    func.coalesce(Task.description_md, ""),
                    ts_query,
                    EXCERPT_HEADLINE_OPTIONS,
                ).label("description_headline"),
            ).where(Task.id.in_(task_ids))
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
            raise TasksRepositoryError("Ошибка подсветки результатов задач.") from error

    async def get_stage_counts(self) -> list[Row]:
        """Возвращает количество задач по каждой стадии всех проектов.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Строки ``(project_id, stage_id, tasks_count)``.

        Raises:
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(
                    Task.project_id,
                    Task.stage_id,
                    func.count().label("tasks_count"),
                ).group_by(Task.project_id, Task.stage_id)
            )
            return list(result.all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подсчитать задачи по стадиям.", exc_info=True)
            raise TasksRepositoryError("Ошибка подсчёта задач по стадиям.") from error

    async def get_portfolio_counters(self, today: date, soon_until: date) -> list[Row]:
        """Возвращает агрегаты задач по всем проектам одним запросом.

        Args:
            today: Текущая дата для определения просрочки.
            soon_until: Верхняя граница окна ближайших сроков.

        Returns:
            Строки ``(project_id, total, done, overdue, due_soon, next_due_date)``.

        Raises:
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            is_open = ProjectStage.is_done_stage.is_(False)
            result: Result = await self.db_session.execute(
                select(
                    Task.project_id,
                    func.count().label("total"),
                    func.count().filter(ProjectStage.is_done_stage.is_(True)).label("done"),
                    func.count()
                    .filter(and_(is_open, Task.due_date.is_not(None), Task.due_date < today))
                    .label("overdue"),
                    func.count()
                    .filter(
                        and_(
                            is_open,
                            Task.due_date.is_not(None),
                            Task.due_date >= today,
                            Task.due_date <= soon_until,
                        )
                    )
                    .label("due_soon"),
                    func.min(Task.due_date)
                    .filter(and_(is_open, Task.due_date >= today))
                    .label("next_due_date"),
                )
                .join(ProjectStage, ProjectStage.id == Task.stage_id)
                .group_by(Task.project_id)
            )
            return list(result.all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подсчитать показатели проектов.", exc_info=True)
            raise TasksRepositoryError("Ошибка подсчёта показателей проектов.") from error

    async def get_attention_tasks(
        self,
        today: date,
        soon_until: date,
        limit: int,
    ) -> list[Task]:
        """Возвращает незавершённые задачи с просроченным или ближайшим сроком.

        Args:
            today: Текущая дата.
            soon_until: Верхняя граница окна ближайших сроков.
            limit: Максимальное количество задач.

        Returns:
            Задачи, отсортированные по возрастанию срока.

        Raises:
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(Task)
                .join(ProjectStage, ProjectStage.id == Task.stage_id)
                .where(
                    and_(
                        ProjectStage.is_done_stage.is_(False),
                        Task.due_date.is_not(None),
                        Task.due_date <= soon_until,
                    )
                )
                .order_by(
                    case((Task.due_date < today, 0), else_=1),
                    Task.due_date,
                    Task.id,
                )
                .limit(limit)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить задачи с ближайшими сроками.", exc_info=True)
            raise TasksRepositoryError("Ошибка получения задач с ближайшими сроками.") from error

    async def get_recent(self, limit: int, project_id: int | None = None) -> list[Task]:
        """Возвращает недавно изменённые задачи.

        Args:
            limit: Максимальное количество задач.
            project_id: Опциональный фильтр по проекту.

        Returns:
            Задачи, отсортированные по убыванию даты обновления.

        Raises:
            TasksRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(Task).order_by(Task.updated_at.desc(), Task.id.desc()).limit(limit)
            if project_id is not None:
                stmt = stmt.where(Task.project_id == project_id)
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить недавние задачи.", exc_info=True)
            raise TasksRepositoryError("Ошибка получения недавних задач.") from error

    async def clear_wbs_node(self, node_ids: set[int]) -> int:
        """Снимает привязку задач к удаляемым разделам ИСР.

        Args:
            node_ids: Идентификаторы разделов ИСР.

        Синхронизирует identity map сессии, чтобы уже загруженные задачи не
        сохраняли устаревшую привязку к удалённому разделу.

        Returns:
            Количество затронутых задач.

        Raises:
            TasksRepositoryError: Если обновление завершилось ошибкой.
        """
        if not node_ids:
            return 0
        try:
            result = await self.db_session.execute(
                update(Task)
                .where(Task.wbs_node_id.in_(node_ids))
                .values(wbs_node_id=None)
                .execution_options(synchronize_session="fetch")
            )
            await self.db_session.commit()
            return int(result.rowcount or 0)
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось снять привязку задач к разделам ИСР.", exc_info=True)
            raise TasksRepositoryError("Ошибка снятия привязки задач к разделам ИСР.") from error

    async def save(self, data: dict) -> Task:
        """Создаёт задачу и возвращает сохранённую модель.

        Args:
            data: Поля новой задачи.

        Returns:
            Сохранённая задача.

        Raises:
            TaskNumberAlreadyExistsRepositoryError: Если номер задачи уже занят.
            TasksRepositoryError: Если сохранить задачу не удалось.
        """
        try:
            task = Task(**data)
            self.db_session.add(task)
            await self.db_session.commit()
            await self.db_session.refresh(task)
            return task
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) in TASK_NUMBER_CONSTRAINTS:
                project_id = int(data.get("project_id", 0))
                number = int(data.get("number", 0))
                logger.warning("⚠️ Номер %s уже занят в проекте id=%s.", number, project_id)
                raise TaskNumberAlreadyExistsRepositoryError(
                    project_id=project_id,
                    number=number,
                ) from error
            logger.error("❌ Ограничение БД не позволило сохранить задачу.", exc_info=True)
            raise TasksRepositoryError("Ошибка ограничения БД при сохранении задачи.") from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить задачу.", exc_info=True)
            raise TasksRepositoryError("Ошибка сохранения задачи.") from error

    async def update(self, task: Task, data: dict) -> Task:
        """Обновляет задачу и возвращает сохранённую модель.

        Args:
            task: Изменяемая ORM-модель задачи.
            data: Новые значения полей.

        Returns:
            Обновлённая задача.

        Raises:
            TasksRepositoryError: Если обновить задачу не удалось.
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
            raise TasksRepositoryError(f"Ошибка обновления задачи id={task.id}.") from error

    async def delete(self, task: Task) -> None:
        """Удаляет задачу.

        Args:
            task: Удаляемая ORM-модель задачи.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            TasksRepositoryError: Если удалить задачу не удалось.
        """
        try:
            await self.db_session.delete(task)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить задачу id=%s.", task.id, exc_info=True)
            raise TasksRepositoryError(f"Ошибка удаления задачи id={task.id}.") from error


def _extract_task_number(search: str) -> int | None:
    """Возвращает номер задачи из запроса вида ``VERA-142`` или ``142``."""
    candidate = search.strip().rsplit("-", maxsplit=1)[-1]
    return int(candidate) if candidate.isdigit() else None
