import logging

from src.db.models.task_activity import TaskActivityEventType
from src.db.models.wbs import WbsItem
from src.exceptions.kanban_stages import (
    KanbanStageNotFoundError,
    KanbanStagesRepositoryError,
)
from src.exceptions.kanban_tasks import (
    KanbanTaskFromWbsDeleteError,
    KanbanTaskNotFoundError,
    KanbanTasksRepositoryError,
    KanbanTasksServiceError,
)
from src.exceptions.task_activity import TaskActivityRepositoryError
from src.exceptions.task_attachments import TaskAttachmentStorageError
from src.exceptions.task_comments import TaskCommentsRepositoryError
from src.exceptions.wbs import WbsRepositoryError
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.wbs import WbsRepository
from src.schemas.kanban_tasks import TaskSchema
from src.storage.task_attachments import TaskAttachmentStorage
from src.utils.fts import mark_literal_match

logger = logging.getLogger(__name__)

RepositoryErrors = (
    KanbanStagesRepositoryError,
    KanbanTasksRepositoryError,
    TaskActivityRepositoryError,
    TaskCommentsRepositoryError,
    WbsRepositoryError,
)


class KanbanTasksService:
    """Сервис сценариев работы с карточками канбана."""

    def __init__(
        self,
        tasks_repository: KanbanTasksRepository,
        stages_repository: KanbanStagesRepository,
        comments_repository: TaskCommentsRepository,
        activity_repository: TaskActivityRepository,
        wbs_repository: WbsRepository,
        attachment_storage: TaskAttachmentStorage | None = None,
    ):
        self.tasks_repository = tasks_repository
        self.stages_repository = stages_repository
        self.comments_repository = comments_repository
        self.activity_repository = activity_repository
        self.wbs_repository = wbs_repository
        self.attachment_storage = attachment_storage

    # Блок подготовки контекста карточек

    async def _build_wbs_context(self) -> dict[int, tuple[str, str | None]]:
        """Строит карту узла ИСР в код и название корневой фазы."""
        items = await self.wbs_repository.get_all_items()
        by_id = {item.id: item for item in items}

        def phase_name_of(item: WbsItem) -> str | None:
            node = item
            while node.parent_id is not None:
                parent = by_id.get(node.parent_id)
                if parent is None:
                    return None
                node = parent
            return node.phase_name

        return {item.id: (item.code, phase_name_of(item)) for item in items}

    async def _build_comment_context(self) -> dict[int, tuple[int, str]]:
        """Строит карту количества и последнего текста комментария по задачам."""
        comments = await self.comments_repository.get_all()
        context: dict[int, tuple[int, str]] = {}
        for comment in comments:
            count, _ = context.get(comment.task_id, (0, ""))
            context[comment.task_id] = (count + 1, comment.body_md)
        return context

    async def _search_task_ids(self, search: str) -> set[int]:
        """Объединяет совпадения задач, комментариев и кодов ИСР."""
        task_ids = await self.tasks_repository.search_ids(search=search)
        task_ids.update(await self.comments_repository.search_task_ids(search=search))
        wbs_item_ids = await self.wbs_repository.get_ids_by_code_search(search=search)
        task_ids.update(
            await self.tasks_repository.get_ids_by_wbs_item_ids(wbs_item_ids=wbs_item_ids)
        )
        return task_ids

    # Блок публичных сценариев задач

    async def get_task_list(
        self,
        stage_id: int | None = None,
        search: str | None = None,
    ) -> list[TaskSchema]:
        """Возвращает задачи с агрегатами ИСР, комментариев и поиска.

        Args:
            stage_id: Опциональный фильтр по стадии.
            search: Опциональный полнотекстовый запрос.

        Returns:
            Карточки задач в сохранённом порядке.

        Raises:
            KanbanTasksServiceError: Если получить данные не удалось.
        """
        try:
            search_text = search.strip() if search else ""
            matching_ids = await self._search_task_ids(search_text) if search_text else None
            tasks = await self.tasks_repository.get_all(
                stage_id=stage_id,
                task_ids=matching_ids,
            )
            wbs_context = await self._build_wbs_context()
            comment_context = await self._build_comment_context()
            task_highlights = (
                await self.tasks_repository.get_search_highlights(
                    task_ids=[task.id for task in tasks],
                    search=search_text,
                )
                if search_text
                else {}
            )
            comment_highlights = (
                await self.comments_repository.get_search_highlights(
                    task_ids=[task.id for task in tasks],
                    search=search_text,
                )
                if search_text
                else {}
            )

            result: list[TaskSchema] = []
            for task in tasks:
                schema = TaskSchema.model_validate(task)
                if task.wbs_item_id is not None and task.wbs_item_id in wbs_context:
                    code, phase_name = wbs_context[task.wbs_item_id]
                    schema.wbs_code = code
                    schema.wbs_phase_name = phase_name
                schema.comments_count, schema.last_comment = comment_context.get(task.id, (0, None))

                highlight = task_highlights.get(task.id)
                if highlight is None:
                    highlight = comment_highlights.get(task.id)
                if highlight is None and search_text and schema.wbs_code:
                    marked_code = mark_literal_match(schema.wbs_code, search_text)
                    if marked_code is not None:
                        highlight = {
                            "search_match_source": "wbs_code",
                            "search_excerpt": marked_code,
                        }
                for field, value in (highlight or {}).items():
                    setattr(schema, field, value)
                result.append(schema)
            return result
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения задач канбана.", exc_info=True)
            raise KanbanTasksServiceError(str(error)) from error

    async def get_task(self, task_id: int) -> TaskSchema:
        """Возвращает задачу по идентификатору.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            Карточка задачи.

        Raises:
            KanbanTaskNotFoundError: Если задача не найдена.
            KanbanTasksServiceError: Если получить задачу не удалось.
        """
        try:
            task = await self.tasks_repository.get_by_id(task_id=task_id)
            if task is None:
                raise KanbanTaskNotFoundError(task_id=task_id)
            return TaskSchema.model_validate(task)
        except KanbanTaskNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения задачи id=%s.", task_id, exc_info=True)
            raise KanbanTasksServiceError(str(error)) from error

    async def create_task(self, data: dict) -> TaskSchema:
        """Создаёт ручную задачу в указанной или первой стадии.

        Args:
            data: Поля создаваемой задачи.

        Returns:
            Созданная карточка задачи.

        Raises:
            KanbanStageNotFoundError: Если указанная стадия не найдена.
            KanbanTasksServiceError: Если создать задачу не удалось.
        """
        try:
            stage_id = data.get("stage_id")
            if stage_id is None:
                stages = await self.stages_repository.get_all()
                if not stages:
                    raise KanbanStageNotFoundError(stage_id=0)
                data["stage_id"] = stages[0].id
            elif await self.stages_repository.get_by_id(stage_id=stage_id) is None:
                raise KanbanStageNotFoundError(stage_id=stage_id)
            task = await self.tasks_repository.save(data=data)
            return TaskSchema.model_validate(task)
        except KanbanStageNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка создания задачи.", exc_info=True)
            raise KanbanTasksServiceError(str(error)) from error

    async def update_task(self, task_id: int, data: dict) -> TaskSchema:
        """Обновляет задачу и фиксирует значимые изменения в истории.

        Args:
            task_id: Идентификатор задачи.
            data: Изменяемые поля задачи.

        Returns:
            Обновлённая карточка задачи.

        Raises:
            KanbanTaskNotFoundError: Если задача не найдена.
            KanbanTasksServiceError: Если обновить задачу не удалось.
        """
        try:
            task = await self.tasks_repository.get_by_id(task_id=task_id)
            if task is None:
                raise KanbanTaskNotFoundError(task_id=task_id)
            if "due_date" in data and data["due_date"] != task.due_date:
                await self.activity_repository.save(
                    task_id=task_id,
                    event_type=TaskActivityEventType.DUE_DATE_CHANGED,
                    from_value=str(task.due_date) if task.due_date else None,
                    to_value=str(data["due_date"]) if data["due_date"] else None,
                )
            if "description_md" in data and data["description_md"] != task.description_md:
                await self.activity_repository.save(
                    task_id=task_id,
                    event_type=TaskActivityEventType.DESCRIPTION_CHANGED,
                    from_value=None,
                    to_value=None,
                )
            updated = await self.tasks_repository.update(task=task, data=data)
            return TaskSchema.model_validate(updated)
        except KanbanTaskNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка обновления задачи id=%s.", task_id, exc_info=True)
            raise KanbanTasksServiceError(str(error)) from error

    async def move_task(
        self,
        task_id: int,
        stage_id: int,
        position: float | None = None,
    ) -> TaskSchema:
        """Перемещает задачу и фиксирует смену стадии в истории.

        Args:
            task_id: Идентификатор задачи.
            stage_id: Идентификатор целевой стадии.
            position: Позиция задачи внутри стадии. Если не указана, задача
                помещается в конец целевой стадии.

        Returns:
            Перемещённая карточка задачи.

        Raises:
            KanbanTaskNotFoundError: Если задача не найдена.
            KanbanStageNotFoundError: Если целевая стадия не найдена.
            KanbanTasksServiceError: Если переместить задачу не удалось.
        """
        try:
            task = await self.tasks_repository.get_by_id(task_id=task_id)
            if task is None:
                raise KanbanTaskNotFoundError(task_id=task_id)
            target_stage = await self.stages_repository.get_by_id(stage_id=stage_id)
            if target_stage is None:
                raise KanbanStageNotFoundError(stage_id=stage_id)
            if task.stage_id == stage_id and position is None:
                return TaskSchema.model_validate(task)
            target_position = position
            if target_position is None:
                max_position = await self.tasks_repository.get_max_position_by_stage(
                    stage_id=stage_id
                )
                target_position = max_position + 1000.0
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
            return TaskSchema.model_validate(updated)
        except (KanbanTaskNotFoundError, KanbanStageNotFoundError):
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка перемещения задачи id=%s.", task_id, exc_info=True)
            raise KanbanTasksServiceError(str(error)) from error

    async def delete_task(self, task_id: int) -> None:
        """Удаляет ручную задачу канбана.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            KanbanTaskNotFoundError: Если задача не найдена.
            KanbanTaskFromWbsDeleteError: Если задача создана из ИСР.
            KanbanTasksServiceError: Если удалить задачу не удалось.
        """
        try:
            task = await self.tasks_repository.get_by_id(task_id=task_id)
            if task is None:
                raise KanbanTaskNotFoundError(task_id=task_id)
            if task.wbs_item_id is not None:
                raise KanbanTaskFromWbsDeleteError(task_id=task_id)
            await self.tasks_repository.delete(task=task)
            await self._cleanup_deleted_task_files(task_id)
        except (KanbanTaskNotFoundError, KanbanTaskFromWbsDeleteError):
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка удаления задачи id=%s.", task_id, exc_info=True)
            raise KanbanTasksServiceError(str(error)) from error

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
