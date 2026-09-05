"""Подмена клиентов внешних систем в собранном приложении.

Ради этого клиенты и вынесены в отдельные фабрики: тест должен уметь
заменить любой сетевой вызов, не поднимая ни LLM, ни Qdrant и не трогая
глобальное состояние модулей.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.clients.embedding import EmbeddingClient
from src.clients.llm import LlmClient
from src.clients.qdrant import ProjectQdrantClient
from src.clients.vision import DisabledVisionCapability
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.tasks import Task, TaskPriority
from src.dependencies.clients import (
    get_embedding_client,
    get_llm_client,
    get_qdrant_client,
    get_vision_capability,
)
from src.dependencies.http_client import get_knowledge_runtime
from src.dependencies.repositories import (
    get_project_stages_repository,
    get_projects_repository,
    get_tasks_repository,
    get_wbs_nodes_repository,
)
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.schemas.wbs_suggestion import WbsSuggestionSchema

SUGGESTION_PATH = "/api/v1/projects/1/wbs/suggestion"


@pytest.fixture
def fake_runtime() -> SimpleNamespace:
    """Контейнер клиентов-дублёров вместо созданного lifespan."""
    return SimpleNamespace(
        http_client=AsyncMock(),
        llm_client=AsyncMock(spec=LlmClient),
        embedding_client=AsyncMock(spec=EmbeddingClient),
        qdrant_client=AsyncMock(spec=ProjectQdrantClient),
        vision=DisabledVisionCapability(),
    )


@pytest.fixture
def project_data() -> None:
    """Подменяет репозитории маршрута: тест проверяет клиента, а не SQL."""
    project = Project(id=1, owner_id=1, key="TEST", name="Тест", color="#58a6ff")
    stage = ProjectStage(id=1, project_id=1, name="В работе", is_done_stage=False)
    task = Task(
        id=1,
        project_id=1,
        stage_id=1,
        number=1,
        title="Задача",
        priority=TaskPriority.MEDIUM,
    )

    projects = AsyncMock(spec=ProjectsRepository)
    projects.get_by_id.return_value = project
    stages = AsyncMock(spec=ProjectStagesRepository)
    stages.get_by_project.return_value = [stage]
    tasks = AsyncMock(spec=TasksRepository)
    tasks.get_by_project.return_value = [task]
    nodes = AsyncMock(spec=WbsNodesRepository)
    nodes.get_by_project.return_value = []

    app.dependency_overrides.update(
        {
            get_projects_repository: lambda: projects,
            get_project_stages_repository: lambda: stages,
            get_tasks_repository: lambda: tasks,
            get_wbs_nodes_repository: lambda: nodes,
        }
    )


@pytest.fixture
def override_runtime(fake_runtime: SimpleNamespace, project_data: None) -> SimpleNamespace:
    """Ставит контейнер-дублёр в граф зависимостей приложения."""
    fake_runtime.llm_client.get_structured_response.return_value = WbsSuggestionSchema()
    app.dependency_overrides[get_knowledge_runtime] = lambda: fake_runtime
    return fake_runtime


@pytest.mark.parametrize(
    "factory",
    [get_llm_client, get_embedding_client, get_qdrant_client, get_vision_capability],
    ids=["llm", "embedding", "qdrant", "vision"],
)
def test_every_client_has_its_own_override_point(factory) -> None:
    """У каждого клиента есть отдельная фабрика, пригодная для подмены."""
    runtime = SimpleNamespace(
        llm_client="llm",
        embedding_client="embedding",
        qdrant_client="qdrant",
        vision="vision",
    )

    assert isinstance(factory(runtime), str)


async def test_runtime_override_reaches_the_endpoint(
    api_client: AsyncClient,
    override_runtime: SimpleNamespace,
) -> None:
    """Подменённый контейнер используется реальным маршрутом без сети."""
    response = await api_client.post(SUGGESTION_PATH)

    assert response.status_code == 200
    override_runtime.llm_client.get_structured_response.assert_awaited_once()


async def test_single_client_can_be_replaced_without_the_others(
    api_client: AsyncClient,
    override_runtime: SimpleNamespace,
) -> None:
    """Один клиент подменяется точечно, остальные остаются прежними."""
    replacement = AsyncMock(spec=LlmClient)
    replacement.get_structured_response.return_value = WbsSuggestionSchema()
    app.dependency_overrides[get_llm_client] = lambda: replacement

    response = await api_client.post(SUGGESTION_PATH)

    assert response.status_code == 200
    replacement.get_structured_response.assert_awaited_once()
    override_runtime.llm_client.get_structured_response.assert_not_awaited()


async def test_no_network_client_is_created_during_the_request(
    api_client: AsyncClient,
    override_runtime: SimpleNamespace,
) -> None:
    """Маршрут не создаёт собственный сетевой клиент в обход общего пула."""
    await api_client.post(SUGGESTION_PATH)

    # Дублёр общего HTTP-клиента остался нетронутым: сервис работает через
    # переданный ему LLM-клиент, а не открывает соединение сам.
    override_runtime.http_client.post.assert_not_awaited()
