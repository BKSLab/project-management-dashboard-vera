"""Смысловой поиск MCP: соединение с БД не удерживается внешним вызовом.

Обращение к эмбеддингам и Qdrant идёт по сети и занимает секунды. Если
делать его внутри области сессии, соединение с PostgreSQL всё это время
остаётся занятым, и пул исчерпывается на нескольких параллельных вызовах.
Поэтому здесь проверяется порядок: аутентификация и доступ — в короткой
области, внешний вызов — после её закрытия.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from src.core.app_state import (
    RUNTIME_STATE_KEY,
    SESSION_FACTORY_STATE_KEY,
    SETTINGS_STATE_KEY,
)
from src.exceptions.clients import ClientError
from src.mcp_server import context as ctx
from src.mcp_server import server as srv
from tests.unit.mcp_server.conftest import PROJECT_ID, make_principal, make_services


class ScopeTracker:
    """Фабрика сессий, помнящая, открыта ли сейчас область работы с БД."""

    def __init__(self) -> None:
        self.active = False
        self.opened = 0

    def __call__(self) -> "ScopeTracker":
        return self

    async def __aenter__(self) -> object:
        self.active = True
        self.opened += 1
        return object()

    async def __aexit__(self, *exc_info) -> bool:
        self.active = False
        return False


class RecordingRuntime:
    """Клиенты знаний, фиксирующие состояние DB-области в момент вызова."""

    def __init__(self, tracker: ScopeTracker, hits: list) -> None:
        self.tracker = tracker
        self.scope_active_during_call: list[bool] = []
        self.embedding_client = SimpleNamespace(get_embedding=self._embedding)
        self.qdrant_client = SimpleNamespace(search=self._search)
        self._hits = hits

    async def _embedding(self, text: str) -> list[float]:
        self.scope_active_during_call.append(self.tracker.active)
        return [0.1, 0.2]

    async def _search(self, **kwargs) -> list:
        self.scope_active_during_call.append(self.tracker.active)
        self.search_kwargs = kwargs
        return self._hits


class SearchContext:
    """Контекст вызова со state приложения и включённой базой знаний."""

    def __init__(self, runtime: object, tracker: ScopeTracker) -> None:
        self.headers = {"Authorization": "Bearer tt_test"}
        state = SimpleNamespace(
            **{
                RUNTIME_STATE_KEY: runtime,
                SETTINGS_STATE_KEY: SimpleNamespace(
                    knowledge=SimpleNamespace(
                        knowledge_enabled=True,
                        qdrant_score_threshold=0.42,
                    )
                ),
                SESSION_FACTORY_STATE_KEY: tracker,
            }
        )
        self.request_context = SimpleNamespace(request=SimpleNamespace(state=state))


def hit(entity_type: str = "task", **overrides) -> SimpleNamespace:
    """Фрагмент ответа Qdrant."""
    payload = {
        "source_id": "task:100",
        "entity_type": entity_type,
        "task_key": "PROJ-142",
        "title": "Собрать отчёт",
        "text": "Решили считать отчёт по фактическим датам.",
    }
    payload.update(overrides)
    return SimpleNamespace(payload=payload, score=0.876_8)


@pytest.fixture
def search(monkeypatch: pytest.MonkeyPatch):
    """Готовит вызов инструмента с отслеживаемой областью сессии."""

    def install(hits: list | None = None):
        services = make_services()
        services.auth.resolve_principal.return_value = make_principal()
        monkeypatch.setattr(ctx, "build_tool_services", lambda **_: services)

        tracker = ScopeTracker()
        runtime = RecordingRuntime(tracker, [] if hits is None else hits)
        return SearchContext(runtime, tracker), tracker, runtime, services

    return install


async def test_external_call_happens_after_the_db_scope_is_closed(search) -> None:
    """Эмбеддинг и Qdrant вызываются уже без открытого соединения с БД."""
    context, tracker, runtime, _ = search([hit()])

    await srv.search_project_knowledge(context, project_key="PROJ", query="отчёт")

    assert runtime.scope_active_during_call == [False, False]
    assert tracker.opened == 1
    assert tracker.active is False


async def test_access_is_checked_inside_the_db_scope(search) -> None:
    """Доступ проверяется до внешнего вызова и внутри короткой области."""
    context, _, runtime, services = search([hit()])

    await srv.search_project_knowledge(context, project_key="proj", query="отчёт")

    services.access.ensure_project_access.assert_awaited_once_with(
        project_id=PROJECT_ID,
        user_id=1,
    )
    assert runtime.search_kwargs["project_id"] == PROJECT_ID
    assert runtime.search_kwargs["score_threshold"] == 0.42


async def test_disabled_knowledge_does_not_reach_external_clients(search) -> None:
    """При выключенной базе знаний внешние клиенты не вызываются."""
    context, _, runtime, _ = search()
    context.request_context.request.state.app_settings.knowledge.knowledge_enabled = False

    with pytest.raises(ToolError) as error:
        await srv.search_project_knowledge(context, project_key="PROJ", query="отчёт")

    assert "отключён" in str(error.value)
    assert runtime.scope_active_during_call == []


async def test_entity_type_filter_is_applied_to_hits(search) -> None:
    """Фильтр по типу сущности отсеивает лишние фрагменты."""
    context, _, _, _ = search([hit("task"), hit("document")])

    result = await srv.search_project_knowledge(
        context,
        project_key="PROJ",
        query="отчёт",
        entity_type=" Document ",
    )

    assert [item["entity_type"] for item in result] == ["document"]


async def test_hit_is_presented_with_display_key_and_rounded_score(search) -> None:
    """Фрагмент отдаётся ключом задачи и округлённой оценкой."""
    context, _, _, _ = search([hit()])

    result = await srv.search_project_knowledge(context, project_key="PROJ", query="отчёт")

    assert result == [
        {
            "source": "task:100",
            "entity_type": "task",
            "task_key": "PROJ-142",
            "title": "Собрать отчёт",
            "score": 0.877,
            "excerpt": "Решили считать отчёт по фактическим датам.",
        }
    ]


async def test_client_failure_becomes_a_tool_error(search) -> None:
    """Сбой внешнего клиента не выносит наружу деталей интеграции."""
    context, _, runtime, _ = search()
    runtime.embedding_client.get_embedding = AsyncMock(side_effect=ClientError("qdrant 503"))

    with pytest.raises(ToolError) as error:
        await srv.search_project_knowledge(context, project_key="PROJ", query="отчёт")

    assert str(error.value) == "Семантический поиск временно недоступен."
    assert "503" not in str(error.value)
