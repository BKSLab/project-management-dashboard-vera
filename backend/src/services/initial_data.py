import json
import logging
from pathlib import Path

from src.db.models.wbs import WbsRole
from src.exceptions.initial_data import (
    InitialDataServiceError,
    SeedStateAlreadyExistsRepositoryError,
    SeedStateRepositoryError,
)
from src.exceptions.kanban_stages import KanbanStagesRepositoryError
from src.exceptions.kanban_tasks import KanbanTasksRepositoryError
from src.exceptions.wbs import WbsRepositoryError
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.seed_state import SeedStateRepository
from src.repositories.wbs import WbsRepository

logger = logging.getLogger(__name__)


class InitialDataService:
    """Надёжно и ровно один раз загружает базовую ИСР и стадии канбана."""

    SEED_KEY = "vera_wbs_v1"
    DEFAULT_STAGES = (
        {"name": "Бэклог", "order_index": 0, "color": "#999999", "is_done_stage": False},
        {"name": "К выполнению", "order_index": 1, "color": "#3B82F6", "is_done_stage": False},
        {"name": "В работе", "order_index": 2, "color": "#F5B800", "is_done_stage": False},
        {"name": "На проверке", "order_index": 3, "color": "#A855F7", "is_done_stage": False},
        {"name": "Готово", "order_index": 4, "color": "#22C55E", "is_done_stage": True},
    )

    def __init__(
        self,
        seed_state_repository: SeedStateRepository,
        stages_repository: KanbanStagesRepository,
        tasks_repository: KanbanTasksRepository,
        wbs_repository: WbsRepository,
        data_path: Path,
    ):
        self.seed_state_repository = seed_state_repository
        self.stages_repository = stages_repository
        self.tasks_repository = tasks_repository
        self.wbs_repository = wbs_repository
        self.data_path = data_path

    def _read_nodes(self) -> list[dict]:
        """Читает и минимально валидирует JSON-снэпшот ИСР."""
        if not self.data_path.exists():
            raise InitialDataServiceError(f"Файл ИСР не найден: {self.data_path}.")
        try:
            nodes = json.loads(self.data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise InitialDataServiceError(
                f"Не удалось прочитать JSON ИСР: {self.data_path}."
            ) from error
        if not isinstance(nodes, list) or not nodes:
            raise InitialDataServiceError("JSON ИСР не содержит список узлов.")

        seen_codes: set[str] = set()
        for node in nodes:
            code = node.get("code")
            parent_code = node.get("parent_code")
            if not isinstance(code, str) or code in seen_codes:
                raise InitialDataServiceError(f"Некорректный или повторный код ИСР: {code!r}.")
            if parent_code is not None and parent_code not in seen_codes:
                raise InitialDataServiceError(
                    f"Родитель {parent_code!r} узла {code!r} отсутствует или идёт позже."
                )
            seen_codes.add(code)
        return nodes

    @staticmethod
    def _resolve_role(raw_role: str | None) -> WbsRole | None:
        """Преобразует строковую роль снэпшота в enum модели."""
        if raw_role is None:
            return None
        try:
            return WbsRole(raw_role)
        except ValueError as error:
            raise InitialDataServiceError(f"Неизвестная роль ИСР: {raw_role}.") from error

    async def ensure_loaded(self) -> None:
        """Загружает и проверяет начальные данные, если набор ещё не завершён.

        Args:
            Нет дополнительных аргументов.

        Returns:
            ``None`` после проверки или успешной загрузки данных.

        Raises:
            InitialDataServiceError: Если снэпшот некорректен или загрузка не завершилась.
        """
        try:
            nodes = self._read_nodes()
            state = await self.seed_state_repository.get_by_key(key=self.SEED_KEY)
            stages = await self.stages_repository.get_all()
            stages_by_name = {stage.name: stage for stage in stages}
            existing_items = await self.wbs_repository.get_all_items()
            items_by_code = {item.code: item for item in existing_items}
            existing_tasks = await self.tasks_repository.get_all()
            tasks_by_wbs_item_id = {
                task.wbs_item_id: task for task in existing_tasks if task.wbs_item_id is not None
            }
            expected_codes = {node["code"] for node in nodes}
            expected_leaf_ids = {
                items_by_code[node["code"]].id
                for node in nodes
                if node["is_leaf"] and node["code"] in items_by_code
            }
            seed_is_complete = (
                len(items_by_code) >= len(nodes)
                and expected_codes.issubset(items_by_code)
                and expected_leaf_ids.issubset(tasks_by_wbs_item_id)
                and all(stage["name"] in stages_by_name for stage in self.DEFAULT_STAGES)
            )
            if state is not None and seed_is_complete:
                logger.info(
                    "✅ Начальные данные %s проверены: %s узлов ИСР.",
                    self.SEED_KEY,
                    len(nodes),
                )
                return
            if state is not None:
                logger.warning(
                    "⚠️ Маркер %s найден, но начальные данные неполны; выполняется восстановление.",
                    self.SEED_KEY,
                )

            for stage_data in self.DEFAULT_STAGES:
                if stage_data["name"] not in stages_by_name:
                    stage = await self.stages_repository.save(data=dict(stage_data))
                    stages_by_name[stage.name] = stage
                    logger.info("➕ Создана стадия канбана %s.", stage.name)

            backlog_stage = stages_by_name.get("Бэклог")
            if backlog_stage is None:
                raise InitialDataServiceError("После загрузки отсутствует стадия «Бэклог».")

            for node in nodes:
                item = items_by_code.get(node["code"])
                if item is None:
                    parent = items_by_code.get(node["parent_code"])
                    item = await self.wbs_repository.create_item(
                        data={
                            "parent_id": parent.id if parent else None,
                            "code": node["code"],
                            "phase_name": node["phase_name"],
                            "title": node["title"],
                            "role": self._resolve_role(node["role"]),
                            "order_index": node["order_index"],
                            "is_leaf": node["is_leaf"],
                        }
                    )
                    items_by_code[item.code] = item
                    logger.info("➕ Создан узел ИСР %s.", item.code)

                if node["is_leaf"] and item.id not in tasks_by_wbs_item_id:
                    task = await self.tasks_repository.save(
                        data={
                            "wbs_item_id": item.id,
                            "stage_id": backlog_stage.id,
                            "title": item.title,
                            "position": float(item.order_index),
                        }
                    )
                    tasks_by_wbs_item_id[item.id] = task

            verified_items = await self.wbs_repository.get_all_items()
            verified_by_code = {item.code: item for item in verified_items}
            verified_tasks = await self.tasks_repository.get_all()
            verified_task_wbs_ids = {
                task.wbs_item_id for task in verified_tasks if task.wbs_item_id is not None
            }
            missing_codes = [node["code"] for node in nodes if node["code"] not in verified_by_code]
            missing_tasks = [
                node["code"]
                for node in nodes
                if node["is_leaf"]
                and (
                    node["code"] not in verified_by_code
                    or verified_by_code[node["code"]].id not in verified_task_wbs_ids
                )
            ]
            if missing_codes or missing_tasks:
                raise InitialDataServiceError(
                    "Проверка ИСР после загрузки не пройдена: "
                    f"нет узлов={missing_codes}, нет задач={missing_tasks}."
                )

            if state is None:
                try:
                    await self.seed_state_repository.save(key=self.SEED_KEY)
                except SeedStateAlreadyExistsRepositoryError:
                    logger.warning(
                        "⚠️ Маркер %s уже записан параллельным процессом.",
                        self.SEED_KEY,
                    )
            logger.info(
                "✅ Начальные данные ИСР загружены: %s узлов, %s листовых задач.",
                len(nodes),
                sum(1 for node in nodes if node["is_leaf"]),
            )
        except InitialDataServiceError:
            raise
        except (
            SeedStateRepositoryError,
            KanbanStagesRepositoryError,
            KanbanTasksRepositoryError,
            WbsRepositoryError,
        ) as error:
            logger.error("❌ Ошибка подготовки начальных данных.", exc_info=True)
            raise InitialDataServiceError(str(error)) from error
