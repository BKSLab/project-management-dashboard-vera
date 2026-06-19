import logging
from collections import defaultdict

from src.db.models.wbs import WbsItem
from src.exceptions.services import WbsItemNotFoundError
from src.repositories.kanban import KanbanRepository
from src.repositories.wbs import WbsRepository
from src.schemas.wbs import WbsItemSchema, WbsNodeSchema, WbsProgressSchema, WbsTaskRefSchema

logger = logging.getLogger(__name__)


class WbsService:
    """Сервис сборки дерева ИСР с rollup-прогрессом и управления узлами."""

    def __init__(self, wbs_repository: WbsRepository, kanban_repository: KanbanRepository):
        self.wbs_repository = wbs_repository
        self.kanban_repository = kanban_repository

    @staticmethod
    def _count_leaf_progress(item: WbsItem, children_by_parent: dict) -> tuple[int, int]:
        """Возвращает (done, total) среди листовых задач всех потомков узла."""
        if item.is_leaf:
            if item.task is None:
                return 0, 0
            is_done = bool(item.task.stage and item.task.stage.is_done_stage)
            return (1 if is_done else 0), 1

        done = 0
        total = 0
        for child in children_by_parent.get(item.id, []):
            child_done, child_total = WbsService._count_leaf_progress(child, children_by_parent)
            done += child_done
            total += child_total
        return done, total

    @staticmethod
    def _build_node(item: WbsItem, children_by_parent: dict) -> WbsNodeSchema:
        task_ref = None
        progress = None

        if item.is_leaf:
            if item.task is not None:
                task_ref = WbsTaskRefSchema(
                    id=item.task.id,
                    stage_id=item.task.stage_id,
                    stage_name=item.task.stage.name if item.task.stage else '',
                    due_date=item.task.due_date,
                )
        else:
            done, total = WbsService._count_leaf_progress(item, children_by_parent)
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
            children=[WbsService._build_node(child, children_by_parent) for child in children],
        )

    async def get_tree(self) -> list[WbsNodeSchema]:
        """Возвращает дерево ИСР верхнего уровня с прогрессом и связанными задачами."""
        items = await self.wbs_repository.get_all_items()

        children_by_parent: dict = defaultdict(list)
        roots: list[WbsItem] = []
        for item in items:
            if item.parent_id is None:
                roots.append(item)
            else:
                children_by_parent[item.parent_id].append(item)

        for siblings in children_by_parent.values():
            siblings.sort(key=lambda child: child.order_index)
        roots.sort(key=lambda item: item.order_index)

        return [self._build_node(root, children_by_parent) for root in roots]

    async def _get_backlog_stage_id(self) -> int | None:
        stages = await self.kanban_repository.get_all_stages()
        return stages[0].id if stages else None

    async def create_item(
        self, parent_id: int | None, title: str, role, phase_name: str | None
    ) -> WbsItemSchema:
        """Создаёт узел ИСР. Если родитель был листом, превращает его в фазу/раздел
        и удаляет его собственную карточку канбана (у фазы карточки не бывает)."""
        parent: WbsItem | None = None
        if parent_id is not None:
            parent = await self.wbs_repository.get_by_id(parent_id)
            if parent is None:
                raise WbsItemNotFoundError(item_id=parent_id)

        siblings = await self.wbs_repository.get_children(parent_id)
        order_index = len(siblings)
        code = f"{parent.code}.{order_index + 1}" if parent is not None else str(order_index + 1)

        if parent is not None and parent.is_leaf:
            if parent.task is not None:
                await self.kanban_repository.delete_task(task=parent.task)
            await self.wbs_repository.update_item(item=parent, data={"is_leaf": False})

        new_item = await self.wbs_repository.create_item(data={
            "parent_id": parent_id,
            "code": code,
            "phase_name": phase_name if parent_id is None else None,
            "title": title,
            "role": role,
            "order_index": order_index,
            "is_leaf": True,
        })

        backlog_stage_id = await self._get_backlog_stage_id()
        if backlog_stage_id is not None:
            await self.kanban_repository.create_task(data={
                "wbs_item_id": new_item.id,
                "stage_id": backlog_stage_id,
                "title": new_item.title,
                "position": 0.0,
            })

        return WbsItemSchema.model_validate(new_item)

    async def update_item(
        self, item_id: int, data: dict
    ) -> WbsItemSchema:
        """Обновляет узел ИСР. При изменении названия синхронизирует заголовок связанной карточки канбана."""
        item = await self.wbs_repository.get_by_id(item_id)
        if item is None:
            raise WbsItemNotFoundError(item_id=item_id)

        linked_task = item.task
        updated = await self.wbs_repository.update_item(item=item, data=data)

        if "title" in data and item.is_leaf and linked_task is not None:
            await self.kanban_repository.update_task(task=linked_task, data={"title": data["title"]})

        return WbsItemSchema.model_validate(updated)

    async def _delete_linked_tasks_recursively(self, item: WbsItem) -> None:
        """Удаляет связанные карточки канбана у узла и всех его потомков."""
        if item.is_leaf and item.task is not None:
            await self.kanban_repository.delete_task(task=item.task)

        children = await self.wbs_repository.get_children(item.id)
        for child in children:
            child_with_task = await self.wbs_repository.get_by_id(child.id)
            if child_with_task is not None:
                await self._delete_linked_tasks_recursively(child_with_task)

    async def delete_item(self, item_id: int) -> None:
        """Удаляет узел ИСР вместе со всеми потомками и их связанными карточками канбана."""
        item = await self.wbs_repository.get_by_id(item_id)
        if item is None:
            raise WbsItemNotFoundError(item_id=item_id)

        await self._delete_linked_tasks_recursively(item)
        await self.wbs_repository.delete_item(item=item)
