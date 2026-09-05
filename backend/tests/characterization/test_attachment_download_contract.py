"""Контракт выдачи файла задачи: заголовки, имя файла и коды ответа.

Этап 6 убрал request-scoped DB-сессию из графа этого маршрута: подготовка
идёт в короткой области внутри сервиса. Тело, заголовки и коды ответа при
этом обязаны остаться прежними — здесь они и зафиксированы.
"""

from pathlib import Path
from urllib.parse import unquote

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.scopes import get_attachment_download_service
from src.exceptions.access import ResourceNotAvailableError
from src.exceptions.auth import NotAuthenticatedError
from src.exceptions.task_attachments import (
    TaskAttachmentNotFoundError,
    TaskAttachmentsServiceError,
)
from src.services.attachment_download import AttachmentDownload

FILE_BODY = b"%PDF-1.4 characterization payload"
CONTENT_PATH = "/api/v1/tasks/1/attachments/4/content"


class FakeDownloadService:
    """Подготовка выдачи с заранее заданным результатом."""

    def __init__(self, *, download: AttachmentDownload | None = None, error=None) -> None:
        self.download = download
        self.error = error
        self.calls: list[dict] = []

    async def prepare(self, **kwargs) -> AttachmentDownload:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        assert self.download is not None
        return self.download


@pytest.fixture
def stored_file(tmp_path: Path) -> Path:
    """Физический файл на диске, который отдаёт маршрут."""
    path = tmp_path / "stored.bin"
    path.write_bytes(FILE_BODY)
    return path


def _install(service: FakeDownloadService) -> FakeDownloadService:
    """Ставит двойник подготовки выдачи в граф зависимостей."""
    app.dependency_overrides[get_attachment_download_service] = lambda: service
    return service


async def test_download_returns_file_body_and_filename(
    api_client: AsyncClient,
    stored_file: Path,
) -> None:
    """Скачивание отдаёт байты файла и исходное имя в Content-Disposition."""
    _install(
        FakeDownloadService(
            download=AttachmentDownload(
                path=stored_file,
                media_type="application/pdf",
                filename="Отчёт за август.pdf",
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
        FakeDownloadService(
            download=AttachmentDownload(
                path=stored_file,
                media_type="image/png",
                filename="Схема.png",
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
        FakeDownloadService(
            download=AttachmentDownload(
                path=stored_file,
                media_type="image/png",
                filename="Схема.png",
                previewable=True,
            )
        )
    )

    response = await api_client.get(CONTENT_PATH)

    assert response.headers["x-content-type-options"] == "nosniff"


async def test_missing_attachment_returns_not_found(api_client: AsyncClient) -> None:
    """Отсутствующий файл отвечает 404 с доменной формулировкой."""
    error = TaskAttachmentNotFoundError(attachment_id=4)
    _install(FakeDownloadService(error=error))

    response = await api_client.get(CONTENT_PATH)

    assert response.status_code == 404
    assert response.json() == {"detail": error.detail}


async def test_storage_failure_does_not_leak_internal_details(
    api_client: AsyncClient,
) -> None:
    """Сбой хранилища отвечает 500 и не раскрывает путь на диске."""
    _install(FakeDownloadService(error=TaskAttachmentsServiceError("/srv/uploads/secret.bin")))

    response = await api_client.get(CONTENT_PATH)

    assert response.status_code == 500
    assert "/srv/uploads" not in response.text


async def test_unauthenticated_request_is_rejected(api_client: AsyncClient) -> None:
    """Аутентификация никуда не делась: она выполняется внутри сервиса."""
    error = NotAuthenticatedError()
    _install(FakeDownloadService(error=error))

    response = await api_client.get(CONTENT_PATH)

    assert response.status_code == 401
    assert response.json() == {"detail": error.detail}


async def test_foreign_task_is_not_found(api_client: AsyncClient) -> None:
    """Файл чужой задачи отвечает тем же 404, что и несуществующий."""
    error = ResourceNotAvailableError(resource="Задача", resource_id=1)
    _install(FakeDownloadService(error=error))

    response = await api_client.get(CONTENT_PATH)

    assert response.status_code == 404
    assert response.json() == {"detail": "Объект не найден."}


async def test_credentials_reach_the_preflight(
    api_client: AsyncClient,
    stored_file: Path,
) -> None:
    """Транспорт передаёт в сервис и cookie, и Bearer-секрет.

    Проверка нужна потому, что аутентификация переехала внутрь сервиса:
    если транспорт перестанет передавать учётные данные, маршрут молча
    станет анонимным.
    """
    service = _install(
        FakeDownloadService(
            download=AttachmentDownload(
                path=stored_file,
                media_type="application/pdf",
                filename="Файл.pdf",
                previewable=False,
            )
        )
    )

    await api_client.get(CONTENT_PATH, headers={"Authorization": "Bearer tt_secret"})

    assert service.calls, "Сервис подготовки не был вызван."
    call = service.calls[-1]
    assert call["task_id"] == 1
    assert call["attachment_id"] == 4
    assert call["bearer_secret"] == "tt_secret"
