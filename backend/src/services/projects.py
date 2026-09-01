import logging
from datetime import date, timedelta

from src.db.models.project_members import ProjectRole
from src.db.models.project_stages import ProjectStage
from src.db.models.tasks import Task
from src.exceptions.project_stages import ProjectStagesRepositoryError
from src.exceptions.projects import (
    ProjectKeyAlreadyExistsRepositoryError,
    ProjectKeyConflictError,
    ProjectNotFoundError,
    ProjectsRepositoryError,
    ProjectsServiceError,
)
from src.exceptions.task_attachments import TaskAttachmentStorageError
from src.exceptions.tasks import TasksRepositoryError
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.schemas.projects import ProjectSchema, ProjectStatsSchema, StageBreakdownSchema
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)

DUE_SOON_DAYS = 7

DEFAULT_STAGES: tuple[dict, ...] = (
    {"name": "Бэклог", "color": "#7d8793", "is_done_stage": False},
    {"name": "В работе", "color": "#58a6ff", "is_done_stage": False},
    {"name": "Ревью", "color": "#a371f7", "is_done_stage": False},
    {"name": "Тестирование", "color": "#d29922", "is_done_stage": False},
    {"name": "Готово", "color": "#3fb950", "is_done_stage": True},
)

RepositoryErrors = (
    ProjectsRepositoryError,
    ProjectStagesRepositoryError,
    TasksRepositoryError,
)


class ProjectsService:
    """Сервис сценариев работы с проектами."""

    def __init__(
        self,
        projects_repository: ProjectsRepository,
        members_repository: ProjectMembersRepository,
        stages_repository: ProjectStagesRepository,
        tasks_repository: TasksRepository,
        attachment_storage: TaskAttachmentStorage | None = None,
    ):
        self.projects_repository = projects_repository
        self.members_repository = members_repository
        self.stages_repository = stages_repository
        self.tasks_repository = tasks_repository
        self.attachment_storage = attachment_storage

    async def get_project_list(self, user_id: int) -> list[ProjectSchema]:
        """Возвращает проекты, доступные пользователю.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Список проектов пользователя в порядке отображения.

        Raises:
            ProjectsServiceError: Если получить проекты не удалось.
        """
        try:
            allowed_ids = await self.members_repository.get_project_ids_for_user(user_id=user_id)
            projects = await self.projects_repository.get_all()
            return [
                ProjectSchema.model_validate(project)
                for project in projects
                if project.id in allowed_ids
            ]
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения списка проектов.", exc_info=True)
            raise ProjectsServiceError(str(error)) from error

    async def get_project(self, project_id: int) -> ProjectSchema:
        """Возвращает проект по идентификатору.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Карточка проекта.

        Raises:
            ProjectNotFoundError: Если проект не найден или недоступен.
            ProjectsServiceError: Если получить проект не удалось.
        """
        try:
            project = await self.projects_repository.get_by_id(project_id=project_id)
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            return ProjectSchema.model_validate(project)
        except ProjectNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения проекта id=%s.", project_id, exc_info=True)
            raise ProjectsServiceError(str(error)) from error

    async def create_project(self, data: dict, owner_id: int) -> ProjectSchema:
        """Создаёт проект, делает автора владельцем и добавляет стадии.

        Владелец сразу получает участие с ролью OWNER, поэтому доступ к проекту
        проверяется одинаково и для него, и для будущих приглашённых.

        Args:
            data: Поля нового проекта.
            owner_id: Идентификатор пользователя-владельца.

        Returns:
            Созданный проект.

        Raises:
            ProjectKeyConflictError: Если код проекта уже занят.
            ProjectsServiceError: Если создать проект не удалось.
        """
        try:
            order_index = await self.projects_repository.get_max_order_index() + 1
            project = await self.projects_repository.save(
                data={**data, "owner_id": owner_id, "order_index": order_index}
            )
            await self.members_repository.save(
                data={
                    "project_id": project.id,
                    "user_id": owner_id,
                    "role": ProjectRole.OWNER,
                }
            )
            await self.stages_repository.save_many(
                items=[
                    {**stage, "project_id": project.id, "order_index": index}
                    for index, stage in enumerate(DEFAULT_STAGES)
                ]
            )
            logger.info("✅ Проект %s создан со стадиями по умолчанию.", project.key)
            return ProjectSchema.model_validate(project)
        except ProjectKeyAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт кода проекта %s.", error.key)
            raise ProjectKeyConflictError(key=error.key) from error
        except RepositoryErrors as error:
            logger.error("❌ Ошибка создания проекта.", exc_info=True)
            raise ProjectsServiceError(str(error)) from error

    async def update_project(self, project_id: int, data: dict) -> ProjectSchema:
        """Обновляет поля проекта.

        Args:
            project_id: Идентификатор проекта.
            data: Изменяемые поля проекта.

        Returns:
            Обновлённый проект.

        Raises:
            ProjectNotFoundError: Если проект не найден или недоступен.
            ProjectKeyConflictError: Если новый код проекта уже занят.
            ProjectsServiceError: Если обновить проект не удалось.
        """
        try:
            project = await self.projects_repository.get_by_id(project_id=project_id)
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            updated = await self.projects_repository.update(project=project, data=data)
            return ProjectSchema.model_validate(updated)
        except ProjectNotFoundError:
            raise
        except ProjectKeyAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт кода проекта %s.", error.key)
            raise ProjectKeyConflictError(key=error.key) from error
        except RepositoryErrors as error:
            logger.error("❌ Ошибка обновления проекта id=%s.", project_id, exc_info=True)
            raise ProjectsServiceError(str(error)) from error

    async def delete_project(self, project_id: int) -> None:
        """Удаляет проект вместе с задачами, стадиями, структурой и документами.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            ProjectNotFoundError: Если проект не найден.
            ProjectsServiceError: Если удалить проект не удалось.
        """
        try:
            project = await self.projects_repository.get_by_id(project_id=project_id)
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            tasks = await self.tasks_repository.get_by_project(project_id=project_id)
            task_ids = [task.id for task in tasks]
            await self.projects_repository.delete(project=project)
            await self._cleanup_task_files(task_ids=task_ids)
            logger.info("✅ Проект id=%s удалён вместе с %s задачами.", project_id, len(task_ids))
        except ProjectNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка удаления проекта id=%s.", project_id, exc_info=True)
            raise ProjectsServiceError(str(error)) from error

    async def get_project_stats(self, project_id: int) -> ProjectStatsSchema:
        """Собирает показатели одного проекта.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Показатели проекта с распределением по стадиям.

        Raises:
            ProjectNotFoundError: Если проект не найден или недоступен.
            ProjectsServiceError: Если собрать показатели не удалось.
        """
        try:
            project = await self.projects_repository.get_by_id(project_id=project_id)
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            stages = await self.stages_repository.get_by_project(project_id=project_id)
            tasks = await self.tasks_repository.get_by_project(project_id=project_id)
            return build_project_stats(project_id=project_id, stages=stages, tasks=tasks)
        except ProjectNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка расчёта показателей проекта id=%s.", project_id, exc_info=True)
            raise ProjectsServiceError(str(error)) from error

    async def _cleanup_task_files(self, task_ids: list[int]) -> None:
        """Best-effort очищает каталоги файлов удалённых задач."""
        if self.attachment_storage is None:
            return
        for task_id in task_ids:
            try:
                await self.attachment_storage.delete_task_directory(task_id)
            except TaskAttachmentStorageError:
                logger.warning(
                    "⚠️ Не удалось очистить каталог файлов удалённой задачи id=%s.",
                    task_id,
                    exc_info=True,
                )


