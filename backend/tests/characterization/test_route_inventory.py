"""Инвентарь публичных маршрутов: URL и HTTP-методы заморожены.

Рефакторинг не имеет права добавить, удалить или переименовать маршрут.
Этот тест — единственная защита от такого изменения «по дороге»: он падает
и на исчезнувшем адресе, и на внезапно появившемся.

Классификация non-GET маршрутов используется дальше на этапе 2, где к
каждой доменной мутации подключается проверка scope записи.
"""

from fastapi.routing import APIRoute

from main import app

FROZEN_ROUTES: set[tuple[str, str]] = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/logout"),
    ("GET", "/api/v1/auth/me"),
    ("POST", "/api/v1/auth/register"),
    ("DELETE", "/api/v1/comments/{comment_id}"),
    ("GET", "/api/v1/dashboard"),
    ("GET", "/api/v1/dashboard/analytics"),
    ("POST", "/api/v1/dashboard/analytics"),
    ("POST", "/api/v1/document-links"),
    ("DELETE", "/api/v1/document-links/{link_id}"),
    ("DELETE", "/api/v1/documents/{document_id}"),
    ("GET", "/api/v1/documents/{document_id}"),
    ("PATCH", "/api/v1/documents/{document_id}"),
    ("GET", "/api/v1/documents/{document_id}/links"),
    ("GET", "/api/v1/projects"),
    ("POST", "/api/v1/projects"),
    ("DELETE", "/api/v1/projects/{project_id}"),
    ("GET", "/api/v1/projects/{project_id}"),
    ("PATCH", "/api/v1/projects/{project_id}"),
    ("GET", "/api/v1/projects/{project_id}/board/stickers"),
    ("POST", "/api/v1/projects/{project_id}/board/stickers"),
    ("DELETE", "/api/v1/projects/{project_id}/board/stickers/{sticker_id}"),
    ("PATCH", "/api/v1/projects/{project_id}/board/stickers/{sticker_id}"),
    ("PATCH", "/api/v1/projects/{project_id}/board/stickers/{sticker_id}/position"),
    ("GET", "/api/v1/projects/{project_id}/calendar"),
    ("POST", "/api/v1/projects/{project_id}/calendar/scenarios/apply"),
    ("POST", "/api/v1/projects/{project_id}/calendar/scenarios/preview"),
    ("GET", "/api/v1/projects/{project_id}/calendar/unscheduled"),
    ("GET", "/api/v1/projects/{project_id}/documents"),
    ("POST", "/api/v1/projects/{project_id}/documents"),
    ("POST", "/api/v1/projects/{project_id}/knowledge/ask"),
    ("POST", "/api/v1/projects/{project_id}/knowledge/reindex"),
    ("GET", "/api/v1/projects/{project_id}/knowledge/status"),
    ("GET", "/api/v1/projects/{project_id}/members"),
    ("POST", "/api/v1/projects/{project_id}/members"),
    ("DELETE", "/api/v1/projects/{project_id}/members/{user_id}"),
    ("GET", "/api/v1/projects/{project_id}/members/{user_id}/avatar"),
    ("GET", "/api/v1/projects/{project_id}/milestones"),
    ("POST", "/api/v1/projects/{project_id}/milestones"),
    ("DELETE", "/api/v1/projects/{project_id}/milestones/{milestone_id}"),
    ("PATCH", "/api/v1/projects/{project_id}/milestones/{milestone_id}"),
    ("GET", "/api/v1/projects/{project_id}/stages"),
    ("POST", "/api/v1/projects/{project_id}/stages"),
    ("GET", "/api/v1/projects/{project_id}/stats"),
    ("GET", "/api/v1/projects/{project_id}/task-dependencies"),
    ("POST", "/api/v1/projects/{project_id}/task-dependencies"),
    ("DELETE", "/api/v1/projects/{project_id}/task-dependencies/{dependency_id}"),
    ("GET", "/api/v1/projects/{project_id}/tasks"),
    ("POST", "/api/v1/projects/{project_id}/tasks"),
    ("POST", "/api/v1/projects/{project_id}/tasks/rephrase"),
    ("GET", "/api/v1/projects/{project_id}/wbs"),
    ("POST", "/api/v1/projects/{project_id}/wbs/nodes"),
    ("DELETE", "/api/v1/projects/{project_id}/wbs/nodes/{node_id}"),
    ("PATCH", "/api/v1/projects/{project_id}/wbs/nodes/{node_id}"),
    ("POST", "/api/v1/projects/{project_id}/wbs/nodes/{node_id}/move"),
    ("POST", "/api/v1/projects/{project_id}/wbs/suggestion"),
    ("POST", "/api/v1/projects/{project_id}/wbs/suggestion/apply"),
    ("POST", "/api/v1/projects/{project_id}/wbs/tasks/{task_id}/assign"),
    ("DELETE", "/api/v1/projects/{project_id}/wbs/tasks/{task_id}/assignment"),
    ("POST", "/api/v1/projects/{project_id}/wbs/tasks/{task_id}/placement"),
    ("DELETE", "/api/v1/stages/{stage_id}"),
    ("PATCH", "/api/v1/stages/{stage_id}"),
    ("DELETE", "/api/v1/tasks/{task_id}"),
    ("GET", "/api/v1/tasks/{task_id}"),
    ("PATCH", "/api/v1/tasks/{task_id}"),
    ("GET", "/api/v1/tasks/{task_id}/activity"),
    ("GET", "/api/v1/tasks/{task_id}/attachments"),
    ("POST", "/api/v1/tasks/{task_id}/attachments"),
    ("DELETE", "/api/v1/tasks/{task_id}/attachments/{attachment_id}"),
    ("GET", "/api/v1/tasks/{task_id}/attachments/{attachment_id}/content"),
    ("POST", "/api/v1/tasks/{task_id}/baseline"),
    ("GET", "/api/v1/tasks/{task_id}/comments"),
    ("POST", "/api/v1/tasks/{task_id}/comments"),
    ("POST", "/api/v1/tasks/{task_id}/documents/import"),
    ("GET", "/api/v1/tasks/{task_id}/links"),
    ("PATCH", "/api/v1/tasks/{task_id}/move"),
    ("PATCH", "/api/v1/users/me"),
    ("DELETE", "/api/v1/users/me/avatar"),
    ("GET", "/api/v1/users/me/avatar"),
    ("POST", "/api/v1/users/me/avatar"),
    ("POST", "/api/v1/users/me/password"),
    ("GET", "/api/v1/users/me/tokens"),
    ("POST", "/api/v1/users/me/tokens"),
    ("DELETE", "/api/v1/users/me/tokens/{token_id}"),
}

