from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import (
    get_dashboard_service,
    get_document_links_service,
    get_documents_service,
    get_project_stages_service,
    get_projects_service,
    get_task_activity_service,
    get_task_comments_service,
    get_tasks_service,
    get_wbs_nodes_service,
)
from src.exceptions.dashboard import DashboardServiceError
from src.exceptions.document_links import (
    DocumentLinkAlreadyExistsError,
    DocumentLinkProjectMismatchError,
    DocumentLinksServiceError,
)
from src.exceptions.documents import DocumentSlugConflictError, DocumentsServiceError
from src.exceptions.project_stages import (
    ProjectLastStageDeleteError,
    ProjectStageHasTasksError,
    ProjectStagesServiceError,
)
from src.exceptions.projects import (
    ProjectKeyConflictError,
    ProjectNotFoundError,
    ProjectsServiceError,
)
from src.exceptions.task_activity import TaskActivityServiceError
from src.exceptions.task_comments import TaskCommentNotFoundError, TaskCommentsServiceError
from src.exceptions.tasks import TaskNotFoundError, TasksServiceError
from src.exceptions.wbs_nodes import (
    WbsNodeCycleError,
    WbsNodeForeignProjectError,
    WbsNodeNotFoundError,
    WbsNodesServiceError,
)
from src.services.dashboard import DashboardService
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.project_stages import ProjectStagesService
from src.services.projects import ProjectsService
from src.services.task_activity import TaskActivityService
from src.services.task_comments import TaskCommentsService
from src.services.tasks import TasksService
from src.services.wbs_nodes import WbsNodesService


