"""Архитектурные ограничители графа зависимостей.

Правила проверяются разбором исходников: забытый `get_settings()` в
сервисе или вернувшийся глобальный runtime не ломают ни один сценарный
тест, поэтому единственная защита от их возвращения — статический guard.

Тест сообщает точный файл и строку: сообщение об ошибке должно объяснять,
что именно нарушено, а не только факт нарушения.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"

# Чтение глобальных настроек допустимо только в точке сборки приложения.
SETTINGS_ALLOWLIST = {
    SRC / "core" / "settings.py",
    SRC / "db" / "session.py",
    SRC / "main.py",
    SRC / "dependencies" / "settings.py",
    SRC / "dependencies" / "storage.py",
    SRC / "core" / "config_logger.py",
    SRC / "db" / "alembic" / "env.py",
    SRC / "utils" / "tokens.py",
    SRC / "utils" / "check_db.py",
}

# Временно разрешённые точки чтения настроек: они убираются вместе с
# переносом соответствующей границы и должны исчезнуть из этого списка.
PENDING_SETTINGS_READERS = {
    # Этап 2: auth-зависимость становится тонким transport-адаптером.
    SRC / "dependencies" / "auth.py",
    # Этап 7: cookie policy передаётся явной transport-зависимостью.
    SRC / "api" / "v1" / "endpoints" / "auth.py",
}


def iter_python_files(*relative: str) -> list[Path]:
    """Возвращает исходные файлы указанных пакетов без кеша интерпретатора."""
    files: list[Path] = []
    for part in relative:
        root = SRC / part
        target = [root] if root.is_file() else sorted(root.rglob("*.py"))
        files.extend(path for path in target if "__pycache__" not in path.parts)
    return files


def calls_named(tree: ast.AST, name: str) -> list[int]:
    """Возвращает номера строк, где вызывается функция с данным именем."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == name:
            lines.append(node.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == name:
            lines.append(node.lineno)
    return lines


@pytest.mark.parametrize(
    "path",
    iter_python_files("services"),
    ids=lambda path: path.name,
)
def test_service_never_reads_global_settings(path: Path) -> None:
    """Сервис получает значения через конструктор, а не читает настройки."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = calls_named(tree, "get_settings")

    assert not lines, (
        f"{path.relative_to(SRC.parent)} вызывает get_settings() в строках {lines}. "
        "Нужное значение передаётся сервису конструктором."
    )


@pytest.mark.parametrize(
    "path",
    iter_python_files("services", "mcp_server", "knowledge/worker.py", "api"),
    ids=lambda path: path.name,
)
def test_no_module_finds_clients_by_itself(path: Path) -> None:
    """Глобального локатора клиентов больше нет ни у кого."""
    source = path.read_text(encoding="utf-8")

    assert "get_knowledge_runtime()" not in source, (
        f"{path.relative_to(SRC.parent)} ищет клиентов сам. "
        "Клиенты создаёт lifespan и передаёт через зависимость."
    )


def test_global_runtime_locator_is_gone() -> None:
    """Ленивый глобальный runtime удалён вместе со своим состоянием."""
    source = (SRC / "knowledge" / "runtime.py").read_text(encoding="utf-8")

    assert "global _runtime" not in source
    assert "def get_knowledge_runtime(" not in source


@pytest.mark.parametrize(
    "path",
    iter_python_files("mcp_server", "knowledge/worker.py"),
    ids=lambda path: path.name,
)
def test_transport_and_worker_do_not_read_global_settings(path: Path) -> None:
    """Транспорт и worker получают настройки аргументом, а не глобально."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = calls_named(tree, "get_settings")

    assert not lines, (
        f"{path.relative_to(SRC.parent)} вызывает get_settings() в строках {lines}. "
        "Настройки передаются из composition root."
    )


def test_settings_are_read_only_in_declared_composition_points() -> None:
    """Список мест, читающих глобальные настройки, зафиксирован явно.

    Новая точка чтения — осознанное решение: она должна попасть в
    allowlist вместе с обоснованием, а не появиться незаметно.
    """
    allowed = SETTINGS_ALLOWLIST | PENDING_SETTINGS_READERS
    offenders: list[str] = []
    for path in iter_python_files("."):
        if path in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        lines = calls_named(tree, "get_settings")
        if lines:
            offenders.append(f"{path.relative_to(SRC.parent)}:{lines}")

    assert not offenders, (
        "Настройки читаются вне разрешённых точек сборки: " + ", ".join(offenders)
    )


def test_pending_settings_readers_still_need_the_exception() -> None:
    """Временное исключение снимается вместе с переносом границы.

    Если файл перестал читать настройки, он обязан уйти из списка
    отложенных: иначе исключение переживёт причину, ради которой оно
    появилось, и перестанет что-либо охранять.
    """
    stale: list[str] = []
    for path in PENDING_SETTINGS_READERS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not calls_named(tree, "get_settings"):
            stale.append(str(path.relative_to(SRC.parent)))

    assert not stale, (
        "Файлы больше не читают настройки и должны быть убраны из "
        f"PENDING_SETTINGS_READERS: {stale}"
    )


@pytest.mark.parametrize(
    "path",
    iter_python_files("clients", "storage"),
    ids=lambda path: path.name,
)
def test_client_does_not_create_its_own_transport(path: Path) -> None:
    """Клиент получает transport готовым: у сетевого ресурса один владелец."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    created = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"AsyncClient", "AsyncQdrantClient"}
    ]

    assert not created, (
        f"{path.relative_to(SRC.parent)} создаёт сетевой клиент в строках {created}. "
        "Transport создаёт lifespan и передаёт конструктором."
    )


@pytest.mark.parametrize(
    "path",
    [SRC / "dependencies" / "auth.py", SRC / "dependencies" / "access.py"],
    ids=["auth", "access"],
)
def test_auth_and_access_adapters_do_not_touch_data(path: Path) -> None:
    """Auth и access зависимости не обращаются к данным.

    Им разрешено единственное исключение — перевод ошибки сервиса в
    `HTTPException`. Всё остальное, включая правила доступа и чтение
    репозиториев, принадлежит сервисному слою.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_prefixes = ("src.repositories", "src.db")
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith(forbidden_prefixes):
                offenders.append(f"{node.module}:{node.lineno}")
        elif isinstance(node, ast.Import):
            offenders.extend(
                f"{alias.name}:{node.lineno}"
                for alias in node.names
                if alias.name.startswith(forbidden_prefixes)
            )

    assert not offenders, (
        f"{path.relative_to(SRC.parent)} обращается к слою данных: {offenders}. "
        "Правила доступа принадлежат сервису."
    )


@pytest.mark.parametrize(
    "path",
    [SRC / "dependencies" / "auth.py", SRC / "dependencies" / "access.py"],
    ids=["auth", "access"],
)
def test_required_dependencies_have_no_none_default(path: Path) -> None:
    """Обязательная зависимость не может отсутствовать молча.

    `= None` у репозитория или сервиса превращает ошибку сборки графа в
    падение по `AttributeError` где-то ниже.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        args = node.args
        defaults = dict(
            zip(args.args[len(args.args) - len(args.defaults) :], args.defaults, strict=True)
        )
        for argument, default in defaults.items():
            annotation = ast.unparse(argument.annotation) if argument.annotation else ""
            is_none_default = isinstance(default, ast.Constant) and default.value is None
            looks_required = annotation.endswith(("ServiceDep", "RepositoryDep"))
            if is_none_default and looks_required:
                offenders.append(f"{node.name}({argument.arg}) в строке {node.lineno}")

    assert not offenders, (
        f"{path.relative_to(SRC.parent)}: обязательные зависимости объявлены "
        f"необязательными: {offenders}"
    )


def test_endpoints_never_receive_orm_models_from_access_guards() -> None:
    """Guard доступа не поднимает персистентную модель в эндпоинт."""
    source = (SRC / "dependencies" / "access.py").read_text(encoding="utf-8")
    removed_aliases = (
        "AccessibleProjectDep",
        "OwnedProjectDep",
        "AccessibleTaskDep",
        "AccessibleStageDep",
        "AccessibleDocumentDep",
    )

    present = [alias for alias in removed_aliases if alias in source]
    assert not present, (
        f"Возвращены ORM-алиасы доступа: {present}. "
        "Эндпоинт работает с идентификатором пути и разрешением."
    )
