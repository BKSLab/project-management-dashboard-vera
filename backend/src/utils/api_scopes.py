"""Общие права HTTP, агента и MCP; они сужают доступ локального владельца."""

from typing import Final

SCOPE_BOARDS_READ: Final = "boards:read"
SCOPE_BOARDS_WRITE: Final = "boards:write"
SCOPE_PROJECTS_READ: Final = "projects:read"
SCOPE_PROJECTS_WRITE: Final = "projects:write"
SCOPE_TASKS_READ: Final = "tasks:read"
SCOPE_TASKS_WRITE: Final = "tasks:write"
SCOPE_TASKS_DELETE: Final = "tasks:delete"
SCOPE_COMMENTS_WRITE: Final = "comments:write"
SCOPE_KNOWLEDGE_READ: Final = "knowledge:read"
SCOPE_STRUCTURE_READ: Final = "structure:read"
SCOPE_STRUCTURE_WRITE: Final = "structure:write"
SCOPE_AGENT_ASK: Final = "agent:ask"

API_SCOPES: Final[dict[str, str]] = {
    SCOPE_BOARDS_READ: "Читать доступные доски и их содержимое.",
    SCOPE_BOARDS_WRITE: "Создавать и изменять свои и доступные проектные доски.",
    SCOPE_PROJECTS_READ: "Читать доступные проекты, участников, календарь и риски.",
    SCOPE_PROJECTS_WRITE: "Создавать и изменять проекты в пределах доступа владельца.",
    SCOPE_TASKS_READ: "Читать задачи, комментарии, отчёты, историю и вложения.",
    SCOPE_TASKS_WRITE: "Создавать и изменять задачи, сроки, назначения и отчёты.",
    SCOPE_TASKS_DELETE: "Удалять задачи вместе с их содержимым.",
    SCOPE_COMMENTS_WRITE: "Добавлять и изменять комментарии к доступным задачам.",
    SCOPE_KNOWLEDGE_READ: "Искать и читать доступные источники знаний.",
    SCOPE_STRUCTURE_READ: "Читать ИСР доступных проектов.",
    SCOPE_STRUCTURE_WRITE: "Изменять разделы ИСР и размещение задач.",
    SCOPE_AGENT_ASK: "Задавать вопросы по доступным владельцу данным; запись требует отдельных прав.",
}
WRITE_SCOPES: Final = frozenset(
    {
        SCOPE_BOARDS_WRITE,
        SCOPE_PROJECTS_WRITE,
        SCOPE_TASKS_WRITE,
        SCOPE_TASKS_DELETE,
        SCOPE_COMMENTS_WRITE,
        SCOPE_STRUCTURE_WRITE,
    }
)
READ_SCOPES: Final = frozenset(API_SCOPES) - WRITE_SCOPES
PERSONAL_SCOPES: Final = frozenset(API_SCOPES)


def unknown_scopes(scopes: list[str]) -> list[str]:
    return sorted(set(scopes) - API_SCOPES.keys())


def personal_scopes(scopes: list[str]) -> list[str]:
    return unknown_scopes(scopes)
