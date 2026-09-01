from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.documents import Document
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project, ProjectStatus
from src.db.models.tasks import Task, TaskPriority
from src.exceptions.knowledge import KnowledgeProviderError
from src.repositories.documents import DocumentsRepository
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.project_agent import AgentOutput, ProjectAgentService


def build_service(*, semantic_available: bool = True):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        owner_id=1,
        key="VERA",
        name="Агент Вера",
        description_md="Система управления рисками",
        status=ProjectStatus.ACTIVE,
        color="#58a6ff",
        created_at=now,
        updated_at=now,
    )
    stage = ProjectStage(
        id=3,
        project_id=project.id,
        name="В работе",
        order_index=1,
        color="#58a6ff",
        is_done_stage=False,
    )
    task = Task(
        id=7,
        project_id=project.id,
        stage_id=stage.id,
        number=12,
        title="Подготовить паспорт рисков",
        description_md="Согласовать владельцев рисков",
        priority=TaskPriority.HIGH,
        position=1000.0,
        created_at=now,
        updated_at=now,
    )
    document = Document(
        id=9,
        project_id=project.id,
        slug="risk-policy",
        title="Политика рисков",
        content_md="Порядок эскалации рисков",
        created_at=now,
        updated_at=now,
    )

    stages = AsyncMock(spec=ProjectStagesRepository)
    stages.get_by_project.return_value = [stage]
    tasks = AsyncMock(spec=TasksRepository)
    tasks.get_by_project.return_value = [task]
    nodes = AsyncMock(spec=WbsNodesRepository)
    nodes.get_by_project.return_value = []
    documents = AsyncMock(spec=DocumentsRepository)
    documents.get_by_project.return_value = [document]
    activity = AsyncMock(spec=TaskActivityRepository)
    activity.get_recent_by_project.return_value = []
    jobs = AsyncMock(spec=KnowledgeIndexJobsRepository)

    embedding_client = AsyncMock()
    qdrant_client = AsyncMock()
    if semantic_available:
        embedding_client.get_embedding.return_value = [1.0, 0.0]
        qdrant_client.search.return_value = []
    else:
        embedding_client.get_embedding.side_effect = KnowledgeProviderError("offline")
    llm_client = AsyncMock()
    llm_client.get_structured_response.return_value = AgentOutput(
        answer="Задача **VERA-12** находится в работе.",
        source_ids=["task:7"],
    )
    runtime = SimpleNamespace(
        embedding_client=embedding_client,
        qdrant_client=qdrant_client,
        llm_client=llm_client,
    )
    service = ProjectAgentService(
        stages_repository=stages,
        tasks_repository=tasks,
        wbs_nodes_repository=nodes,
        documents_repository=documents,
        activity_repository=activity,
        jobs_repository=jobs,
        runtime=runtime,
    )
    return service, project, runtime


@pytest.mark.asyncio
async def test_agent_combines_current_sql_state_with_validated_sources() -> None:
    service, project, runtime = build_service()

    answer = await service.ask(project=project, question="Что сейчас в работе?", history=[])

    assert answer.answer.startswith("Задача")
    assert [source.source_id for source in answer.sources] == ["task:7"]
    prompt = runtime.llm_client.get_structured_response.await_args.kwargs["content"]
    assert "VERA-12" in prompt
    assert "стадия=В работе" in prompt
    assert "приоритет=HIGH" in prompt


@pytest.mark.asyncio
async def test_agent_falls_back_to_sql_when_semantic_provider_is_offline() -> None:
    service, project, runtime = build_service(semantic_available=False)

    answer = await service.ask(project=project, question="Что сейчас в работе?", history=[])

    assert answer.sources[0].source_id == "task:7"
    runtime.qdrant_client.search.assert_not_awaited()
    runtime.llm_client.get_structured_response.assert_awaited_once()
