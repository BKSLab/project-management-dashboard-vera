import logging

from src.db.models.knowledge_index_jobs import KnowledgeEntityType
from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.milestones import (
    MilestoneNotFoundError,
    MilestonesRepositoryError,
    MilestonesServiceError,
)
from src.exceptions.projects import ProjectNotFoundError, ProjectsRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.exceptions.wbs_nodes import (
    WbsNodeForeignProjectError,
    WbsNodeNotFoundError,
    WbsNodesRepositoryError,
)
from src.repositories.milestones import MilestonesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.wbs_nodes import WbsNodesRepository
from src.schemas.milestones import MilestoneSchema
from src.services.knowledge_events import KnowledgeEvents

logger = logging.getLogger(__name__)

RepositoryErrors = (
    MilestonesRepositoryError,
    ProjectsRepositoryError,
    WbsNodesRepositoryError,
    KnowledgeEventsServiceError,
    UnitOfWorkRepositoryError,
)


class MilestonesService:
    """Сервис простых проектных вех с общей транзакционной границей."""

    def __init__(
        self,
        milestones_repository: MilestonesRepository,
        projects_repository: ProjectsRepository,
        wbs_nodes_repository: WbsNodesRepository,
        unit_of_work: UnitOfWork,
        knowledge_events: KnowledgeEvents | None = None,
    ) -> None:
        self.milestones_repository = milestones_repository
        self.projects_repository = projects_repository
        self.wbs_nodes_repository = wbs_nodes_repository
        self.unit_of_work = unit_of_work
        self.knowledge_events = knowledge_events

    async def list_milestones(self, project_id: int) -> list[MilestoneSchema]:
        """Возвращает пользовательские вехи проекта."""
        try:
            await self._ensure_project_exists(project_id)
            milestones = await self.milestones_repository.get_by_project(project_id)
            return [MilestoneSchema.model_validate(item) for item in milestones]
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения вех проекта id=%s.", project_id, exc_info=True)
            raise MilestonesServiceError(str(error)) from error

    async def create_milestone(self, project_id: int, data: dict) -> MilestoneSchema:
        """Создаёт пользовательскую веху проекта."""
        try:
            await self._ensure_project_exists(project_id)
            await self._validate_wbs_node(project_id, data.get("wbs_node_id"))
            milestone = await self.milestones_repository.save({**data, "project_id": project_id})
            if self.knowledge_events is not None:
                await self.knowledge_events.upsert(
                    project_id=project_id,
                    entity_type=KnowledgeEntityType.MILESTONE,
                    entity_id=milestone.id,
                )
            await self.unit_of_work.commit()
            return MilestoneSchema.model_validate(milestone)
        except RepositoryErrors as error:
            logger.error("❌ Ошибка создания вехи проекта id=%s.", project_id, exc_info=True)
            raise MilestonesServiceError(str(error)) from error

    async def update_milestone(
        self,
        project_id: int,
        milestone_id: int,
        data: dict,
    ) -> MilestoneSchema:
        """Обновляет принадлежащую проекту веху."""
        try:
            milestone = await self._get_in_project(project_id, milestone_id)
            await self._validate_wbs_node(project_id, data.get("wbs_node_id"))
            updated = await self.milestones_repository.update(milestone, data)
            if self.knowledge_events is not None and {"title", "description_md"}.intersection(data):
                await self.knowledge_events.upsert(
                    project_id=project_id,
                    entity_type=KnowledgeEntityType.MILESTONE,
                    entity_id=milestone_id,
                )
            await self.unit_of_work.commit()
            return MilestoneSchema.model_validate(updated)
        except RepositoryErrors as error:
            logger.error("❌ Ошибка обновления вехи id=%s.", milestone_id, exc_info=True)
            raise MilestonesServiceError(str(error)) from error

    async def delete_milestone(self, project_id: int, milestone_id: int) -> None:
        """Удаляет принадлежащую проекту веху."""
        try:
            milestone = await self._get_in_project(project_id, milestone_id)
            await self.milestones_repository.delete(milestone)
            if self.knowledge_events is not None:
                await self.knowledge_events.delete(
                    project_id=project_id,
                    entity_type=KnowledgeEntityType.MILESTONE,
                    entity_id=milestone_id,
                )
            await self.unit_of_work.commit()
        except RepositoryErrors as error:
            logger.error("❌ Ошибка удаления вехи id=%s.", milestone_id, exc_info=True)
            raise MilestonesServiceError(str(error)) from error

    async def _ensure_project_exists(self, project_id: int) -> None:
        if await self.projects_repository.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id=project_id)

    async def _get_in_project(self, project_id: int, milestone_id: int):
        milestone = await self.milestones_repository.get_by_id(milestone_id)
        if milestone is None or milestone.project_id != project_id:
            raise MilestoneNotFoundError(milestone_id)
        return milestone

    async def _validate_wbs_node(self, project_id: int, node_id: int | None) -> None:
        if node_id is None:
            return
        node = await self.wbs_nodes_repository.get_by_id(node_id)
        if node is None:
            raise WbsNodeNotFoundError(node_id=node_id)
        if node.project_id != project_id:
            raise WbsNodeForeignProjectError(node_id=node_id, project_id=project_id)
