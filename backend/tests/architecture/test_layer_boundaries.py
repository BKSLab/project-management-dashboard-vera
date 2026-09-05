"""Границы слоёв, проверяемые разбором импортов.

Нарушение границы не ломает ни один сценарный тест: код работает и с
репозиторием внутри эндпоинта. Поэтому единственная защита — статическая
проверка того, что каждый слой видит только соседний снизу.

Сообщение об ошибке называет файл, имя и строку: тест должен объяснять,
что именно нарушено.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
ENDPOINTS = SRC / "api" / "v1" / "endpoints"

# Слой данных: эндпоинт не должен знать о нём вообще.
DATA_LAYER_PREFIXES = ("src.repositories", "src.db", "sqlalchemy")

# Реализации внешних клиентов: эндпоинт работает с сервисом, а не с ними.
CLIENT_MODULES = (
    "src.clients.llm",
    "src.clients.embedding",
    "src.clients.qdrant",
    "src.clients.vision",
)

# Конструкторы, которые разрешено вызывать только в местах сборки графа.
COMPOSITION_MODULES = {
    SRC / "dependencies" / "services.py",
    SRC / "dependencies" / "repositories.py",
    SRC / "dependencies" / "scopes.py",
    SRC / "dependencies" / "storage.py",
    SRC / "dependencies" / "clients.py",
    SRC / "mcp_server" / "services.py",
    SRC / "knowledge" / "runtime.py",
    SRC / "main.py",
}

# Модули, которые ещё собирают репозитории сами. Исключение временное и
# снимается вместе с соответствующим этапом: MCP переходит на сервисный
# слой, worker получает зависимости конструктором.
PENDING_REPOSITORY_BUILDERS = {
    SRC / "mcp_server" / "context.py",
    SRC / "mcp_server" / "server.py",
    SRC / "mcp_server" / "write_tools.py",
    SRC / "knowledge" / "worker.py",
}


def endpoint_files() -> list[Path]:
    """Возвращает модули HTTP-эндпоинтов."""
    return [path for path in sorted(ENDPOINTS.glob("*.py")) if path.name != "__init__.py"]


def imported_modules(path: Path) -> list[tuple[str, int]]:
    """Возвращает импортируемые модули с номерами строк."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
    return found


@pytest.mark.parametrize("path", endpoint_files(), ids=lambda path: path.name)
def test_endpoint_does_not_import_the_data_layer(path: Path) -> None:
    """Эндпоинт не знает ни репозиториев, ни моделей, ни SQLAlchemy.

    Транспорт вызывает сервис и переводит его ошибку в HTTP-ответ. Прямой
    доступ к данным здесь означал бы, что бизнес-правило живёт в
    обработчике запроса.
    """
    offenders = [
        f"{module}:{lineno}"
        for module, lineno in imported_modules(path)
        if module.startswith(DATA_LAYER_PREFIXES)
    ]

    assert not offenders, f"{path.name} импортирует слой данных: {offenders}"


@pytest.mark.parametrize("path", endpoint_files(), ids=lambda path: path.name)
def test_endpoint_does_not_import_client_implementations(path: Path) -> None:
    """Эндпоинт не знает реализаций внешних клиентов."""
    offenders = [
        f"{module}:{lineno}"
        for module, lineno in imported_modules(path)
        if module in CLIENT_MODULES
    ]

    assert not offenders, f"{path.name} импортирует клиента внешней системы: {offenders}"


@pytest.mark.parametrize("path", endpoint_files(), ids=lambda path: path.name)
def test_endpoint_does_not_construct_services(path: Path) -> None:
    """Эндпоинт получает готовый сервис, а не собирает его сам.

    Собранный вручную сервис невозможно подменить через
    `dependency_overrides`, и его зависимости перестают быть видимыми в
    графе приложения.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = [
        f"{node.func.id}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id.endswith(("Service", "Repository"))
    ]

    assert not offenders, f"{path.name} создаёт зависимость напрямую: {offenders}"


@pytest.mark.parametrize(
    "path",
    [path for path in sorted((SRC / "services").glob("*.py")) if path.name != "__init__.py"],
    ids=lambda path: path.name,
)
def test_service_does_not_import_transport(path: Path) -> None:
    """Сервис не знает ни FastAPI, ни слоя зависимостей, ни сессии.

    Импорт FastAPI в сервисе означает, что бизнес-правило описано в
    терминах HTTP и не может быть вызвано из MCP или worker-а.
    """
    forbidden = ("fastapi", "src.dependencies", "src.db.session")
    offenders = [
        f"{module}:{lineno}"
        for module, lineno in imported_modules(path)
        if module.startswith(forbidden)
    ]

    assert not offenders, f"{path.name} импортирует транспортный слой: {offenders}"


def test_repository_constructors_live_only_in_composition_modules() -> None:
    """Репозитории создаются только там, где собирается граф зависимостей.

    Конструктор репозитория в другом месте означает скрытую зависимость
    от сессии: её нельзя ни увидеть в сигнатуре, ни подменить в тесте.
    """
    allowed_dirs = (SRC / "repositories", SRC / "db")
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts or "alembic" in path.parts:
            continue
        if path in COMPOSITION_MODULES or path in PENDING_REPOSITORY_BUILDERS:
            continue
        if any(path.is_relative_to(item) for item in allowed_dirs):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id.endswith("Repository")
            ):
                offenders.append(f"{path.relative_to(SRC.parent)}:{node.lineno} {node.func.id}")

    assert not offenders, (
        "Репозитории создаются вне модулей сборки графа:\n  " + "\n  ".join(offenders)
    )


def test_task_enums_live_in_the_transport_layer() -> None:
    """Приоритет и роль задачи объявлены в слое контракта, а не в модели.

    Эти значения эндпоинт принимает в query-параметрах и отдаёт наружу,
    поэтому брать их из модели базы он не должен. Направление
    зависимости обратное: модель ссылается на общее перечисление.

    Остальные перечисления схем пока приходят из моделей — это
    зафиксированное расхождение, а не проверяемый здесь инвариант:
    массовое переименование выходит за границы задачи.
    """
    enums_source = (SRC / "schemas" / "enums.py").read_text(encoding="utf-8")
    model_source = (SRC / "db" / "models" / "tasks.py").read_text(encoding="utf-8")

    assert "class TaskPriority" in enums_source
    assert "class TaskRole" in enums_source
    assert "class TaskPriority" not in model_source, (
        "Перечисление объявлено в двух местах: значения разойдутся."
    )
    assert "from src.schemas.enums import" in model_source, (
        "Модель должна ссылаться на общее перечисление контракта."
    )


def test_pending_repository_builders_still_need_the_exception() -> None:
    """Временное исключение снимается вместе с переносом границы.

    Если модуль перестал собирать репозитории, он обязан уйти из списка
    отложенных: иначе исключение переживёт причину своего появления и
    перестанет что-либо охранять.
    """
    stale: list[str] = []
    for path in PENDING_REPOSITORY_BUILDERS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        builds = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id.endswith("Repository")
            for node in ast.walk(tree)
        )
        if not builds:
            stale.append(str(path.relative_to(SRC.parent)))

    assert not stale, (
        "Модули больше не собирают репозитории и должны быть убраны из "
        f"PENDING_REPOSITORY_BUILDERS: {stale}"
    )
