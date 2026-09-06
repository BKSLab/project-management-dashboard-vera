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


async def test_both_channels_answer_identically_on_every_case() -> None:
    """HTTP и MCP отвечают одинаково: свой проект, чужой, отсутствующий, сбой.

    Каналы проходятся одним тестом, потому что проверяется именно их
    эквивалентность: расхождение любого случая означает, что правило
    доступа где-то скопировано, а не вызвано. Внутри канала чужой и
    несуществующий проект тоже неотличимы — иначе перебором
    идентификаторов выяснялось бы, какие проекты существуют.
    """
    problems: list[str] = []
    for name, answer in sorted(CHANNELS.items()):
        service = access_service()
        if await answer(service, FOREIGN_PROJECT_ID) != await answer(service, MISSING_PROJECT_ID):
            problems.append(f"{name}: чужой и несуществующий проект отличимы")

        status, _ = await answer(access_service(), FOREIGN_PROJECT_ID)
        if status != 404:
            problems.append(f"{name}: чужой проект отвечает {status} вместо 404")

        service = access_service()
        service.members_repository.get.side_effect = None
        service.members_repository.get.return_value = SimpleNamespace(role=ProjectRole.MEMBER)
        status, _ = await answer(service, MEMBER_PROJECT_ID)
        if status != 200:
            problems.append(f"{name}: участник проекта получил {status}")

        service = access_service()
        service.members_repository.get.side_effect = RepositoryError("relation does not exist")
        status, message = await answer(service, FOREIGN_PROJECT_ID)
        if status == 200:
            problems.append(f"{name}: сбой базы открыл доступ")
        if "relation" in message:
            problems.append(f"{name}: наружу вышли подробности запроса к базе")

    assert not problems, "Каналы отвечают по-разному: " + "; ".join(problems)


async def test_both_channels_ask_the_same_service_method() -> None:
    """Решение принимает один и тот же use case, а не копия правила."""
    service = AsyncMock(spec=AccessService)
    service.ensure_project_access.return_value = object()

    await http_answer(service, MEMBER_PROJECT_ID)
    await mcp_answer(service, MEMBER_PROJECT_ID)

    calls = [call.kwargs for call in service.ensure_project_access.await_args_list]

    assert calls == [{"project_id": MEMBER_PROJECT_ID, "user_id": USER_ID}] * 2
