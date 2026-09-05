"""Одинаковые сценарии доступа дают эквивалентный результат в HTTP и MCP.

До этапа 8 MCP проверял доступ собственным кодом: он сам читал участников
проекта и сам решал, что показывать. Две реализации одного правила
расходятся молча — расхождение видно только по итоговому ответу канала.

Здесь оба канала получают один и тот же `AccessService` и один и тот же
принципал. Проверяется не текст сообщений (он разный по формату канала),
а то, что решение принято одним сервисом и что внутри каждого канала
чужой и несуществующий проект неотличимы.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ToolError

from src.db.models.api_tokens import ApiTokenScope
from src.db.models.project_members import ProjectRole
from src.dependencies.access import require_project_access
from src.exceptions.base import RepositoryError
from src.mcp_server.context import ToolContext, ensure_project_access
from src.repositories.project_members import ProjectMembersRepository
from src.services.access import AccessService
from src.services.auth import Principal

USER_ID = 1
MEMBER_PROJECT_ID = 1
FOREIGN_PROJECT_ID = 42
MISSING_PROJECT_ID = 99


def principal() -> Principal:
    """Владелец вызова, одинаковый для обоих каналов."""
    return Principal(
        user_id=USER_ID,
        username="characterization",
        last_name="Тестов",
        first_name="Тест",
        middle_name=None,
        scope=ApiTokenScope.READ,
        via_api_token=True,
    )


def access_service() -> AccessService:
    """Сервис доступа: пользователь состоит только в своём проекте.

    Чужой проект существует, несуществующий — нет. Для сервиса это один
    и тот же ответ: участия нет.
    """
    members = AsyncMock(spec=ProjectMembersRepository)
    members.get.side_effect = lambda *, project_id, user_id: None
    return AccessService(
        members_repository=members,
        tasks_repository=AsyncMock(),
        stages_repository=AsyncMock(),
        documents_repository=AsyncMock(),
        comments_repository=AsyncMock(),
        links_repository=AsyncMock(),
    )


async def http_answer(service: AccessService, project_id: int) -> tuple[int, str]:
    """Ответ HTTP-канала на запрос доступа к проекту."""
    try:
        await require_project_access(
            project_id=project_id,
            principal=principal(),
            service=service,
        )
    except HTTPException as error:
        return error.status_code, str(error.detail)
    return 200, "доступ разрешён"


async def mcp_answer(service: AccessService, project_id: int) -> tuple[int, str]:
    """Ответ MCP-канала на тот же запрос доступа."""
    tools = ToolContext(
        principal=principal(),
        services=AsyncMock(access=service),
        runtime=AsyncMock(),
        settings=AsyncMock(),
    )
    try:
        await ensure_project_access(tools, project_id)
    except ToolError as error:
        return 404, str(error)
    return 200, "доступ разрешён"


CHANNELS = {"http": http_answer, "mcp": mcp_answer}


@pytest.mark.parametrize("channel", sorted(CHANNELS), ids=sorted(CHANNELS))
async def test_foreign_and_missing_project_are_indistinguishable(channel: str) -> None:
    """Внутри канала чужой и несуществующий проект отвечают одинаково.

    Разные ответы позволили бы перебором идентификаторов узнать, какие
    проекты существуют в системе.
    """
    service = access_service()
    answer = CHANNELS[channel]

    assert await answer(service, FOREIGN_PROJECT_ID) == await answer(service, MISSING_PROJECT_ID)


@pytest.mark.parametrize("channel", sorted(CHANNELS), ids=sorted(CHANNELS))
async def test_both_channels_deny_access_to_a_foreign_project(channel: str) -> None:
    """Отказ одинаково означает «не найдено» в обоих каналах."""
    status, _ = await CHANNELS[channel](access_service(), FOREIGN_PROJECT_ID)

    assert status == 404


@pytest.mark.parametrize("channel", sorted(CHANNELS), ids=sorted(CHANNELS))
async def test_both_channels_allow_access_to_own_project(channel: str) -> None:
    """Участник проекта проходит проверку в обоих каналах."""
    service = access_service()
    service.members_repository.get.side_effect = None
    service.members_repository.get.return_value = SimpleNamespace(role=ProjectRole.MEMBER)

    status, _ = await CHANNELS[channel](service, MEMBER_PROJECT_ID)

    assert status == 200


@pytest.mark.parametrize("channel", sorted(CHANNELS), ids=sorted(CHANNELS))
async def test_repository_failure_does_not_leak_into_either_channel(channel: str) -> None:
    """Сбой чтения участников не выглядит как разрешённый доступ.

    Ошибка инфраструктуры не должна ни открывать проект, ни выносить
    наружу подробности запроса к базе.
    """
    service = access_service()
    service.members_repository.get.side_effect = RepositoryError("relation does not exist")

    status, message = await CHANNELS[channel](service, FOREIGN_PROJECT_ID)

    assert status != 200
    assert "relation" not in message


async def test_both_channels_ask_the_same_service_method() -> None:
    """Решение принимает один и тот же use case, а не копия правила."""
    service = AsyncMock(spec=AccessService)
    service.ensure_project_access.return_value = object()

    await http_answer(service, MEMBER_PROJECT_ID)
    await mcp_answer(service, MEMBER_PROJECT_ID)

    calls = [call.kwargs for call in service.ensure_project_access.await_args_list]

    assert calls == [{"project_id": MEMBER_PROJECT_ID, "user_id": USER_ID}] * 2
