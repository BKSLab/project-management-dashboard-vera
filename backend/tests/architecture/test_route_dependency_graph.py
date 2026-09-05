"""Проверки собранного графа зависимостей приложения.

Забытый write scope на новом маршруте не ломает ни один сценарный тест: он
просто тихо разрешает READ-токену изменять данные. Единственная защита —
обход `route.dependant` у собранного приложения.

Классификация хранится множествами конкретных `(метод, путь)`, а не
правилом «любой POST — запись»: часть POST логически read-only, и решение о
каждом из них должно быть принято человеком, а не выведено из метода.
"""

from fastapi.routing import APIRoute

from main import app

# Маршруты входа: доступны без аутентификации по определению.
PUBLIC_ROUTES = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/register"),
}

# Управление токенами закрыто для самих токенов: скомпрометированный токен
# не должен уметь выпустить себе замену и отозвать чужие.
SESSION_ONLY_ROUTES = {
    ("POST", "/api/v1/users/me/tokens"),
    ("DELETE", "/api/v1/users/me/tokens/{token_id}"),
}

# POST, которые ничего не меняют: расчёт, предпросмотр и поиск.
READ_ONLY_POST_ROUTES = {
    ("POST", "/api/v1/projects/{project_id}/calendar/scenarios/preview"),
    ("POST", "/api/v1/projects/{project_id}/tasks/rephrase"),
    ("POST", "/api/v1/projects/{project_id}/wbs/suggestion"),
    ("POST", "/api/v1/projects/{project_id}/knowledge/ask"),
}

EXPECTED_NON_GET_TOTAL = 56
EXPECTED_MUTATION_TOTAL = 47


def route_dependencies(route: APIRoute) -> set[str]:
    """Возвращает имена всех зависимостей маршрута, включая транзитивные."""
    names: set[str] = set()

    def walk(dependant) -> None:
        if dependant.call is not None:
            names.add(getattr(dependant.call, "__name__", ""))
        for sub in dependant.dependencies:
            walk(sub)

    walk(route.dependant)
    return names