@pytest.mark.asyncio
async def test_create_project_maps_key_conflict_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectsService)
    service.create_project.side_effect = ProjectKeyConflictError(key="PROJ")
    app.dependency_overrides[get_projects_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects",
        json={"key": "PROJ", "name": "Тестовый проект"},
    )

    assert response.status_code == 409
    assert "PROJ" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_project_maps_missing_project_to_404(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectsService)
    service.get_project.side_effect = ProjectNotFoundError(project_id=999)
    app.dependency_overrides[get_projects_service] = lambda: service

    response = await api_client.get("/api/v1/projects/999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_stage_maps_non_empty_stage_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStagesService)
    service.delete_stage.side_effect = ProjectStageHasTasksError(stage_id=2)
    app.dependency_overrides[get_project_stages_service] = lambda: service

    response = await api_client.delete("/api/v1/stages/2")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_stage_maps_last_stage_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStagesService)
    service.delete_stage.side_effect = ProjectLastStageDeleteError(stage_id=2)
    app.dependency_overrides[get_project_stages_service] = lambda: service

    response = await api_client.delete("/api/v1/stages/2")

    assert response.status_code == 409
    assert "последнюю" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_task_maps_missing_task_to_404(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=TasksService)
    service.get_task.side_effect = TaskNotFoundError(task_id=999)
    app.dependency_overrides[get_tasks_service] = lambda: service

    response = await api_client.get("/api/v1/tasks/999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_comment_maps_missing_comment_to_404(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=TaskCommentsService)
    service.delete_comment.side_effect = TaskCommentNotFoundError(comment_id=999)
    app.dependency_overrides[get_task_comments_service] = lambda: service

    response = await api_client.delete("/api/v1/comments/999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_wbs_node_maps_missing_node_to_404(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsNodesService)
    service.update_node.side_effect = WbsNodeNotFoundError(node_id=999)
    app.dependency_overrides[get_wbs_nodes_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/projects/1/wbs/nodes/999",
        json={"title": "Новое название"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_move_wbs_node_maps_cycle_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsNodesService)
    service.move_node.side_effect = WbsNodeCycleError(node_id=3, parent_id=7)
    app.dependency_overrides[get_wbs_nodes_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/wbs/nodes/3/move",
        json={"parent_id": 7, "before_id": None},
    )

    assert response.status_code == 409
    assert "подраздел" in response.json()["detail"]


@pytest.mark.asyncio
async def test_assign_task_maps_foreign_node_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsNodesService)
    service.assign_task.side_effect = WbsNodeForeignProjectError(node_id=5, project_id=1)
    app.dependency_overrides[get_wbs_nodes_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/wbs/tasks/2/assign",
        json={"wbs_node_id": 5},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_document_maps_slug_conflict_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=DocumentsService)
    service.create_document.side_effect = DocumentSlugConflictError(slug="roadmap")
    app.dependency_overrides[get_documents_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/documents",
        json={"slug": "roadmap", "title": "Roadmap", "content_md": "Текст"},
    )

    assert response.status_code == 409
    assert "roadmap" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_document_link_maps_duplicate_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=DocumentLinksService)
    service.create_link.side_effect = DocumentLinkAlreadyExistsError(document_id=1)
    app.dependency_overrides[get_document_links_service] = lambda: service

    response = await api_client.post(
        "/api/v1/document-links",
        json={"document_id": 1, "task_id": 2},
    )

    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_document_link_maps_project_mismatch_to_409(
    api_client: AsyncClient,
) -> None:
    service = AsyncMock(spec=DocumentLinksService)
    service.create_link.side_effect = DocumentLinkProjectMismatchError(
        document_id=1,
        task_id=2,
    )
    app.dependency_overrides[get_document_links_service] = lambda: service

    response = await api_client.post(
        "/api/v1/document-links",
        json={"document_id": 1, "task_id": 2},
    )

    assert response.status_code == 409
    assert "одного проекта" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dependency", "service_class", "method_name", "error", "http_method", "path"),
    [
        (
            get_dashboard_service,
            DashboardService,
            "get_overview",
            DashboardServiceError("Ошибка сценария"),
            "get",
            "/api/v1/dashboard",
        ),
        (
            get_projects_service,
            ProjectsService,
            "get_project_list",
            ProjectsServiceError("Ошибка сценария"),
            "get",
            "/api/v1/projects",
        ),
        (
            get_project_stages_service,
            ProjectStagesService,
            "get_stage_list",
            ProjectStagesServiceError("Ошибка сценария"),
            "get",
            "/api/v1/projects/1/stages",
        ),
        (
            get_tasks_service,
            TasksService,
            "get_task_list",
            TasksServiceError("Ошибка сценария"),
            "get",
            "/api/v1/projects/1/tasks",
        ),
        (
            get_wbs_nodes_service,
            WbsNodesService,
            "get_structure",
            WbsNodesServiceError("Ошибка сценария"),
            "get",
            "/api/v1/projects/1/wbs",
        ),
        (
            get_documents_service,
            DocumentsService,
            "get_document_list",
            DocumentsServiceError("Ошибка сценария"),
            "get",
            "/api/v1/projects/1/documents",
        ),
        (
            get_document_links_service,
            DocumentLinksService,
            "delete_link",
            DocumentLinksServiceError("Ошибка сценария"),
            "delete",
            "/api/v1/document-links/1",
        ),
        (
            get_task_comments_service,
            TaskCommentsService,
            "get_comments",
            TaskCommentsServiceError("Ошибка сценария"),
            "get",
            "/api/v1/tasks/1/comments",
        ),
        (
            get_task_activity_service,
            TaskActivityService,
            "get_activity",
            TaskActivityServiceError("Ошибка сценария"),
            "get",
            "/api/v1/tasks/1/activity",
        ),
    ],
)
async def test_endpoint_maps_service_error_to_500(
    api_client: AsyncClient,
    dependency: object,
    service_class: type,
    method_name: str,
    error: Exception,
    http_method: str,
    path: str,
) -> None:
    service = AsyncMock(spec=service_class)
    getattr(service, method_name).side_effect = error
    app.dependency_overrides[dependency] = lambda: service

    response = await getattr(api_client, http_method)(path)

    assert response.status_code == 500
    assert response.json()["detail"]
