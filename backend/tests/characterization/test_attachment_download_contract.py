"""Контракт выдачи файла задачи: заголовки, имя файла и коды ответа.

Этап 6 убирает request-scoped DB-сессию из графа этого маршрута. Тело,
заголовки и коды ответа при этом обязаны остаться прежними — здесь они и
зафиксированы.
"""

from pathlib import Path
from urllib.parse import unquote

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import get_task_attachments_service
from src.exceptions.task_attachments import (
    TaskAttachmentNotFoundError,
    TaskAttachmentsServiceError,
)
from src.services.task_attachments import TaskAttachmentContent

FILE_BODY = b"%PDF-1.4 characterization payload"
CONTENT_PATH = "/api/v1/tasks/1/attachments/4/content"


class FakeAttachmentsService:
    """Сервис файлов задач с заранее подготовленным результатом."""

    def __init__(self, *, content: TaskAttachmentContent | None = None, error=None) -> None:
        self.content = content
        self.error = error
        self.max_file_size = 10 * 1024 * 1024

    async def get_attachment_content(
        self,
        *,
        task_id: int,
        attachment_id: int,
    ) -> TaskAttachmentContent:
        if self.error is not None:
            raise self.error
        assert self.content is not None
        return self.content


@pytest.fixture
def stored_file(tmp_path: Path) -> Path:
    """Физический файл на диске, который отдаёт маршрут."""
    path = tmp_path / "stored.bin"
    path.write_bytes(FILE_BODY)
    return path


def _install(service: FakeAttachmentsService) -> None:
    """Ставит двойник сервиса файлов в граф зависимостей."""
    app.dependency_overrides[get_task_attachments_service] = lambda: service


async def test_download_returns_file_body_and_filename(
    api_client: AsyncClient,
    stored_file: Path,
) -> None:
    """Скачивание отдаёт байты файла и исходное имя в Content-Disposition."""
    _install(
        FakeAttachmentsService(
            content=TaskAttachmentContent(
                path=stored_file,
                original_name="Отчёт за август.pdf",
                content_type="application/pdf",
                previewable=False,
            )
        )
    )

    response = await api_client.get(CONTENT_PATH)

    assert response.status_code == 200
    assert response.content == FILE_BODY
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "Отчёт за август.pdf" in unquote(disposition)


async def test_previewable_file_is_served_inline(
    api_client: AsyncClient,
    stored_file: Path,
) -> None:
    """Безопасное изображение показывается inline, а не скачивается."""
    _install(
        FakeAttachmentsService(
            content=TaskAttachmentContent(
                path=stored_file,
                original_name="Схема.png",
                content_type="image/png",
                previewable=True,
            )
        )
    )

    response = await api_client.get(CONTENT_PATH)

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["content-type"] == "image/png"


async def test_download_always_sets_nosniff(
    api_client: AsyncClient,
    stored_file: Path,
) -> None:
    """Заголовок ``nosniff`` обязателен: браузер не должен угадывать тип."""
    _install(
        FakeAttachmentsService(
            content=TaskAttachmentContent(
                path=stored_file,
                original_name="Схема.png",
                content_type="image/png",
                previewable=True,
            )
        )
    )

    response = await api_client.get(CONTENT_PATH)

    assert response.headers["x-content-type-options"] == "nosniff"


async def test_missing_attachment_returns_not_found(api_client: AsyncClient) -> None:
    """Отсутствующий файл отвечает 404 с доменной формулировкой."""
    error = TaskAttachmentNotFoundError(attachment_id=4)
    _install(FakeAttachmentsService(error=error))

    response = await api_client.get(CONTENT_PATH)

    assert response.status_code == 404
    assert response.json() == {"detail": error.detail}


async def test_storage_failure_does_not_leak_internal_details(
    api_client: AsyncClient,
) -> None:
    """Сбой хранилища отвечает 500 и не раскрывает путь на диске."""
    _install(FakeAttachmentsService(error=TaskAttachmentsServiceError("/srv/uploads/secret.bin")))

    response = await api_client.get(CONTENT_PATH)

    assert response.status_code == 500
    assert "/srv/uploads" not in response.text