def api_routes() -> list[tuple[str, str, APIRoute]]:
    """Перечисляет маршруты приложения парами метод и путь."""
    rows: list[tuple[str, str, APIRoute]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            rows.append((method, route.path, route))
    return rows


def non_get_routes() -> list[tuple[str, str, APIRoute]]:
    """Перечисляет изменяющие по методу маршруты приложения."""
    return [row for row in api_routes() if row[0] != "GET"]


def mutation_routes() -> list[tuple[str, str, APIRoute]]:
    """Перечисляет доменные мутации: всё, кроме явных исключений."""
    explicit = PUBLIC_ROUTES | SESSION_ONLY_ROUTES | READ_ONLY_POST_ROUTES
    return [row for row in non_get_routes() if (row[0], row[1]) not in explicit]


def test_every_non_get_route_is_classified() -> None:
    """Каждый изменяющий по методу маршрут отнесён к известному классу.

    Новый неклассифицированный маршрут ломает тест: решение о его правах
    должно быть принято явно, а не унаследовано по умолчанию.
    """
    actual = {(method, path) for method, path, _ in non_get_routes()}
    explicit = PUBLIC_ROUTES | SESSION_ONLY_ROUTES | READ_ONLY_POST_ROUTES

    unknown_declared = explicit - actual
    assert not unknown_declared, f"Классифицированы несуществующие маршруты: {unknown_declared}"
    assert len(actual) == EXPECTED_NON_GET_TOTAL, (
        f"Изменилось число изменяющих маршрутов: {len(actual)} вместо {EXPECTED_NON_GET_TOTAL}. "
        "Обнови классификацию вместе с маршрутом."
    )


def test_route_counts_match_the_declared_inventory() -> None:
    """Число доменных мутаций совпадает с зафиксированным инвентарём."""
    assert len(mutation_routes()) == EXPECTED_MUTATION_TOTAL


def test_every_mutation_requires_write_scope() -> None:
    """READ-токен не может выполнить ни одну доменную мутацию."""
    unprotected = [
        f"{method} {path}"
        for method, path, route in mutation_routes()
        if "require_write_scope" not in route_dependencies(route)
    ]

    assert not unprotected, (
        "Маршруты изменяют данные без проверки scope записи:\n  " + "\n  ".join(sorted(unprotected))
    )


def test_read_only_posts_do_not_require_write_scope() -> None:
    """Расчёт и предпросмотр остаются доступны токену на чтение."""
    wrongly_protected = [
        f"{method} {path}"
        for method, path, route in api_routes()
        if (method, path) in READ_ONLY_POST_ROUTES
        and "require_write_scope" in route_dependencies(route)
    ]

    assert not wrongly_protected, (
        "Логически read-only маршруты требуют право записи:\n  "
        + "\n  ".join(sorted(wrongly_protected))
    )


def test_get_routes_never_require_write_scope() -> None:
    """Чтение не требует права записи ни на одном маршруте."""
    wrongly_protected = [
        f"{method} {path}"
        for method, path, route in api_routes()
        if method == "GET" and "require_write_scope" in route_dependencies(route)
    ]

    assert not wrongly_protected, (
        "Чтение требует право записи:\n  " + "\n  ".join(sorted(wrongly_protected))
    )


def test_public_routes_have_no_authentication() -> None:
    """Маршруты входа не требуют уже открытой сессии."""
    wrongly_guarded = [
        f"{method} {path}"
        for method, path, route in api_routes()
        if (method, path) in PUBLIC_ROUTES and "get_principal" in route_dependencies(route)
    ]

    assert not wrongly_guarded, f"Маршруты входа закрыты аутентификацией: {wrongly_guarded}"


def test_session_only_routes_are_closed_for_tokens() -> None:
    """Управление токенами защищено guard сессии, а не scope записи."""
    for method, path, route in api_routes():
        if (method, path) not in SESSION_ONLY_ROUTES:
            continue
        deps = route_dependencies(route)
        assert "require_session" in deps, f"{method} {path} не закрыт guard сессии."
        assert "require_write_scope" not in deps, (
            f"{method} {path} использует scope записи вместо guard сессии."
        )


def test_every_protected_route_authenticates() -> None:
    """Ни один непубличный маршрут не обходит аутентификацию."""
    unauthenticated = [
        f"{method} {path}"
        for method, path, route in api_routes()
        if (method, path) not in PUBLIC_ROUTES and "get_principal" not in route_dependencies(route)
    ]

    assert not unauthenticated, (
        "Маршруты доступны без аутентификации:\n  " + "\n  ".join(sorted(unauthenticated))
    )


def test_project_scoped_routes_check_project_access() -> None:
    """Маршрут внутри проекта проверяет доступ к этому проекту."""
    guards = {
        "require_project_access",
        "require_project_ownership",
        "require_task_access",
        "require_stage_access",
        "require_document_access",
        "require_comment_access",
        "require_link_access",
    }
    unguarded = [
        f"{method} {path}"
        for method, path, route in api_routes()
        if "{project_id}" in path and not (route_dependencies(route) & guards)
    ]

    assert not unguarded, (
        "Маршруты проекта не проверяют доступ:\n  " + "\n  ".join(sorted(unguarded))
    )


def test_access_guards_do_not_leak_orm_models() -> None:
    """Guard доступа возвращает разрешение, а не персистентную модель."""
    from src.dependencies import access
    from src.services.access import AccessGrant

    guards = [
        access.require_project_access,
        access.require_project_ownership,
        access.require_task_access,
        access.require_stage_access,
        access.require_document_access,
        access.require_comment_access,
        access.require_link_access,
    ]
    for guard in guards:
        assert guard.__annotations__["return"] is AccessGrant, (
            f"{guard.__name__} возвращает не AccessGrant."
        )
