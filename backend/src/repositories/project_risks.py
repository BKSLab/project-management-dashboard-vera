import logging
from datetime import date
from typing import Any, NoReturn

from sqlalchemy import Select, case, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_risks import ProjectRisk
from src.exceptions.project_risks import ProjectRiskRepositoryError
from src.schemas.enums import RiskSource, RiskStatus
from src.schemas.project_risks import ProjectRiskFilters

logger = logging.getLogger(__name__)


class ProjectRiskRepository:
    """SQL-операции реестра; транзакцией записи владеет application service."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def get_by_id(
        self, *, project_id: int, risk_id: int, for_update: bool = False
    ) -> ProjectRisk | None:
        """Читает риск строго внутри проекта, при изменении блокирует строку.

        Args:
            project_id: Проект запроса.
            risk_id: Идентификатор риска.
            for_update: Сериализовать изменения оценки по актуальной паре значений.

        Returns:
            Риск либо None.

        Raises:
            ProjectRiskRepositoryError: Ошибка чтения.
        """
        try:
            statement = select(ProjectRisk).where(
                ProjectRisk.project_id == project_id, ProjectRisk.id == risk_id
            )
            if for_update:
                statement = statement.with_for_update().execution_options(populate_existing=True)
            return (await self.db_session.execute(statement)).scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self._fail("получить риск", error)

    async def get_by_ids(self, *, project_id: int, risk_ids: set[int]) -> list[ProjectRisk]:
        """Проверяет найденные индексом риски одним SQL-запросом.

        Args:
            project_id: Разрешённый проект.
            risk_ids: Идентификаторы кандидатов поиска.

        Returns:
            Только существующие риски данного проекта.

        Raises:
            ProjectRiskRepositoryError: Ошибка чтения.
        """
        try:
            statement = select(ProjectRisk).where(
                ProjectRisk.project_id == project_id, ProjectRisk.id.in_(risk_ids)
            )
            return list((await self.db_session.execute(statement)).scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self._fail("проверить риски поиска", error)

    async def get_page(
        self, *, project_id: int, filters: ProjectRiskFilters, page: int, page_size: int
    ) -> list[ProjectRisk]:
        """Читает одну страницу реестра в стабильном порядке.

        Args:
            project_id: Проект запроса.
            filters: Условия поиска.
            page: Номер страницы от единицы.
            page_size: Размер страницы.

        Returns:
            Риски по уровню опасности, затем дате контроля и ID.

        Raises:
            ProjectRiskRepositoryError: Ошибка чтения.
        """
        try:
            statement = self._filter(
                select(ProjectRisk).where(ProjectRisk.project_id == project_id), filters
            )
            statement = (
                statement.order_by(
                    case((ProjectRisk.status == RiskStatus.CLOSED, 1), else_=0),
                    case(
                        (ProjectRisk.risk_level == "HIGH", 0),
                        (ProjectRisk.risk_level == "MEDIUM", 1),
                        else_=2,
                    ),
                    ProjectRisk.review_date.asc().nulls_last(),
                    ProjectRisk.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            return list((await self.db_session.execute(statement)).scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self._fail("получить страницу рисков", error)

    async def get_count(self, *, project_id: int, filters: ProjectRiskFilters) -> int:
        """Считает весь отфильтрованный набор без загрузки записей.

        Args:
            project_id: Проект запроса.
            filters: Условия поиска.

        Returns:
            Число совпадений.

        Raises:
            ProjectRiskRepositoryError: Ошибка подсчёта.
        """
        try:
            statement = self._filter(
                select(func.count())
                .select_from(ProjectRisk)
                .where(ProjectRisk.project_id == project_id),
                filters,
            )
            return int((await self.db_session.execute(statement)).scalar_one())
        except (SQLAlchemyError, Exception) as error:
            await self._fail("подсчитать риски", error)

    async def get_by_project(self, project_id: int) -> list[ProjectRisk]:
        """Читает исходные риски для индексации и аналитического снимка.

        Args:
            project_id: Проект запроса.

        Returns:
            Риски в порядке идентификаторов.

        Raises:
            ProjectRiskRepositoryError: Ошибка чтения.
        """
        try:
            statement = (
                select(ProjectRisk)
                .where(ProjectRisk.project_id == project_id)
                .order_by(ProjectRisk.id)
            )
            return list((await self.db_session.execute(statement)).scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self._fail("получить риски проекта", error)

    async def get_aggregates(
        self, *, project_ids: set[int], filters: ProjectRiskFilters, today: date
    ) -> list[dict[str, Any]]:
        """Группирует счётчики одной SQL-операцией для проекта или портфеля.

        Args:
            project_ids: Уже разрешённые пользователю проекты.
            filters: Условия реестра.
            today: Дата, относительно которой считается контроль.

        Returns:
            Группы по проекту, статусу и ячейке матрицы; трактовка в сервисе.

        Raises:
            ProjectRiskRepositoryError: Ошибка агрегации.
        """
        try:
            columns = (
                ProjectRisk.project_id,
                ProjectRisk.status,
                ProjectRisk.probability,
                ProjectRisk.impact,
                ProjectRisk.risk_level,
            )
            statement = (
                select(
                    *columns,
                    func.count().label("count"),
                    func.count().filter(ProjectRisk.owner_user_id.is_(None)).label("without_owner"),
                    func.count()
                    .filter(func.btrim(ProjectRisk.mitigation_plan) == "")
                    .label("without_mitigation"),
                    func.count().filter(ProjectRisk.review_date <= today).label("due_for_review"),
                    func.count().filter(ProjectRisk.review_date < today).label("review_overdue"),
                    func.count().filter(ProjectRisk.task_id.is_not(None)).label("linked"),
                    func.count()
                    .filter(ProjectRisk.source == RiskSource.AI_SUGGESTED)
                    .label("ai_suggested"),
                    func.max(ProjectRisk.updated_at).label("latest_update"),
                )
                .where(ProjectRisk.project_id.in_(project_ids))
                .group_by(*columns)
            )
            result = await self.db_session.execute(self._filter(statement, filters))
            return [dict(row) for row in result.mappings().all()]
        except (SQLAlchemyError, Exception) as error:
            await self._fail("получить аналитику рисков", error)

    async def get_task_counts(self, project_id: int) -> dict[int, int]:
        """Считает активные риски сразу для всех задач проекта.

        Args:
            project_id: Проект запроса.

        Returns:
            Отображение task_id в количество активных рисков.

        Raises:
            ProjectRiskRepositoryError: Ошибка подсчёта.
        """
        try:
            statement = (
                select(ProjectRisk.task_id, func.count())
                .where(
                    ProjectRisk.project_id == project_id,
                    ProjectRisk.task_id.is_not(None),
                    ProjectRisk.status != RiskStatus.CLOSED,
                )
                .group_by(ProjectRisk.task_id)
            )
            return {row[0]: row[1] for row in (await self.db_session.execute(statement)).all()}
        except (SQLAlchemyError, Exception) as error:
            await self._fail("подсчитать риски задач", error)

    async def save(self, data: dict[str, Any]) -> ProjectRisk:
        """Создаёт риск внутри транзакции сервиса.

        Args:
            data: Проверенные поля вместе с вычисленным уровнем.

        Returns:
            Риск с серверными ID и временем из RETURNING.

        Raises:
            ProjectRiskRepositoryError: Ошибка записи.
        """
        try:
            risk = ProjectRisk(**data)
            self.db_session.add(risk)
            await self.db_session.flush()
            return risk
        except (SQLAlchemyError, Exception) as error:
            await self._fail("создать риск", error)

    async def update(self, risk: ProjectRisk, changes: dict[str, Any]) -> ProjectRisk:
        """Изменяет заблокированную сервисом запись в общей транзакции.

        Args:
            risk: Актуальная запись.
            changes: Проверенные изменения с пересчитанной оценкой.

        Returns:
            Обновлённый риск с серверным updated_at.

        Raises:
            ProjectRiskRepositoryError: Ошибка записи.
        """
        try:
            for name, value in changes.items():
                setattr(risk, name, value)
            await self.db_session.flush()
            return risk
        except (SQLAlchemyError, Exception) as error:
            await self._fail("изменить риск", error)

    async def delete(self, risk: ProjectRisk) -> None:
        """Удаляет риск в транзакции вместе с заданием удаления индекса.

        Args:
            risk: Риск проверенного проекта.

        Raises:
            ProjectRiskRepositoryError: Ошибка удаления.
        """
        try:
            await self.db_session.delete(risk)
            await self.db_session.flush()
        except (SQLAlchemyError, Exception) as error:
            await self._fail("удалить риск", error)

    async def clear_owner(self, *, project_id: int, user_id: int) -> list[int]:
        """Снимает назначения при исключении участника из команды.

        Args:
            project_id: Проект команды.
            user_id: Удаляемый участник.

        Returns:
            Идентификаторы изменённых рисков для обновления индекса.

        Raises:
            ProjectRiskRepositoryError: Ошибка записи.
        """
        try:
            statement = (
                update(ProjectRisk)
                .where(
                    ProjectRisk.project_id == project_id,
                    ProjectRisk.owner_user_id == user_id,
                )
                .values(owner_user_id=None, updated_at=func.now())
                .returning(ProjectRisk.id)
            )
            return list((await self.db_session.execute(statement)).scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self._fail("снять ответственного с рисков", error)

    @staticmethod
    def _filter(statement: Select, filters: ProjectRiskFilters) -> Select:
        for name in ("status", "probability", "impact", "risk_level", "owner_user_id", "task_id"):
            value = getattr(filters, name)
            if value is not None:
                statement = statement.where(getattr(ProjectRisk, name) == value)
        if filters.active_only:
            statement = statement.where(ProjectRisk.status != RiskStatus.CLOSED)
        if filters.search:
            pattern = (
                "%"
                + filters.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                + "%"
            )
            clauses = [
                ProjectRisk.title.ilike(pattern, escape="\\"),
                ProjectRisk.description.ilike(pattern, escape="\\"),
            ]
            key_number = filters.search.upper().removeprefix("RISK-")
            if key_number.isdecimal() and len(key_number) <= 10 and int(key_number) <= 2147483647:
                clauses.append(ProjectRisk.id == int(key_number))
            statement = statement.where(or_(*clauses))
        return statement

    async def _fail(self, operation: str, error: Exception) -> NoReturn:
        await self.db_session.rollback()
        logger.error("❌ Не удалось %s.", operation, exc_info=True)
        raise ProjectRiskRepositoryError(f"Не удалось {operation}.") from error
