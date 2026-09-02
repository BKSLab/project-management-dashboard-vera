import logging
from collections import defaultdict, deque

from src.exceptions.projects import ProjectNotFoundError, ProjectsRepositoryError
from src.exceptions.task_dependencies import (
    TaskDependenciesRepositoryError,
    TaskDependenciesServiceError,
    TaskDependencyAlreadyExistsError,
    TaskDependencyAlreadyExistsRepositoryError,
    TaskDependencyCycleError,
    TaskDependencyForeignProjectError,
    TaskDependencyNotFoundError,
    TaskDependencySelfReferenceError,
)
from src.exceptions.tasks import TaskNotFoundError, TasksRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.repositories.projects import ProjectsRepository
from src.repositories.task_dependencies import TaskDependenciesRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.task_dependencies import TaskDependencySchema

logger = logging.getLogger(__name__)

RepositoryErrors = (
    ProjectsRepositoryError,
    TaskDependenciesRepositoryError,
    TasksRepositoryError,
    UnitOfWorkRepositoryError,
)


class TaskDependenciesService:
    """Сервис ациклического графа зависимостей задач проекта."""

    def __init__(
        self,
        dependencies_repository: TaskDependenciesRepository,
        projects_repository: ProjectsRepository,
        tasks_repository: TasksRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.dependencies_repository = dependencies_repository
        self.projects_repository = projects_repository
        self.tasks_repository = tasks_repository
        self.unit_of_work = unit_of_work

    async def list_dependencies(self, project_id: int) -> list[TaskDependencySchema]:
        """Возвращает граф доступного проекта."""
        try:
            await self._ensure_project_exists(project_id)
            dependencies = await self.dependencies_repository.get_by_project(project_id)
            return [TaskDependencySchema.model_validate(item) for item in dependencies]
        except ProjectNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error(
                "❌ Ошибка получения зависимостей проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise TaskDependenciesServiceError(str(error)) from error

    async def create_dependency(self, project_id: int, data: dict) -> TaskDependencySchema:
        """Создаёт связь после проверки принадлежности и циклов."""
        predecessor_id = data["predecessor_task_id"]
        successor_id = data["successor_task_id"]
        if predecessor_id == successor_id:
            raise TaskDependencySelfReferenceError()
        try:
            await self._ensure_project_exists(project_id)
            tasks = {
                task.id: task
                for task in await self.tasks_repository.get_by_ids({predecessor_id, successor_id})
            }
            for task_id in (predecessor_id, successor_id):
                if task_id not in tasks:
                    raise TaskNotFoundError(task_id)
                if tasks[task_id].project_id != project_id:
                    raise TaskDependencyForeignProjectError()
            dependencies = await self.dependencies_repository.get_by_project(project_id)
            if any(
                item.predecessor_task_id == predecessor_id
                and item.successor_task_id == successor_id
                for item in dependencies
            ):
                raise TaskDependencyAlreadyExistsError()
            if _would_create_cycle(
                dependencies,
                predecessor_id=predecessor_id,
                successor_id=successor_id,
            ):
                raise TaskDependencyCycleError()
            dependency = await self.dependencies_repository.save({**data, "project_id": project_id})
            dependencies_after_insert = await self.dependencies_repository.get_by_project(
                project_id
            )
            if _would_create_cycle(
                dependencies_after_insert,
                predecessor_id=predecessor_id,
                successor_id=successor_id,
            ):
                await self.unit_of_work.rollback()
                raise TaskDependencyCycleError()
            await self.unit_of_work.commit()
            return TaskDependencySchema.model_validate(dependency)
        except (
            ProjectNotFoundError,
            TaskNotFoundError,
            TaskDependencyAlreadyExistsError,
            TaskDependencyCycleError,
            TaskDependencyForeignProjectError,
        ):
            raise
        except TaskDependencyAlreadyExistsRepositoryError as error:
            raise TaskDependencyAlreadyExistsError() from error
        except RepositoryErrors as error:
            logger.error(
                "❌ Ошибка создания зависимости проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise TaskDependenciesServiceError(str(error)) from error

    async def delete_dependency(self, project_id: int, dependency_id: int) -> None:
        """Удаляет принадлежащую проекту связь."""
        try:
            dependency = await self.dependencies_repository.get_by_id(dependency_id)
            if dependency is None or dependency.project_id != project_id:
                raise TaskDependencyNotFoundError(dependency_id)
            await self.dependencies_repository.delete(dependency)
            await self.unit_of_work.commit()
        except TaskDependencyNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error(
                "❌ Ошибка удаления зависимости id=%s.",
                dependency_id,
                exc_info=True,
            )
            raise TaskDependenciesServiceError(str(error)) from error

    async def _ensure_project_exists(self, project_id: int) -> None:
        if await self.projects_repository.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id=project_id)


def _would_create_cycle(
    dependencies,
    *,
    predecessor_id: int,
    successor_id: int,
) -> bool:
    """Проверяет, существует ли уже путь от successor к predecessor."""
    successors: dict[int, list[int]] = defaultdict(list)
    for dependency in dependencies:
        successors[dependency.predecessor_task_id].append(dependency.successor_task_id)
    queue = deque([successor_id])
    visited: set[int] = set()
    while queue:
        task_id = queue.popleft()
        if task_id == predecessor_id:
            return True
        if task_id in visited:
            continue
        visited.add(task_id)
        queue.extend(successors[task_id])
    return False