def build_project_stats(
    project_id: int,
    stages: list[ProjectStage],
    tasks: list[Task],
    today: date | None = None,
) -> ProjectStatsSchema:
    """Считает показатели проекта из его стадий и задач.

    Args:
        project_id: Идентификатор проекта.
        stages: Стадии проекта в порядке отображения.
        tasks: Задачи проекта.
        today: Дата, относительно которой считается просрочка.

    Returns:
        Показатели проекта с распределением по стадиям.
    """
    current_day = today or date.today()
    soon_until = current_day + timedelta(days=DUE_SOON_DAYS)
    done_stage_ids = {stage.id for stage in stages if stage.is_done_stage}
    backlog_stage_id = stages[0].id if stages else None

    counts_by_stage: dict[int, int] = {stage.id: 0 for stage in stages}
    done_tasks = 0
    in_progress_tasks = 0
    overdue_tasks = 0
    due_soon_tasks = 0
    unassigned_tasks = 0
    next_due_date: date | None = None

    for task in tasks:
        counts_by_stage[task.stage_id] = counts_by_stage.get(task.stage_id, 0) + 1
        if task.wbs_node_id is None:
            unassigned_tasks += 1

        is_done = task.stage_id in done_stage_ids
        if is_done:
            done_tasks += 1
            continue
        if task.stage_id != backlog_stage_id:
            in_progress_tasks += 1
        if task.due_date is None:
            continue
        if task.due_date < current_day:
            overdue_tasks += 1
            continue
        if task.due_date <= soon_until:
            due_soon_tasks += 1
        if next_due_date is None or task.due_date < next_due_date:
            next_due_date = task.due_date

    total_tasks = len(tasks)
    return ProjectStatsSchema(
        project_id=project_id,
        total_tasks=total_tasks,
        done_tasks=done_tasks,
        in_progress_tasks=in_progress_tasks,
        overdue_tasks=overdue_tasks,
        due_soon_tasks=due_soon_tasks,
        unassigned_tasks=unassigned_tasks,
        completion_rate=(done_tasks / total_tasks) if total_tasks else 0.0,
        next_due_date=next_due_date,
        stage_breakdown=[
            StageBreakdownSchema(
                stage_id=stage.id,
                stage_name=stage.name,
                color=stage.color,
                is_done_stage=stage.is_done_stage,
                tasks_count=counts_by_stage.get(stage.id, 0),
            )
            for stage in stages
        ],
    )
