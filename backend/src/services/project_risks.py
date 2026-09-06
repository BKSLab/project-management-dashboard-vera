import logging
from datetime import date
from typing import Any

from src.db.models.knowledge_index_jobs import KnowledgeEntityType
from src.db.models.project_risks import ProjectRisk
from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.project_risks import (
    ProjectRiskNotFoundError,
    ProjectRiskOwnerMismatchError,
    ProjectRiskRepositoryError,
    ProjectRiskServiceError,
    ProjectRiskTaskMismatchError,
)
from src.exceptions.projects import ProjectsRepositoryError
from src.exceptions.tasks import TasksRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_risks import ProjectRiskRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.enums import RiskRating, RiskReasonCode, RiskStatus
from src.schemas.project_risks import (
    ProjectRiskCreateSchema,
    ProjectRiskFilters,
    ProjectRiskPageSchema,
    ProjectRiskSchema,
    ProjectRiskSummarySchema,
    ProjectRiskUpdateSchema,
    RiskMatrixCellSchema,
    RiskSignalSchema,
)
from src.services.access import AccessService
from src.services.knowledge_events import KnowledgeEvents

logger = logging.getLogger(__name__)
RepositoryErrors = (
    ProjectRiskRepositoryError,
    ProjectsRepositoryError,
    TasksRepositoryError,
    UnitOfWorkRepositoryError,
    KnowledgeEventsServiceError,
)


def calculate_risk_level(probability: RiskRating, impact: RiskRating) -> RiskRating:
    """Применяет утверждённую матрицу 3×3 без числовой псевдоточности."""
    matrix = {
        RiskRating.LOW: {
            RiskRating.LOW: RiskRating.LOW,
            RiskRating.MEDIUM: RiskRating.LOW,
            RiskRating.HIGH: RiskRating.MEDIUM,
        },
        RiskRating.MEDIUM: {
            RiskRating.LOW: RiskRating.LOW,
            RiskRating.MEDIUM: RiskRating.MEDIUM,
            RiskRating.HIGH: RiskRating.HIGH,
        },
        RiskRating.HIGH: {
            RiskRating.LOW: RiskRating.MEDIUM,
            RiskRating.MEDIUM: RiskRating.HIGH,
            RiskRating.HIGH: RiskRating.HIGH,
        },
    }
    return matrix[probability][impact]


def build_risk_summary(groups: list[dict[str, Any]]) -> ProjectRiskSummarySchema:
    """Трактует SQL-агрегаты одинаково для реестра, аналитики и портфеля."""
    summary = ProjectRiskSummarySchema()
    cells = {(probability, impact): 0 for probability in RiskRating for impact in RiskRating}
    high_open = 0
    for row in groups:
        count = row["count"]
        state = RiskStatus(row["status"])
        summary.total_risks += count
        field = f"{state.value.lower()}_risks"
        setattr(summary, field, getattr(summary, field) + count)
        summary.risks_linked_to_tasks += row["linked"]
        summary.ai_suggested_risks += row["ai_suggested"]
        cells[(row["probability"], row["impact"])] += count
        updated = row["latest_update"]
        if updated and (summary.latest_update is None or updated > summary.latest_update):
            summary.latest_update = updated
        if state == RiskStatus.CLOSED:
            continue
        summary.active_risks += count
        level_field = f"{RiskRating(row['risk_level']).value.lower()}_risks"
        setattr(summary, level_field, getattr(summary, level_field) + count)
        summary.risks_without_owner += row["without_owner"]
        summary.risks_without_mitigation += row["without_mitigation"]
        summary.risks_due_for_review += row["due_for_review"]
        summary.risks_review_overdue += row["review_overdue"]
        if (
            state in {RiskStatus.OPEN, RiskStatus.MITIGATING}
            and row["risk_level"] == RiskRating.HIGH
        ):
            high_open += count
    summary.matrix = [
        RiskMatrixCellSchema(probability=p, impact=i, count=count)
        for (p, i), count in cells.items()
    ]
    summary.signals = [
        RiskSignalSchema(code=code, count=count)
        for code, count in (
            (RiskReasonCode.HIGH_OPEN_RISK, high_open),
            (RiskReasonCode.RISK_REVIEW_OVERDUE, summary.risks_review_overdue),
            (RiskReasonCode.RISK_WITHOUT_OWNER, summary.risks_without_owner),
            (RiskReasonCode.RISK_WITHOUT_MITIGATION, summary.risks_without_mitigation),
            (RiskReasonCode.RISK_OCCURRED, summary.occurred_risks),
        )
        if count
    ]
    return summary


