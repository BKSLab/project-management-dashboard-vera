import logging
from collections import defaultdict

from src.db.models.kanban_tasks import KanbanTask
from src.db.models.wbs import WbsItem, WbsRole
from src.exceptions.kanban_stages import KanbanStagesRepositoryError
from src.exceptions.kanban_tasks import (
    KanbanTasksRepositoryError,
    KanbanTaskWbsLinkAlreadyExistsRepositoryError,
)
from src.exceptions.task_attachments import TaskAttachmentStorageError
from src.exceptions.wbs import (
    WbsCodeAlreadyExistsRepositoryError,
    WbsCodeConflictError,
    WbsItemNotFoundError,
    WbsRepositoryError,
    WbsServiceError,
)
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.wbs import WbsRepository
from src.schemas.wbs import WbsItemSchema, WbsNodeSchema, WbsProgressSchema, WbsTaskRefSchema
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)


class WbsService:
    """Сервис сборки дерева ИСР с rollup-прогрессом и управления узлами."""

    def __init__(
        self,
        wbs_repository: WbsRepository,
        tasks_repository: KanbanTasksRepository,
        stages_repository: KanbanStagesRepository,
        attachment_storage: TaskAttachmentStorage | None = None,
    ):
        self.wbs_repository = wbs_repository
        self.tasks_repository = tasks_repository
        self.stages_repository = stages_repository
        self.attachment_storage = attachment_storage

    @staticmethod
    def _count_leaf_progress(
        item: WbsItem,
        children_by_parent: dict[int, list[WbsItem]],
        tasks_by_wbs: dict[int, KanbanTask],
        done_stage_ids: set[int],
    ) -> tuple[int, int]:
        """Возвращает (done, total) среди листовых задач всех потомков узла."""
        if item.is_leaf:
            task = tasks_by_wbs.get(item.id)
            if task is None:
                return 0, 0
            is_done = task.stage_id in done_stage_ids
            return (1 if is_done else 0), 1

        done = 0
        total = 0
        for child in children_by_parent.get(item.id, []):
            child_done, child_total = WbsService._count_leaf_progress(
                child,
                children_by_parent,
                tasks_by_wbs,
                done_stage_ids,
            )
            done += child_done
            total += child_total
        return done, total

    @staticmethod
    def _build_node(
        item: WbsItem,
        children_by_parent: dict[int, list[WbsItem]],
        tasks_by_wbs: dict[int, KanbanTask],
        stage_names: dict[int, str],
        done_stage_ids: set[int],
    ) -> WbsNodeSchema:
        """Рекурсивно строит API-представление узла ИСР."""
        task_ref = None
        progress = None

        if item.is_leaf:
            task = tasks_by_wbs.get(item.id)
            if task is not None:
                task_ref = WbsTaskRefSchema(
                    id=task.id,
                    stage_id=task.stage_id,
                    stage_name=stage_names.get(task.stage_id, ""),
                    due_date=task.due_date,
                )
        else:
            done, total = WbsService._count_leaf_progress(
                item,
                children_by_parent,
                tasks_by_wbs,
                done_stage_ids,
            )
            progress = WbsProgressSchema(done=done, total=total)

        children = children_by_parent.get(item.id, [])
        return WbsNodeSchema(
            id=item.id,
            code=item.code,
            phase_name=item.phase_name,
            title=item.title,
            role=item.role,
            progress=progress,
            task=task_ref,
            children=[
                WbsService._build_node(
                    child,
                    children_by_parent,
                    tasks_by_wbs,
                    stage_names,
                    done_stage_ids,
                )
                for child in children
            ],
        )

    async def get_tree(self) -> list[WbsNodeSchema]:
        """Возвращает дерево ИСР верхнего уровня с прогрессом и задачами.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Корневые узлы дерева ИСР.

        Raises:
            WbsServiceError: Если получить данные дерева не удалось.
        """
        try:
            items = await self.wbs_repository.get_all_items()
            tasks = await self.tasks_repository.get_all()
            stages = await self.stages_repository.get_all()
            tasks_by_wbs = {
                task.wbs_item_id: task for task in tasks if task.wbs_item_id is not None
            }
            stage_names = {stage.id: stage.name for stage in stages}
            done_stage_ids = {stage.id for stage in stages if stage.is_done_stage}

            children_by_parent: dict[int, list[WbsItem]] = defaultdict(list)
            roots: list[WbsItem] = []
            for item in items:
                if item.parent_id is None:
                    roots.append(item)
                else:
                    children_by_parent[item.parent_id].append(item)

            for siblings in children_by_parent.values():
                siblings.sort(key=lambda child: child.order_index)
            roots.sort(key=lambda item: item.order_index)

            return [
                self._build_node(
                    root,
                    children_by_parent,
                    tasks_by_wbs,
                    stage_names,
                    done_stage_ids,
                )
                for root in roots
            ]
        except (
            WbsRepositoryError,
            KanbanTasksRepositoryError,
            KanbanStagesRepositoryError,
        ) as error:
            logger.error("❌ Ошибка построения дерева ИСР.", exc_info=True)
            raise WbsServiceError(str(error)) from error

    async def _get_backlog_stage_id(self) -> int | None:
        stages = await self.stages_repository.get_all()
        return stages[0].id if stages else None

    async def create_item(
        self,
        parent_id: int | None,
        title: str,
        role: WbsRole | None,
        phase_name: str | None,
    ) -> WbsItemSchema:
        """Создаёт узел ИСР и синхронизирует его карточку канбана.

        Если родитель был листом, превращает его в раздел и удаляет его прежнюю карточку.

        Args:
            parent_id: Родительский узел или ``None`` для корневого узла.
            title: Название узла.
            role: Ответственная роль.
            phase_name: Название фазы для корневого узла.

        Returns:
            Созданный узел ИСР.

        Raises:
            WbsItemNotFoundError: Если родитель не найден.
            WbsServiceError: Если создать узел не удалось.
        """
        try:
            parent: WbsItem | None = None
            if parent_id is not None:
                parent = await self.wbs_repository.get_by_id(parent_id)
                if parent is None:
                    raise WbsItemNotFoundError(item_id=parent_id)

            siblings = await self.wbs_repository.get_children(parent_id)
            order_index = len(siblings)
            code = (
                f"{parent.code}.{order_index + 1}" if parent is not None else str(order_index + 1)
            )

            if parent is not None and parent.is_leaf:
                parent_task = await self.tasks_repository.get_by_wbs_item_id(wbs_item_id=parent.id)
                if parent_task is not None:
                    await self.tasks_repository.delete(task=parent_task)
                await self.wbs_repository.update_item(item=parent, data={"is_leaf": False})

            new_item = await self.wbs_repository.create_item(
                data={
                    "parent_id": parent_id,
                    "code": code,
                    "phase_name": phase_name if parent_id is None else None,
                    "title": title,
                    "role": role,
                    "order_index": order_index,
                    "is_leaf": True,
                }
            )

            backlog_stage_id = await self._get_backlog_stage_id()
            if backlog_stage_id is not None:
                await self.tasks_repository.save(
                    data={
                        "wbs_item_id": new_item.id,
                        "stage_id": backlog_stage_id,
                        "title": new_item.title,
                        "position": 0.0,
                    }
                )
            return WbsItemSchema.model_validate(new_item)
        except WbsCodeAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт кода ИСР %s.", error.code)
            raise WbsCodeConflictError(code=error.code) from error
        except KanbanTaskWbsLinkAlreadyExistsRepositoryError as error:
            logger.error(
                "❌ Узел ИСР id=%s уже связан с задачей.",
                error.wbs_item_id,
                exc_info=True,
            )
            raise WbsServiceError(str(error)) from error
        except WbsItemNotFoundError:
            raise
        except (
            WbsRepositoryError,
            KanbanTasksRepositoryError,
            KanbanStagesRepositoryError,
        ) as error:
            logger.error("❌ Ошибка создания узла ИСР.", exc_info=True)
            raise WbsServiceError(str(error)) from error

    async def update_item(self, item_id: int, data: dict) -> WbsItemSchema:
        """Обновляет узел ИСР и заголовок связанной задачи.

        Args:
            item_id: Идентификатор узла ИСР.
            data: Изменяемые поля узла.

        Returns:
            Обновлённый узел ИСР.

        Raises:
            WbsItemNotFoundError: Если узел не найден.
            WbsCodeConflictError: Если новый код уже занят.
            WbsServiceError: Если обновить узел не удалось.
        """
        try:
            item = await self.wbs_repository.get_by_id(item_id)
            if item is None:
                raise WbsItemNotFoundError(item_id=item_id)

            linked_task = await self.tasks_repository.get_by_wbs_item_id(wbs_item_id=item.id)
            updated = await self.wbs_repository.update_item(item=item, data=data)
            if "title" in data and item.is_leaf and linked_task is not None:
                await self.tasks_repository.update(
                    task=linked_task,
                    data={"title": data["title"]},
                )
            return WbsItemSchema.model_validate(updated)
        except WbsCodeAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт кода ИСР %s.", error.code)
            raise WbsCodeConflictError(code=error.code) from error
        except WbsItemNotFoundError:
            raise
        except (WbsRepositoryError, KanbanTasksRepositoryError) as error:
            logger.error("❌ Ошибка обновления узла ИСР id=%s.", item_id, exc_info=True)
            raise WbsServiceError(str(error)) from error

    async def _delete_linked_tasks_recursively(self, item: WbsItem) -> None:
        """Удаляет связанные карточки канбана у узла и всех его потомков."""
        if item.is_leaf:
            linked_task = await self.tasks_repository.get_by_wbs_item_id(wbs_item_id=item.id)
            if linked_task is not None:
                await self.tasks_repository.delete(task=linked_task)
                await self._cleanup_deleted_task_files(linked_task.id)

        children = await self.wbs_repository.get_children(item.id)
        for child in children:
            await self._delete_linked_tasks_recursively(child)

    async def _cleanup_deleted_task_files(self, task_id: int) -> None:
        """Best-effort очищает физический каталог удалённой WBS-задачи."""
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

    async def delete_item(self, item_id: int) -> None:
        """Удаляет узел ИСР, потомков и связанные карточки канбана.

        Args:
            item_id: Идентификатор узла ИСР.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            WbsItemNotFoundError: Если узел не найден.
            WbsServiceError: Если удалить узел не удалось.
        """
        try:
            item = await self.wbs_repository.get_by_id(item_id)
            if item is None:
                raise WbsItemNotFoundError(item_id=item_id)
            await self._delete_linked_tasks_recursively(item)
            await self.wbs_repository.delete_item(item=item)
        except WbsItemNotFoundError:
            raise
        except (WbsRepositoryError, KanbanTasksRepositoryError) as error:
            logger.error("❌ Ошибка удаления узла ИСР id=%s.", item_id, exc_info=True)
            raise WbsServiceError(str(error)) from error
