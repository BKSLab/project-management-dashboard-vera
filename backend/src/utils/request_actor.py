"""Кто выполняет текущий запрос — для подписи записей истории задачи.

История задачи пишется в одном месте (``TaskActivityRepository.save``), но
вызывают её десятки сценариев из REST, MCP и проектного агента. Протащить
автора параметром через каждый сценарий — значит однажды забыть его в
новом. Поэтому автор кладётся в переменную контекста там, где запрос
аутентифицирован (HTTP-зависимость и контекст инструмента MCP), а
репозиторий истории читает его при записи.

Переменная контекста изолирована по задаче asyncio: параллельные запросы
друг друга не видят. Нет значения — событие пишется без автора, как раньше.
"""

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestActor:
    """Автор изменений текущего запроса.

    Attributes:
        user_id: Пользователь, от чьего имени идёт запрос.
        name: Его имя для подписи в истории.
        via_api_key_label: Имя сервисного ключа, если запрос пришёл через него.
    """

    user_id: int
    name: str
    via_api_key_label: str | None = None


_current_actor: ContextVar[RequestActor | None] = ContextVar("request_actor", default=None)


def set_request_actor(actor: RequestActor | None) -> Token:
    """Запоминает автора текущего запроса.

    Returns:
        Маркер для восстановления прежнего значения.
    """
    return _current_actor.set(actor)


def reset_request_actor(token: Token) -> None:
    """Возвращает значение, бывшее до ``set_request_actor``."""
    _current_actor.reset(token)


def current_request_actor() -> RequestActor | None:
    """Возвращает автора текущего запроса либо ``None``."""
    return _current_actor.get()
