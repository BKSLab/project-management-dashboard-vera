from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import get_task_attachments_service
from src.exceptions.task_attachments import (
    TaskAttachmentNotFoundError,
    TaskAttachmentTooLargeError,
)
from src.schemas.task_attachments import TaskAttachmentSchema
from src.services.task_attachments import TaskAttachmentContent, TaskAttachmentsService


def attachment_schema() -> TaskAttachmentSchema:
    """Возвращает стабильный API-ответ файла задачи."""
    return TaskAttachmentSchema(
        id=4,
        task_id=2,
        original_name="report.pdf",
        content_type="application/pdf",
        size=3,
        created_at=datetime.now(UTC),
        content_url="/api/v1/tasks/2/attachments/4/content",
        previewable=False,
    )


@pytest.mark.asyncio
async def test_upload_task_attachment_accepts_multipart(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=TaskAttachmentsService)
    service.max_file_size = 10 * 1024 * 1024
    service.upload_attachment.return_value = attachment_schema()
    app.dependency_overrides[get_task_attachments_service] = lambda: service

    response = await api_client.post(
        "/api/v1/tasks/2/attachments",
        files={"file": ("report.pdf", b"pdf", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["original_name"] == "report.pdf"
    service.upload_attachment.assert_awaited_once_with(
        task_id=2,
        file_name="report.pdf",
        content_type="application/pdf",
        content=b"pdf",
    )


@pytest.mark.asyncio
async def test_upload_task_attachment_maps_too_large_to_413(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=TaskAttachmentsService)
    service.max_file_size = 10 * 1024 * 1024
    service.upload_attachment.side_effect = TaskAttachmentTooLargeError(max_size_mb=10)
    app.dependency_overrides[get_task_attachments_service] = lambda: service

    response = await api_client.post(
        "/api/v1/tasks/2/attachments",
        files={"file": ("report.pdf", b"pdf", "application/pdf")},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_get_task_attachment_content_streams_inline_image(
    api_client: AsyncClient,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "photo.png"
    image_path.write_bytes(b"image")
    service = AsyncMock(spec=TaskAttachmentsService)
    service.get_attachment_content.return_value = TaskAttachmentContent(
        path=image_path,
        original_name="photo.png",
        content_type="image/png",
        previewable=True,
    )
    app.dependency_overrides[get_task_attachments_service] = lambda: service

    response = await api_client.get("/api/v1/tasks/2/attachments/4/content")

    assert response.status_code == 200
    assert response.content == b"image"
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_delete_task_attachment_maps_missing_file_to_404(
    api_client: AsyncClient,
) -> None:
    service = AsyncMock(spec=TaskAttachmentsService)
    service.delete_attachment.side_effect = TaskAttachmentNotFoundError(attachment_id=999)
    app.dependency_overrides[get_task_attachments_service] = lambda: service

    response = await api_client.delete("/api/v1/tasks/2/attachments/999")

    assert response.status_code == 404