# Маршруты входа: доступны без аутентификации по определению.
PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/register"),
}

# Управление токенами закрыто для самих токенов: только сессия интерфейса.
SESSION_ONLY_ROUTES: set[tuple[str, str]] = {
    ("POST", "/api/v1/users/me/tokens"),
    ("DELETE", "/api/v1/users/me/tokens/{token_id}"),
}

# POST, которые ничего не меняют: расчёт, предпросмотр и поиск.
READ_ONLY_POST_ROUTES: set[tuple[str, str]] = {
    ("POST", "/api/v1/projects/{project_id}/calendar/scenarios/preview"),
    ("POST", "/api/v1/projects/{project_id}/tasks/rephrase"),
    ("POST", "/api/v1/projects/{project_id}/wbs/suggestion"),
    ("POST", "/api/v1/projects/{project_id}/knowledge/ask"),
}


def _actual_routes() -> set[tuple[str, str]]:
    """Собирает фактический инвентарь маршрутов приложения."""
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            routes.add((method, route.path))
    return routes


def test_route_inventory_is_frozen() -> None:
    """Набор публичных маршрутов не меняется рефакторингом."""
    actual = _actual_routes()

    disappeared = FROZEN_ROUTES - actual
    appeared = actual - FROZEN_ROUTES

    assert not disappeared, f"Маршруты исчезли: {sorted(disappeared)}"
    assert not appeared, f"Появились незадекларированные маршруты: {sorted(appeared)}"


def test_non_get_routes_are_fully_classified() -> None:
    """Каждый изменяющий маршрут отнесён ровно к одному классу доступа.

    Неклассифицированный non-GET маршрут — это маршрут, для которого никто
    не решил, нужен ли ему scope записи. Такой пробел должен ломать сборку.
    """
    non_get = {(method, path) for method, path in FROZEN_ROUTES if method != "GET"}
    explicit = PUBLIC_ROUTES | SESSION_ONLY_ROUTES | READ_ONLY_POST_ROUTES

    overlap = [
        pair
        for pair in explicit
        if sum(pair in group for group in (PUBLIC_ROUTES, SESSION_ONLY_ROUTES, READ_ONLY_POST_ROUTES)) > 1
    ]
    assert not overlap, f"Маршрут попал в несколько классов: {sorted(overlap)}"
    assert explicit <= non_get, f"Классифицирован несуществующий маршрут: {sorted(explicit - non_get)}"

    mutations = non_get - explicit
    assert len(non_get) == 56, f"Изменилось число изменяющих маршрутов: {len(non_get)}"
    assert len(mutations) == 47, f"Изменилось число доменных мутаций: {len(mutations)}"


def test_every_route_has_unique_method_and_path() -> None:
    """Один и тот же метод и путь не объявлены дважды."""
    seen: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            seen.append((method, route.path))

    duplicates = {pair for pair in seen if seen.count(pair) > 1}
    assert not duplicates, f"Дублирующиеся маршруты: {sorted(duplicates)}"
