import logging

from src.db.models.task_activity import TaskActivityEventType
from src.db.models.tasks import Task
from src.exceptions.project_stages import (
    ProjectStageForeignProjectError,
    ProjectStageNotFoundError,
    ProjectStagesRepositoryError,
)
from src.exceptions.projects import ProjectNotFoundError, ProjectsRepositoryError
from src.exceptions.task_activity import TaskActivityRepositoryError
from src.exceptions.task_attachments import TaskAttachmentStorageError
from src.exceptions.task_comments import TaskCommentsRepositoryError
from src.exceptions.tasks import (
    TaskNotFoundError,
    TaskNumberAllocationError,
    TaskNumberAlreadyExistsRepositoryError,
    TasksRepositoryError,
    TasksServiceError,
)
from src.exceptions.wbs_nodes import (
    WbsNodeForeignProjectError,
    WbsNodeNotFoundError,
    WbsNodesRepositoryError,
)
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.schemas.tasks import TaskSchema
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)

POSITION_STEP = 1000.0
NUMBER_ALLOCATION_ATTEMPTS = 5

RepositoryErrors = (
    ProjectsRepositoryError,
    ProjectStagesRepositoryError,
    TasksRepositoryError,
    TaskActivityRepositoryError,
    TaskCommentsRepositoryError,
    WbsNodesRepositoryError,
)


