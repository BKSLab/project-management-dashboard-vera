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


@pytest.mark.parametrize(
    "path",
    iter_python_files("clients", "storage"),
    ids=lambda path: path.name,
)
def test_client_and_storage_do_not_import_service_errors(path: Path) -> None:
    """Нижний слой не знает исключений вышестоящего.

    Клиент, поднимающий `*ServiceError`, фактически объявляет чужой
    контракт: вышестоящий сервис перестаёт быть местом, где решается,
    во что превращается сбой внешней системы.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.startswith("src.exceptions"):
            continue
        if node.module in {"src.exceptions.clients", "src.exceptions.storage"}:
            continue
        offenders.extend(
            f"{node.module}.{alias.name}:{node.lineno}"
            for alias in node.names
            if alias.name.endswith("ServiceError") or "Service" in alias.name
        )

    assert not offenders, (
        f"{path.relative_to(SRC.parent)} импортирует исключения сервисного слоя: {offenders}. "
        "Преобразование принадлежит вызывающему сервису."
    )


@pytest.mark.parametrize(
    "path",
    iter_python_files("api"),
    ids=lambda path: path.name,
)
def test_endpoints_do_not_catch_lower_layer_errors(path: Path) -> None:
    """Эндпоинт не ловит ошибки клиента, хранилища или репозитория.

    Их обязан преобразовать сервис: если такая ошибка доходит до
    транспорта, значит граница слоя где-то пропущена.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_suffixes = ("ClientError", "StorageError", "RepositoryError")
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.type is None:
            continue
        elements = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
        for element in elements:
            if isinstance(element, ast.Name) and element.id.endswith(forbidden_suffixes):
                offenders.append(f"{element.id}:{node.lineno}")

    assert not offenders, (
        f"{path.relative_to(SRC.parent)} ловит ошибку нижнего слоя: {offenders}."
    )


def test_broad_application_error_is_confined_to_transport_boundaries() -> None:
    """Широкий перехват допустим только на финальной границе транспорта.

    Внутри сервиса он скрывает, какой именно контракт зависимости
    обрабатывается, и молча проглатывает новое семейство ошибок.
    """
    allowed_prefixes = (SRC / "mcp_server",)
    offenders: list[str] = []
    for path in iter_python_files("."):
        if any(path.is_relative_to(prefix) for prefix in allowed_prefixes):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or node.type is None:
                continue
            elements = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
            offenders.extend(
                f"{path.relative_to(SRC.parent)}:{node.lineno}"
                for element in elements
                if isinstance(element, ast.Name) and element.id == "ApplicationError"
            )

    assert not offenders, (
        "Широкий перехват ApplicationError вне транспортной границы: " + ", ".join(offenders)
    )


def test_no_dead_reraise_of_own_errors_remains() -> None:
    """Не осталось `except OwnError: raise`, который ничего не ловит.

    Такая клауза появляется, когда `try` охватывает и вызов зависимости,
    и собственную доменную проверку. Она ничего не защищает и создаёт
    ложное впечатление, что защищает.
    """
    offenders: list[str] = []
    for path in iter_python_files("services"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for index, handler in enumerate(node.handlers):
                is_bare_raise = (
                    len(handler.body) == 1
                    and isinstance(handler.body[0], ast.Raise)
                    and handler.body[0].exc is None
                )
                if not is_bare_raise or handler.type is None:
                    continue
                later_types = [
                    ast.unparse(other.type)
                    for other in node.handlers[index + 1 :]
                    if other.type is not None
                ]
                # Пропускаем случаи с широким перехватом ниже: там клауза
                # действительно нужна, чтобы своя ошибка прошла наверх.
                if any("Exception" in item or "BaseException" in item for item in later_types):
                    continue
                offenders.append(
                    f"{path.relative_to(SRC.parent)}:{handler.lineno} "
                    f"({ast.unparse(handler.type)})"
                )

    assert not offenders, "Мёртвые клаузы `except ...: raise`: " + ", ".join(offenders)


# Сценарии с медленным внешним вызовом. Каждый обязан работать через
# короткую область базы, а не через репозитории, живущие вместе с ним.
EXTERNAL_CALL_SERVICES = {
    "analytics.py": "AnalyticsService",
    "project_agent.py": "ProjectAgentService",
    "task_descriptions.py": "TaskDescriptionService",
    "task_documents.py": "TaskDocumentImportService",
    "wbs_suggestion.py": "WbsSuggestionService",
    "attachment_download.py": "AttachmentDownloadService",
}


@pytest.mark.parametrize(
    ("file_name", "class_name"),
    sorted(EXTERNAL_CALL_SERVICES.items()),
    ids=sorted(EXTERNAL_CALL_SERVICES.values()),
)
def test_service_with_external_call_holds_no_repositories(
    file_name: str,
    class_name: str,
) -> None:
    """Сервис с внешним вызовом не хранит репозитории как свои поля.

    Хранимый репозиторий означает сессию, живущую столько же, сколько сам
    сервис. Тогда соединение с PostgreSQL остаётся занятым и во время
    ожидания модели, и во время передачи файла — ради чего короткая
    область и вводилась.
    """
    tree = ast.parse((SRC / "services" / file_name).read_text(encoding="utf-8"))
    service = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    init = next(
        node
        for node in service.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "__init__"
    )

    stored: list[str] = []
    for node in ast.walk(init):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr.endswith(("_repository", "unit_of_work"))
            ):
                stored.append(target.attr)

    assert not stored, (
        f"{class_name} хранит {stored}: сессия проживёт столько же, сколько сервис. "
        "Работа с базой должна идти через короткую область."
    )


@pytest.mark.parametrize(
    ("file_name", "class_name"),
    sorted(EXTERNAL_CALL_SERVICES.items()),
    ids=sorted(EXTERNAL_CALL_SERVICES.values()),
)
def test_service_with_external_call_receives_a_scope(
    file_name: str,
    class_name: str,
) -> None:
    """Такой сервис получает фабрику короткой области конструктором."""
    tree = ast.parse((SRC / "services" / file_name).read_text(encoding="utf-8"))
    service = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    init = next(
        node
        for node in service.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "__init__"
    )
    arguments = {argument.arg for argument in init.args.args + init.args.kwonlyargs}

    assert "scope" in arguments, f"{class_name} не получает фабрику короткой области."


@pytest.mark.parametrize(
    "file_name",
    sorted(EXTERNAL_CALL_SERVICES),
    ids=sorted(EXTERNAL_CALL_SERVICES),
)
def test_service_with_external_call_does_not_import_sqlalchemy(file_name: str) -> None:
    """Сервис не знает о SQLAlchemy: реализация области живёт в DI-слое."""
    source = (SRC / "services" / file_name).read_text(encoding="utf-8")

    assert "sqlalchemy" not in source, (
        f"{file_name} импортирует SQLAlchemy: реализация короткой области "
        "принадлежит слою сборки зависимостей."
    )
