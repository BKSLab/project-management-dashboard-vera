"""Контракт доменной операции, общий для проектного чата и MCP."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from src.agent.tools import AgentToolContext

if TYPE_CHECKING:
    from src.services.agent_tool_scope import AgentProjectToolScope


@dataclass(frozen=True, slots=True)
class ProjectAction:
    """Явно зарегистрированное действие без динамического доступа к методам."""

    name: str
    title: str
    description: str
    parameters: type[BaseModel]
    handler: Callable[
        ["AgentProjectToolScope", AgentToolContext, BaseModel], Awaitable[dict[str, Any]]
    ]
    mutating: bool = True
    requires_confirmation: bool = False
    owner_only: bool = False
