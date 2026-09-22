"""Контракты и исполнение разрешённых инструментов проектного агента."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.exceptions.base import ServiceError


@dataclass(frozen=True, slots=True)
class AgentToolContext:
    """Область инструмента, заданная backend, а не аргументами модели."""

    project_id: int
    user_id: int | None
    can_write: bool = False
    message_id: int | None = None
    run_id: UUID | None = None
    request_id: UUID | None = None
    username: str = ""
    display_name: str = ""


class AgentToolRequest(BaseModel):
    """Имя зарегистрированного инструмента и проверяемые аргументы."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(
        min_length=1, max_length=64, description="Имя из реестра доступных инструментов."
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Аргументы по схеме выбранного инструмента."
    )


AgentToolHandler = Callable[[AgentToolContext, BaseModel], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class AgentTool:
    """Схема инструмента и его явно внедрённый обработчик."""

    name: str
    description: str
    parameters: type[BaseModel]
    handler: AgentToolHandler
    mutating: bool = False
    requires_confirmation: bool = False


class AgentToolExecutor:
    """Разрешает только зарегистрированные инструменты с валидными аргументами."""

    def __init__(self, tools: Sequence[AgentTool]) -> None:
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools):
            raise ValueError("Имена инструментов агента должны быть уникальны.")

    def describe(self, *, include_parameters: bool = True) -> list[dict[str, Any]]:
        """Возвращает модели доступные возможности и схемы аргументов."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                **(
                    {"parameters": tool.parameters.model_json_schema()}
                    if include_parameters
                    else {}
                ),
                "mutating": tool.mutating,
                "requires_confirmation": tool.requires_confirmation,
            }
            for tool in self.tools.values()
        ]

    async def execute(self, context: AgentToolContext, request: AgentToolRequest) -> dict[str, Any]:
        """Выполняет инструмент в серверной области проекта.

        Args:
            context: Проверенный проект и инициатор разговора.
            request: Выбор модели без права переопределить область доступа.
        Returns:
            Результат инструмента либо безопасная ошибка для следующего шага модели.
        """
        tool = self.tools.get(request.name)
        if tool is None:
            return {"error": "Инструмент недоступен. Используй список available_tools."}
        if tool.mutating and not context.can_write:
            return {"error": "Текущий запрос не разрешает изменения проекта."}
        try:
            arguments = tool.parameters.model_validate(request.arguments)
        except ValidationError:
            return {"error": "Аргументы инструмента не соответствуют его схеме."}
        try:
            return await tool.handler(context, arguments)
        except ServiceError as error:
            return {"error": error.detail}
