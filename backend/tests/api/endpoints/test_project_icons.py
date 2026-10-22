"""HTTP-контур картинки проекта: multipart, лимит размера, кеш и приватность ссылки."""

from pathlib import Path
from unittest.mock import AsyncMock

from httpx import AsyncClient

from main import app
from src.dependencies.services import get_project_icons_service
from src.exceptions.projects import ProjectIconImageInvalidError, ProjectIconImageNotFoundError
from src.services.project_icons import ProjectIconImage, ProjectIconsService

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def install() -> AsyncMock:
    service = AsyncMock(spec=ProjectIconsService)
    app.dependency_overrides[get_project_icons_service] = lambda: service
    return service


async def test_editor_uploads_and_oversize_or_svg_is_rejected(api_client: AsyncClient) -> None:
    service = install()
    service.upload.side_effect = ProjectIconImageInvalidError("svg")
    svg = await api_client.post(
        "/api/v1/projects/1/icon-image", files={"file": ("a.svg", b"<svg/>", "image/svg+xml")}
    )
    assert svg.status_code == 422
    assert svg.json()["detail"] == "Картинка проекта — только PNG, JPG или WebP до 2 МБ."
    service.upload.assert_awaited_once_with(
        project_id=1, content=b"<svg/>"
    )

    service.upload.reset_mock()
    big = await api_client.post(
        "/api/v1/projects/1/icon-image",
        files={"file": ("big.png", PNG + b"\x00" * (2 * 1024 * 1024), "image/png")},
    )
    assert big.status_code == 413
    service.upload.assert_not_awaited()


async def test_icon_image_is_served_privately_with_long_cache(
    api_client: AsyncClient, tmp_path: Path
) -> None:
    service = install()
    image = tmp_path / "icon.png"
    image.write_bytes(PNG)
    service.get.return_value = ProjectIconImage(
        content=PNG, content_type="image/png"
    )

    response = await api_client.get("/api/v1/projects/1/icon-image?v=abc")

    assert response.status_code == 200 and response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert response.headers["x-content-type-options"] == "nosniff"

    service.get.side_effect = ProjectIconImageNotFoundError(project_id=1)
    assert (await api_client.get("/api/v1/projects/1/icon-image")).status_code == 404
