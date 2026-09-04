from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.db.models.project_stickers import ProjectStickerColor
from src.dependencies.services import get_project_members_service, get_project_stickers_service
from src.exceptions.project_stickers import (
    ProjectStickerNotFoundError,
    ProjectStickerRevisionConflictError,
    ProjectStickerTaskMismatchError,
)
from src.exceptions.projects import ProjectMemberNotFoundError
from src.exceptions.users import AvatarNotFoundError
from src.schemas.project_stickers import ProjectStickerSchema
from src.services.project_members import ProjectMembersService
from src.services.project_stickers import ProjectStickersService


def sticker_schema(*, revision: int = 1) -> ProjectStickerSchema:
    now = datetime.now(UTC)
    return ProjectStickerSchema(
        id=4,
        project_id=1,
        body="Согласовать API",
        color=ProjectStickerColor.YELLOW,
        canvas_x=40.0,
        canvas_y=40.0,
        created_by_user_id=1,
        created_by_username_snapshot="tester",
        created_by_display_name_snapshot="Тестов Тест",
        task_ids=[11],
        revision=revision,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_stickers_returns_contract(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStickersService)
    service.list_stickers.return_value = [sticker_schema()]
    app.dependency_overrides[get_project_stickers_service] = lambda: service

    response = await api_client.get("/api/v1/projects/1/board/stickers")

    assert response.status_code == 200
    assert response.json()[0]["task_ids"] == [11]
    service.list_stickers.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_create_sticker_uses_authenticated_user(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStickersService)
    service.create_sticker.return_value = sticker_schema()
    app.dependency_overrides[get_project_stickers_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/board/stickers",
        json={
            "body": "Согласовать API",
            "color": "yellow",
            "task_ids": [11],
            "canvas_x": 298.5,
            "canvas_y": 42.0,
        },
    )

    assert response.status_code == 201
    call = service.create_sticker.await_args.kwargs
    assert call["project_id"] == 1
    assert call["current_user"].username == "tester"
    assert call["data"].task_ids == [11]
    assert call["data"].canvas_x == 298.5
    assert call["data"].canvas_y == 42.0


@pytest.mark.asyncio
async def test_patch_sticker_passes_revision(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStickersService)
    service.update_sticker.return_value = sticker_schema(revision=3)
    app.dependency_overrides[get_project_stickers_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/projects/1/board/stickers/4",
        json={"revision": 2, "body": "Новый текст", "task_ids": []},
    )

    assert response.status_code == 200
    call = service.update_sticker.await_args.kwargs
    assert call["sticker_id"] == 4
    assert call["data"].revision == 2


@pytest.mark.asyncio
async def test_delete_sticker_passes_revision(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStickersService)
    app.dependency_overrides[get_project_stickers_service] = lambda: service

    response = await api_client.delete("/api/v1/projects/1/board/stickers/4?revision=3")

    assert response.status_code == 204
    service.delete_sticker.assert_awaited_once_with(
        project_id=1,
        sticker_id=4,
        revision=3,
    )


@pytest.mark.asyncio
async def test_move_sticker_passes_canvas_coordinates(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStickersService)
    service.move_sticker.return_value = sticker_schema()
    app.dependency_overrides[get_project_stickers_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/projects/1/board/stickers/4/position",
        json={"canvas_x": 315.25, "canvas_y": -80.0},
    )

    assert response.status_code == 200
    call = service.move_sticker.await_args.kwargs
    assert call["project_id"] == 1
    assert call["sticker_id"] == 4
    assert call["data"].canvas_x == 315.25
    assert call["data"].canvas_y == -80.0


@pytest.mark.asyncio
async def test_move_sticker_rejects_out_of_range_coordinate(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStickersService)
    app.dependency_overrides[get_project_stickers_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/projects/1/board/stickers/4/position",
        json={"canvas_x": 1_000_001, "canvas_y": 0},
    )

    assert response.status_code == 422
    service.move_sticker.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ProjectStickerNotFoundError(4), 404),
        (ProjectStickerRevisionConflictError(4, 2), 409),
        (ProjectStickerTaskMismatchError({99}), 422),
    ],
)
async def test_patch_maps_domain_errors(
    api_client: AsyncClient,
    error: Exception,
    status_code: int,
) -> None:
    service = AsyncMock(spec=ProjectStickersService)
    service.update_sticker.side_effect = error
    app.dependency_overrides[get_project_stickers_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/projects/1/board/stickers/4",
        json={"revision": 2, "body": "Новый текст"},
    )

    assert response.status_code == status_code


@pytest.mark.asyncio
async def test_empty_sticker_is_rejected_before_service(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectStickersService)
    app.dependency_overrides[get_project_stickers_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/board/stickers",
        json={"body": "   "},
    )

    assert response.status_code == 422
    service.create_sticker.assert_not_awaited()


@pytest.mark.asyncio
async def test_project_member_avatar_has_private_cache_headers(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectMembersService)
    service.get_member_avatar.return_value = (b"webp", "image/webp")
    app.dependency_overrides[get_project_members_service] = lambda: service

    response = await api_client.get("/api/v1/projects/1/members/2/avatar")

    assert response.status_code == 200
    assert response.content == b"webp"
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"].startswith("private")


@pytest.mark.asyncio
async def test_removed_member_avatar_returns_not_found(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectMembersService)
    service.get_member_avatar.side_effect = ProjectMemberNotFoundError(user_id=2)
    app.dependency_overrides[get_project_members_service] = lambda: service

    response = await api_client.get("/api/v1/projects/1/members/2/avatar")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_member_without_avatar_returns_not_found(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=ProjectMembersService)
    service.get_member_avatar.side_effect = AvatarNotFoundError(user_id=2)
    app.dependency_overrides[get_project_members_service] = lambda: service

    response = await api_client.get("/api/v1/projects/1/members/2/avatar")

    assert response.status_code == 404