class TasksService:
    """Сервис сценариев работы с задачами проекта."""

    def __init__(
        self,
        tasks_repository: TasksRepository,
        projects_repository: ProjectsRepository,
        stages_repository: ProjectStagesRepository,
        comments_repository: TaskCommentsRepository,
        activity_repository: TaskActivityRepository,
        wbs_nodes_repository: WbsNodesRepository,
        attachment_storage: TaskAttachmentStorage | None = None,
    ):
        self.tasks_repository = tasks_repository
        self.projects_repository = projects_repository
        self.stages_repository = stages_repository
        self.comments_repository = comments_repository
        self.activity_repository = activity_repository
        self.wbs_nodes_repository = wbs_nodes_repository
        self.attachment_storage = attachment_storage

    async def get_task_list(
        self,
        project_id: int,
        stage_id: int | None = None,
        search: str | None = None,
    ) -> list[TaskSchema]:
        """Возвращает задачи проекта с контекстом комментариев и поиска.

        Args:
            project_id: Идентификатор проекта.
            stage_id: Опциональный фильтр по стадии.
            search: Опциональный поисковый запрос.

        Returns:
            Карточки задач в сохранённом порядке.

        Raises:
            ProjectNotFoundError: Если проект не найден.
            TasksServiceError: Если получить задачи не удалось.
        """
        try:
            project = await self._get_project(project_id=project_id)
            search_text = search.strip() if search else ""
            matching_ids = (
                await self._search_task_ids(project_id=project_id, search=search_text)
                if search_text
                else None
            )
            tasks = await self.tasks_repository.get_by_project(
                project_id=project_id,
                stage_id=stage_id,
                task_ids=matching_ids,
            )
            task_ids = [task.id for task in tasks]
            comment_context = await self._build_comment_context(task_ids=task_ids)
            task_highlights = (
                await self.tasks_repository.get_search_highlights(
                    task_ids=task_ids,
                    search=search_text,
                )
                if search_text
                else {}
            )
            comment_highlights = (
                await self.comments_repository.get_search_highlights(
                    task_ids=task_ids,
                    search=search_text,
                )
                if search_text
                else {}
            )

            result: list[TaskSchema] = []
            for task in tasks:
                schema = to_task_schema(task=task, project_key=project.key)
                schema.comments_count, schema.last_comment = comment_context.get(task.id, (0, None))
                highlight = task_highlights.get(task.id) or comment_highlights.get(task.id)
                for field, value in (highlight or {}).items():
                    setattr(schema, field, value)
                result.append(schema)
            return result
        except ProjectNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения задач проекта id=%s.", project_id, exc_info=True)
            raise TasksServiceError(str(error)) from error

    async def get_task(self, task_id: int) -> TaskSchema:
        """Возвращает задачу по идентификатору.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            Карточка задачи.

        Raises:
            TaskNotFoundError: Если задача не найдена.
            TasksServiceError: Если получить задачу не удалось.
        """
        try:
            task = await self._get_task(task_id=task_id)
            project = await self._get_project(project_id=task.project_id)
            schema = to_task_schema(task=task, project_key=project.key)
            comment_context = await self._build_comment_context(task_ids=[task.id])
            schema.comments_count, schema.last_comment = comment_context.get(task.id, (0, None))
            return schema
        except (TaskNotFoundError, ProjectNotFoundError):
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения задачи id=%s.", task_id, exc_info=True)
            raise TasksServiceError(str(error)) from error

    async def create_task(self, project_id: int, data: dict) -> TaskSchema:
        """Создаёт задачу в проекте и выдаёт ей сквозной номер.

        Args:
            project_id: Идентификатор проекта.
            data: Поля создаваемой задачи.

        Returns:
            Созданная задача.

        Raises:
            ProjectNotFoundError: Если проект не найден.
            ProjectStageNotFoundError: Если у проекта нет стадий или стадия не найдена.
            WbsNodeNotFoundError: Если указанный раздел ИСР не найден.
            TasksServiceError: Если создать задачу не удалось.
        """
        try:
            project = await self._get_project(project_id=project_id)
            payload = dict(data)
            payload["project_id"] = project_id
            payload["stage_id"] = await self._resolve_stage_id(
                project_id=project_id,
                stage_id=payload.get("stage_id"),
            )
            wbs_node_id = payload.get("wbs_node_id")
            if wbs_node_id is not None:
                await self._ensure_wbs_node_in_project(
                    node_id=wbs_node_id,
                    project_id=project_id,
                )
            max_position = await self.tasks_repository.get_max_position_by_stage(
                stage_id=payload["stage_id"]
            )
            payload["position"] = max_position + POSITION_STEP

            task = await self._save_with_number(project_id=project_id, payload=payload)
            logger.info("✅ Задача %s-%s создана.", project.key, task.number)
            return to_task_schema(task=task, project_key=project.key)
        except (
            ProjectNotFoundError,
            ProjectStageNotFoundError,
            ProjectStageForeignProjectError,
            WbsNodeNotFoundError,
            WbsNodeForeignProjectError,
            TaskNumberAllocationError,
        ):
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка создания задачи в проекте id=%s.", project_id, exc_info=True)
            raise TasksServiceError(str(error)) from error

    async def update_task(self, task_id: int, data: dict) -> TaskSchema:
        """Обновляет задачу и фиксирует значимые изменения в истории.

        Args:
            task_id: Идентификатор задачи.
            data: Изменяемые поля задачи.

        Returns:
            Обновлённая задача.

        Raises:
            TaskNotFoundError: Если задача не найдена.
            TasksServiceError: Если обновить задачу не удалось.
        """
        try:
            task = await self._get_task(task_id=task_id)
            project = await self._get_project(project_id=task.project_id)
            await self._record_field_changes(task=task, data=data)
            updated = await self.tasks_repository.update(task=task, data=data)
            return to_task_schema(task=updated, project_key=project.key)
        except (TaskNotFoundError, ProjectNotFoundError):
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка обновления задачи id=%s.", task_id, exc_info=True)
            raise TasksServiceError(str(error)) from error

    async def move_task(
        self,
        task_id: int,
        stage_id: int,
        position: float | None = None,
    ) -> TaskSchema:
        """Перемещает задачу по доске и фиксирует смену стадии.

        Args:
            task_id: Идентификатор задачи.
            stage_id: Идентификатор целевой стадии.
            position: Позиция внутри стадии; без значения задача встаёт в конец.

        Returns:
            Перемещённая задача.

        Raises:
            TaskNotFoundError: Если задача не найдена.
            ProjectStageNotFoundError: Если целевая стадия не найдена.
            ProjectStageForeignProjectError: Если стадия принадлежит другому проекту.
            TasksServiceError: Если переместить задачу не удалось.
        """
        try:
            task = await self._get_task(task_id=task_id)
            project = await self._get_project(project_id=task.project_id)
            target_stage = await self.stages_repository.get_by_id(stage_id=stage_id)
            if target_stage is None:
                raise ProjectStageNotFoundError(stage_id=stage_id)
            if target_stage.project_id != task.project_id:
                raise ProjectStageForeignProjectError(
                    stage_id=stage_id,
                    project_id=task.project_id,
                )
            if task.stage_id == stage_id and position is None:
                return to_task_schema(task=task, project_key=project.key)

            target_position = position
            if target_position is None:
                max_position = await self.tasks_repository.get_max_position_by_stage(
                    stage_id=stage_id
                )
                target_position = max_position + POSITION_STEP
            if task.stage_id != stage_id:
                current_stage = await self.stages_repository.get_by_id(stage_id=task.stage_id)
                await self.activity_repository.save(
                    task_id=task_id,
                    event_type=TaskActivityEventType.STAGE_CHANGED,
                    from_value=current_stage.name if current_stage else None,
                    to_value=target_stage.name,
                )
            updated = await self.tasks_repository.update(
                task=task,
                data={"stage_id": stage_id, "position": target_position},
            )
            return to_task_schema(task=updated, project_key=project.key)
        except (
            TaskNotFoundError,
            ProjectNotFoundError,
            ProjectStageNotFoundError,
            ProjectStageForeignProjectError,
        ):
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка перемещения задачи id=%s.", task_id, exc_info=True)
            raise TasksServiceError(str(error)) from error

    async def delete_task(self, task_id: int) -> None:
        """Удаляет задачу вместе с её файлами.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            TaskNotFoundError: Если задача не найдена.
            TasksServiceError: Если удалить задачу не удалось.
        """
        try:
            task = await self._get_task(task_id=task_id)
            await self.tasks_repository.delete(task=task)
            await self._cleanup_deleted_task_files(task_id=task_id)
        except TaskNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка удаления задачи id=%s.", task_id, exc_info=True)
            raise TasksServiceError(str(error)) from error

    async def _get_task(self, task_id: int) -> Task:
        """Возвращает задачу или поднимает доменную ошибку."""
        task = await self.tasks_repository.get_by_id(task_id=task_id)
        if task is None:
            raise TaskNotFoundError(task_id=task_id)
        return task

    async def _get_project(self, project_id: int):
        """Возвращает проект или поднимает доменную ошибку."""
        project = await self.projects_repository.get_by_id(project_id=project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)
        return project

    async def _resolve_stage_id(self, project_id: int, stage_id: int | None) -> int:
        """Возвращает стадию создаваемой задачи, проверяя её принадлежность проекту."""
        stages = await self.stages_repository.get_by_project(project_id=project_id)
        if not stages:
            raise ProjectStageNotFoundError(stage_id=0)
        if stage_id is None:
            return stages[0].id
        if stage_id not in {stage.id for stage in stages}:
            stage = await self.stages_repository.get_by_id(stage_id=stage_id)
            if stage is None:
                raise ProjectStageNotFoundError(stage_id=stage_id)
            raise ProjectStageForeignProjectError(stage_id=stage_id, project_id=project_id)
        return stage_id

    async def _ensure_wbs_node_in_project(self, node_id: int, project_id: int) -> None:
        """Проверяет, что раздел ИСР существует и принадлежит тому же проекту."""
        node = await self.wbs_nodes_repository.get_by_id(node_id=node_id)
        if node is None:
            raise WbsNodeNotFoundError(node_id=node_id)
        if node.project_id != project_id:
            raise WbsNodeForeignProjectError(node_id=node_id, project_id=project_id)

    async def _save_with_number(self, project_id: int, payload: dict) -> Task:
        """Сохраняет задачу, повторяя попытку при гонке за номером."""
        for _ in range(NUMBER_ALLOCATION_ATTEMPTS):
            number = await self.tasks_repository.get_next_number(project_id=project_id)
            try:
                return await self.tasks_repository.save(data={**payload, "number": number})
            except TaskNumberAlreadyExistsRepositoryError:
                logger.warning(
                    "⚠️ Номер %s занят в проекте id=%s, повторяю выдачу.",
                    number,
                    project_id,
                )
        raise TaskNumberAllocationError(project_id=project_id)

    async def _search_task_ids(self, project_id: int, search: str) -> set[int]:
        """Объединяет совпадения по задачам и их комментариям."""
        task_ids = await self.tasks_repository.search_ids(
            project_id=project_id,
            search=search,
        )
        comment_task_ids = await self.comments_repository.search_task_ids(search=search)
        if comment_task_ids:
            project_task_ids = {
                task.id
                for task in await self.tasks_repository.get_by_project(project_id=project_id)
            }
            task_ids.update(comment_task_ids & project_task_ids)
        return task_ids

    async def _build_comment_context(self, task_ids: list[int]) -> dict[int, tuple[int, str]]:
        """Строит карту количества и текста последнего комментария по задачам."""
        if not task_ids:
            return {}
        comments = await self.comments_repository.get_all()
        wanted = set(task_ids)
        context: dict[int, tuple[int, str]] = {}
        for comment in comments:
            if comment.task_id not in wanted:
                continue
            count, _ = context.get(comment.task_id, (0, ""))
            context[comment.task_id] = (count + 1, comment.body_md)
        return context

    async def _record_field_changes(self, task: Task, data: dict) -> None:
        """Фиксирует изменения значимых полей задачи в истории."""
        if "due_date" in data and data["due_date"] != task.due_date:
            await self.activity_repository.save(
                task_id=task.id,
                event_type=TaskActivityEventType.DUE_DATE_CHANGED,
                from_value=str(task.due_date) if task.due_date else None,
                to_value=str(data["due_date"]) if data["due_date"] else None,
            )
        if "description_md" in data and data["description_md"] != task.description_md:
            await self.activity_repository.save(
                task_id=task.id,
                event_type=TaskActivityEventType.DESCRIPTION_CHANGED,
                from_value=None,
                to_value=None,
            )
        if "priority" in data and data["priority"] != task.priority:
            await self.activity_repository.save(
                task_id=task.id,
                event_type=TaskActivityEventType.PRIORITY_CHANGED,
                from_value=task.priority.value,
                to_value=str(getattr(data["priority"], "value", data["priority"])),
            )
        if "assignee" in data and data["assignee"] != task.assignee:
            await self.activity_repository.save(
                task_id=task.id,
                event_type=TaskActivityEventType.ASSIGNEE_CHANGED,
                from_value=task.assignee,
                to_value=data["assignee"],
            )

    async def _cleanup_deleted_task_files(self, task_id: int) -> None:
        """Best-effort очищает физический каталог удалённой задачи."""
        if self.attachment_storage is None:
            return
        try:
            await self.attachment_storage.delete_task_directory(task_id)
        except TaskAttachmentStorageError:
            logger.warning(
                "⚠️ Не удалось очистить каталог файлов удалённой задачи id=%s.",
                task_id,
                exc_info=True,
            )


def build_task_key(project_key: str, number: int) -> str:
    """Возвращает отображаемый идентификатор задачи вида ``VERA-142``."""
    return f"{project_key}-{number}"


def to_task_schema(task: Task, project_key: str) -> TaskSchema:
    """Преобразует ORM-задачу в схему ответа с отображаемым идентификатором.

    Args:
        task: ORM-модель задачи.
        project_key: Короткий код проекта для формирования ключа задачи.

    Returns:
        Схема задачи без агрегатов комментариев и поиска.
    """
    return TaskSchema(
        id=task.id,
        project_id=task.project_id,
        stage_id=task.stage_id,
        wbs_node_id=task.wbs_node_id,
        number=task.number,
        key=build_task_key(project_key=project_key, number=task.number),
        title=task.title,
        description_md=task.description_md,
        priority=task.priority,
        role=task.role,
        assignee=task.assignee,
        due_date=task.due_date,
        position=task.position,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
