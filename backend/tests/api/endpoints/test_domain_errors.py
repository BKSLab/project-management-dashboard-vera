from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import (
    get_document_links_service,
    get_documents_service,
    get_kanban_stages_service,
    get_kanban_tasks_service,
    get_task_activity_service,
    get_task_comments_service,
    get_wbs_service,
)
from src.exceptions.document_links import (
    DocumentLinkAlreadyExistsError,
    DocumentLinkInvalidError,
    DocumentLinksServiceError,
)
from src.exceptions.documents import DocumentSlugConflictError, DocumentsServiceError
from src.exceptions.kanban_stages import KanbanStageHasTasksError, KanbanStagesServiceError
from src.exceptions.kanban_tasks import KanbanTasksServiceError
from src.exceptions.task_activity import TaskActivityServiceError
from src.exceptions.task_comments import TaskCommentNotFoundError, TaskCommentsServiceError
from src.exceptions.wbs import WbsCodeConflictError, WbsItemNotFoundError, WbsServiceError
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.kanban_stages import KanbanStagesService
from src.services.kanban_tasks import KanbanTasksService
from src.services.task_activity import TaskActivityService
from src.services.task_comments import TaskCommentsService
from src.services.wbs import WbsService


@pytest.mark.asyncio
async def test_create_document_maps_slug_conflict_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=DocumentsService)
    service.create_document.side_effect = DocumentSlugConflictError(slug="roadmap")
    app.dependency_overrides[get_documents_service] = lambda: service

    response = await api_client.post(
        "/api/v1/documents",
        json={"slug": "roadmap", "title": "Roadmap", "content_md": "Текст"},
    )

    assert response.status_code == 409
    assert "roadmap" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_document_link_maps_invalid_target_to_422(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=DocumentLinksService)
    service.create_link.side_effect = DocumentLinkInvalidError()
    app.dependency_overrides[get_document_links_service] = lambda: service

    response = await api_client.post(
        "/api/v1/document-links",
        json={"document_id": 1, "kanban_task_id": 2, "wbs_item_id": 3},
    )

    assert response.status_code == 422
    assert "ровно одно" in response.json()["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_delete_stage_maps_non_empty_stage_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=KanbanStagesService)
    service.delete_stage.side_effect = KanbanStageHasTasksError(stage_id=2)
    app.dependency_overrides[get_kanban_stages_service] = lambda: service

    response = await api_client.delete("/api/v1/kanban/stages/2")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_comment_maps_missing_comment_to_404(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=TaskCommentsService)
    service.delete_comment.side_effect = TaskCommentNotFoundError(comment_id=999)
    app.dependency_overrides[get_task_comments_service] = lambda: service

    response = await api_client.delete("/api/v1/kanban/comments/999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_wbs_item_maps_missing_item_to_404(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsService)
    service.update_item.side_effect = WbsItemNotFoundError(item_id=999)
    app.dependency_overrides[get_wbs_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/wbs/items/999",
        json={"title": "Новое название"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_document_link_maps_duplicate_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=DocumentLinksService)
    service.create_link.side_effect = DocumentLinkAlreadyExistsError(document_id=1)
    app.dependency_overrides[get_document_links_service] = lambda: service

    response = await api_client.post(
        "/api/v1/document-links",
        json={"document_id": 1, "kanban_task_id": 2},
    )

    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_wbs_item_maps_code_conflict_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsService)
    service.create_item.side_effect = WbsCodeConflictError(code="1")
    app.dependency_overrides[get_wbs_service] = lambda: service

    response = await api_client.post(
        "/api/v1/wbs/items",
        json={"title": "Повторный узел", "phase_name": "Фаза"},
    )

    assert response.status_code == 409
    assert "кодом '1'" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dependency", "service_class", "method_name", "error", "http_method", "path"),
    [
        (
            get_documents_service,
            DocumentsService,
            "get_document_list",
            DocumentsServiceError("Ошибка сценария"),
            "get",
            "/api/v1/documents",
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
            get_kanban_stages_service,
            KanbanStagesService,
            "get_stage_list",
            KanbanStagesServiceError("Ошибка сценария"),
            "get",
            "/api/v1/kanban/stages",
        ),
        (
            get_kanban_tasks_service,
            KanbanTasksService,
            "get_task_list",
            KanbanTasksServiceError("Ошибка сценария"),
            "get",
            "/api/v1/kanban/tasks",
        ),
        (
            get_task_comments_service,
            TaskCommentsService,
            "get_comments",
            TaskCommentsServiceError("Ошибка сценария"),
            "get",
            "/api/v1/kanban/tasks/1/comments",
        ),
        (
            get_task_activity_service,
            TaskActivityService,
            "get_activity",
            TaskActivityServiceError("Ошибка сценария"),
            "get",
            "/api/v1/kanban/tasks/1/activity",
        ),
        (
            get_wbs_service,
            WbsService,
            "get_tree",
            WbsServiceError("Ошибка сценария"),
            "get",
            "/api/v1/wbs/tree",
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