class ProjectRiskService:
    """Управляет рисками проекта, их инвариантами и индексированием."""

    def __init__(
        self,
        *,
        risks_repository: ProjectRiskRepository,
        tasks_repository: TasksRepository,
        members_repository: ProjectMembersRepository,
        access_service: AccessService,
        knowledge_events: KnowledgeEvents,
        unit_of_work: UnitOfWork,
        projects_repository: ProjectsRepository,
    ) -> None:
        self.risks_repository = risks_repository
        self.tasks_repository = tasks_repository
        self.members_repository = members_repository
        self.access_service = access_service
        self.knowledge_events = knowledge_events
        self.unit_of_work = unit_of_work
        self.projects_repository = projects_repository

    async def list_risks(
        self,
        *,
        project_id: int,
        user_id: int,
        filters: ProjectRiskFilters,
        page: int = 1,
        page_size: int = 25,
    ) -> ProjectRiskPageSchema:
        """Возвращает страницу реестра доступного проекта.

        Args:
            project_id: Проект реестра.
            user_id: Пользователь текущего запроса.
            filters: Условия поиска.
            page: Номер страницы от единицы.
            page_size: Размер страницы до 100.

        Returns:
            Страница и общее число совпадений.

        Raises:
            AccessServiceError: Проект недоступен.
            ProjectRiskServiceError: Ошибка чтения.
        """
        await self.access_service.ensure_project_access(project_id=project_id, user_id=user_id)
        try:
            total = await self.risks_repository.get_count(project_id=project_id, filters=filters)
            risks = await self.risks_repository.get_page(
                project_id=project_id, filters=filters, page=page, page_size=page_size
            )
            return ProjectRiskPageSchema(
                total=total,
                page=page,
                page_size=page_size,
                items=[ProjectRiskSchema.model_validate(risk) for risk in risks],
            )
        except RepositoryErrors as error:
            logger.error("❌ Ошибка чтения реестра проекта id=%s.", project_id, exc_info=True)
            raise ProjectRiskServiceError(str(error)) from error

    async def get_risk(self, *, project_id: int, risk_id: int, user_id: int) -> ProjectRiskSchema:
        """Возвращает риск в контексте доступного проекта.

        Args:
            project_id: Проект запроса.
            risk_id: Идентификатор риска.
            user_id: Пользователь запроса.

        Returns:
            Сохранённый риск.

        Raises:
            AccessServiceError: Проект недоступен.
            ProjectRiskNotFoundError: Риска в проекте нет.
            ProjectRiskServiceError: Ошибка чтения.
        """
        await self.access_service.ensure_project_access(project_id=project_id, user_id=user_id)
        try:
            return ProjectRiskSchema.model_validate(await self._get_in_project(project_id, risk_id))
        except RepositoryErrors as error:
            logger.error("❌ Ошибка чтения риска id=%s.", risk_id, exc_info=True)
            raise ProjectRiskServiceError(str(error)) from error

    async def create_risk(
        self, *, project_id: int, user_id: int, data: ProjectRiskCreateSchema
    ) -> ProjectRiskSchema:
        """Регистрирует принятое человеком событие и задание индексации атомарно.

        Args:
            project_id: Проект нового риска.
            user_id: Пользователь, принявший решение о создании.
            data: Подтверждённые поля формы или MCP-запроса.

        Returns:
            Риск с вычисленным уровнем.

        Raises:
            AccessServiceError: Проект недоступен.
            ProjectRiskTaskMismatchError: Задача другого проекта.
            ProjectRiskOwnerMismatchError: Ответственный вне команды.
            ProjectRiskServiceError: Ошибка записи или outbox.
        """
        await self.access_service.ensure_project_access(project_id=project_id, user_id=user_id)
        try:
            values = data.model_dump()
            await self._validate_links(project_id, values)
            risk = await self.risks_repository.save(
                {
                    **values,
                    "project_id": project_id,
                    "risk_level": calculate_risk_level(data.probability, data.impact),
                }
            )
            await self.knowledge_events.upsert(
                project_id=project_id, entity_type=KnowledgeEntityType.RISK, entity_id=risk.id
            )
            result = ProjectRiskSchema.model_validate(risk)
            await self.projects_repository.touch(project_id)
            await self.unit_of_work.commit()
            return result
        except RepositoryErrors as error:
            await self.unit_of_work.rollback()
            logger.error("❌ Ошибка создания риска проекта id=%s.", project_id, exc_info=True)
            raise ProjectRiskServiceError(str(error)) from error

    async def update_risk(
        self, *, project_id: int, risk_id: int, user_id: int, data: ProjectRiskUpdateSchema
    ) -> ProjectRiskSchema:
        """Изменяет риск, сохраняя согласованность вероятности, влияния и уровня.

        Args:
            project_id: Проект риска.
            risk_id: Идентификатор риска.
            user_id: Пользователь запроса.
            data: Частичное изменение; источник сохраняется.

        Returns:
            Обновлённый риск.

        Raises:
            AccessServiceError: Проект недоступен.
            ProjectRiskNotFoundError: Риска в проекте нет.
            ProjectRiskTaskMismatchError: Задача другого проекта.
            ProjectRiskOwnerMismatchError: Ответственный вне команды.
            ProjectRiskServiceError: Ошибка записи.
        """
        await self.access_service.ensure_project_access(project_id=project_id, user_id=user_id)
        try:
            changes = data.model_dump(exclude_unset=True)
            await self._validate_links(project_id, changes)
            risk = await self._get_in_project(project_id, risk_id, for_update=True)
            changes["risk_level"] = calculate_risk_level(
                changes.get("probability", risk.probability), changes.get("impact", risk.impact)
            )
            updated = await self.risks_repository.update(risk, changes)
            await self.knowledge_events.upsert(
                project_id=project_id, entity_type=KnowledgeEntityType.RISK, entity_id=risk_id
            )
            result = ProjectRiskSchema.model_validate(updated)
            await self.projects_repository.touch(project_id)
            await self.unit_of_work.commit()
            return result
        except RepositoryErrors as error:
            await self.unit_of_work.rollback()
            logger.error("❌ Ошибка изменения риска id=%s.", risk_id, exc_info=True)
            raise ProjectRiskServiceError(str(error)) from error

    async def delete_risk(self, *, project_id: int, risk_id: int, user_id: int) -> None:
        """Удаляет риск и ставит удаление semantic-представления в outbox.

        Args:
            project_id: Проект риска.
            risk_id: Идентификатор риска.
            user_id: Пользователь запроса.

        Raises:
            AccessServiceError: Проект недоступен.
            ProjectRiskNotFoundError: Риска в проекте нет.
            ProjectRiskServiceError: Ошибка удаления.
        """
        await self.access_service.ensure_project_access(project_id=project_id, user_id=user_id)
        try:
            risk = await self._get_in_project(project_id, risk_id, for_update=True)
            await self.risks_repository.delete(risk)
            await self.knowledge_events.delete(
                project_id=project_id, entity_type=KnowledgeEntityType.RISK, entity_id=risk_id
            )
            await self.projects_repository.touch(project_id)
            await self.unit_of_work.commit()
        except RepositoryErrors as error:
            await self.unit_of_work.rollback()
            logger.error("❌ Ошибка удаления риска id=%s.", risk_id, exc_info=True)
            raise ProjectRiskServiceError(str(error)) from error

    async def get_summary(
        self,
        *,
        project_id: int,
        user_id: int,
        filters: ProjectRiskFilters,
        today: date | None = None,
    ) -> ProjectRiskSummarySchema:
        """Собирает матрицу и проверяемые сигналы по всему набору рисков.

        Args:
            project_id: Проект реестра.
            user_id: Пользователь запроса.
            filters: Условия, независимые от номера страницы.
            today: Дата контроля, по умолчанию текущая дата сервера.

        Returns:
            Счётчики, девять ячеек матрицы и причины внимания.

        Raises:
            AccessServiceError: Проект недоступен.
            ProjectRiskServiceError: Ошибка агрегации.
        """
        await self.access_service.ensure_project_access(project_id=project_id, user_id=user_id)
        try:
            groups = await self.risks_repository.get_aggregates(
                project_ids={project_id}, filters=filters, today=today or date.today()
            )
            return build_risk_summary(groups)
        except RepositoryErrors as error:
            logger.error("❌ Ошибка аналитики рисков проекта id=%s.", project_id, exc_info=True)
            raise ProjectRiskServiceError(str(error)) from error

    async def get_task_counts(self, *, project_id: int, user_id: int) -> dict[int, int]:
        """Возвращает индикаторы активных рисков для всех Kanban cards одним запросом.

        Args:
            project_id: Проект доски.
            user_id: Пользователь запроса.

        Returns:
            Количество рисков каждой связанной задачи.

        Raises:
            AccessServiceError: Проект недоступен.
            ProjectRiskServiceError: Ошибка чтения.
        """
        await self.access_service.ensure_project_access(project_id=project_id, user_id=user_id)
        try:
            return await self.risks_repository.get_task_counts(project_id)
        except RepositoryErrors as error:
            logger.error(
                "❌ Ошибка подсчёта рисков задач проекта id=%s.", project_id, exc_info=True
            )
            raise ProjectRiskServiceError(str(error)) from error

    # Блок проверки инвариантов.

    async def _get_in_project(
        self, project_id: int, risk_id: int, *, for_update: bool = False
    ) -> ProjectRisk:
        risk = await self.risks_repository.get_by_id(
            project_id=project_id, risk_id=risk_id, for_update=for_update
        )
        if risk is None or risk.project_id != project_id:
            raise ProjectRiskNotFoundError(risk_id)
        return risk

    async def _validate_links(self, project_id: int, values: dict[str, Any]) -> None:
        task_id = values.get("task_id")
        if task_id is not None:
            task = await self.tasks_repository.get_by_id(task_id)
            if task is None or task.project_id != project_id:
                raise ProjectRiskTaskMismatchError(task_id)
        owner_id = values.get("owner_user_id")
        if (
            owner_id is not None
            and await self.members_repository.get(project_id, owner_id, for_update=True) is None
        ):
            raise ProjectRiskOwnerMismatchError(owner_id)
