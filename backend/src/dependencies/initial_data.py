from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.seed_state import SeedStateRepository
from src.repositories.wbs import WbsRepository
from src.services.initial_data import InitialDataService

WBS_DATA_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data" / "wbs_seed.json"


def create_initial_data_service(session: AsyncSession) -> InitialDataService:
    """Собирает сервис начальных данных поверх одной сессии БД."""
    return InitialDataService(
        seed_state_repository=SeedStateRepository(session),
        stages_repository=KanbanStagesRepository(session),
        tasks_repository=KanbanTasksRepository(session),
        wbs_repository=WbsRepository(session),
        data_path=WBS_DATA_PATH,
    )
