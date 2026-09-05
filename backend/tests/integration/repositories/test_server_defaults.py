"""Server-defaults, возвращаемые записывающими методами репозиториев.

Эти проверки написаны до удаления `session.refresh()` и должны остаться
зелёными после него: если значение приходило из дополнительного SELECT,
а не из самого DML, тест это покажет.

Проверяется реальный PostgreSQL: поведение `RETURNING` и серверных
умолчаний нельзя подтвердить ни на моках, ни на SQLite.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.api_tokens import ApiTokenScope
from src.db.models.documents import Document
from src.db.models.project_members import ProjectRole
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.task_activity import TaskActivityEventType
from src.db.models.tasks import Task
from src.db.models.users import User
from src.repositories.api_tokens import ApiTokensRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.users import UsersRepository
from src.repositories.wbs_nodes import WbsNodesRepository


def assert_persisted(entity) -> None:
    """Запись получила идентификатор и оба серверных таймстемпа."""
    assert entity.id is not None, "Идентификатор не вернулся из DML."
    assert isinstance(entity.created_at, datetime), "created_at не заполнен сервером."
    assert isinstance(entity.updated_at, datetime), "updated_at не заполнен сервером."


@pytest.mark.asyncio
async def test_user_save_and_update_return_server_defaults(db_session: AsyncSession) -> None:
    """Пользователь возвращается с идентификатором и таймстемпами."""
    repository = UsersRepository(db_session)

    user = await repository.save(
        data={
            "username": "defaults",
            "password_hash": "hash",
            "last_name": "Умолчаниев",
            "first_name": "Сервер",
            "is_active": True,
        }
    )

    assert_persisted(user)
    created_at = user.created_at

    updated = await repository.update(user=user, data={"first_name": "Обновлён"})

    assert updated.first_name == "Обновлён"
    assert updated.created_at == created_at
    assert isinstance(updated.updated_at, datetime)


@pytest.mark.asyncio
async def test_project_save_and_update_return_server_defaults(
    db_session: AsyncSession,
    user: User,
) -> None:
    """Проект возвращается заполненным без дополнительного чтения."""
    repository = ProjectsRepository(db_session)

    project = await repository.save(
        data={
            "owner_id": user.id,
            "key": "DEFA",
            "name": "Проект умолчаний",
            "status": "PLANNING",
            "color": "#58a6ff",
            "order_index": 5,
        }
    )

    assert_persisted(project)
    assert project.key == "DEFA"

    updated = await repository.update(project=project, data={"name": "Переименован"})

    assert updated.name == "Переименован"
    assert isinstance(updated.updated_at, datetime)


@pytest.mark.asyncio
async def test_stage_save_and_update_return_server_defaults(
    db_session: AsyncSession,
    project: Project,
) -> None:
    """Стадия возвращается с идентификатором и таймстемпами."""
    repository = ProjectStagesRepository(db_session)

    stage = await repository.save(
        data={
            "project_id": project.id,
            "name": "Новая стадия",
            "order_index": 7,
            "color": "#a371f7",
            "is_done_stage": False,
        }
    )

    assert stage.id is not None
    assert stage.order_index == 7

    updated = await repository.update(stage=stage, data={"name": "Другая стадия"})

    assert updated.name == "Другая стадия"


@pytest.mark.asyncio
async def test_stage_save_many_returns_every_row_persisted(
    db_session: AsyncSession,
    project: Project,
) -> None:
    """Массовая вставка стадий возвращает заполненными все строки."""
    repository = ProjectStagesRepository(db_session)

    stages = await repository.save_many(
        items=[
            {
                "project_id": project.id,
                "name": f"Стадия {index}",
                "order_index": 10 + index,
                "color": "#58a6ff",
                "is_done_stage": False,
            }
            for index in range(3)
        ]
    )

    assert len(stages) == 3
    for stage in stages:
        assert stage.id is not None, "Идентификатор строки не вернулся из вставки."
    assert len({stage.id for stage in stages}) == 3


@pytest.mark.asyncio
async def test_task_save_and_update_return_server_defaults(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
) -> None:
    """Задача возвращается заполненной сразу после записи."""
    repository = TasksRepository(db_session)

    task = await repository.save(
        data={
            "project_id": project.id,
            "stage_id": stage.id,
            "number": 1,
            "title": "Задача умолчаний",
            "position": 1000.0,
        }
    )

    assert_persisted(task)
    assert task.number == 1

    updated = await repository.update(task=task, data={"title": "Переименована"})

    assert updated.title == "Переименована"
    assert isinstance(updated.updated_at, datetime)


@pytest.mark.asyncio
async def test_document_save_and_update_return_server_defaults(
    db_session: AsyncSession,
    project: Project,
) -> None:
    """Документ возвращается с идентификатором и таймстемпами."""
    repository = DocumentsRepository(db_session)

    document = await repository.create(
        data={
            "project_id": project.id,
            "slug": "defaults",
            "title": "Документ умолчаний",
            "content_md": "# Заголовок",
        }
    )

    assert_persisted(document)

    updated = await repository.update(document=document, data={"title": "Переименован"})

    assert updated.title == "Переименован"
    assert isinstance(updated.updated_at, datetime)


@pytest.mark.asyncio
async def test_wbs_node_save_and_update_return_server_defaults(
    db_session: AsyncSession,
    project: Project,
) -> None:
    """Раздел ИСР возвращается заполненным."""
    repository = WbsNodesRepository(db_session)

    node = await repository.save(
        data={
            "project_id": project.id,
            "parent_id": None,
            "title": "Раздел",
            "position": 1000.0,
        }
    )

    assert_persisted(node)

    updated = await repository.update(node=node, data={"title": "Другой раздел"})

    assert updated.title == "Другой раздел"


@pytest.mark.asyncio
async def test_milestone_save_and_update_return_server_defaults(
    db_session: AsyncSession,
    project: Project,
) -> None:
    """Веха возвращается заполненной."""
    repository = MilestonesRepository(db_session)

    milestone = await repository.save(
        data={
            "project_id": project.id,
            "title": "Веха",
            "due_date": datetime.now(UTC).date(),
        }
    )

    assert_persisted(milestone)

    updated = await repository.update(milestone=milestone, data={"title": "Другая веха"})

    assert updated.title == "Другая веха"


@pytest.mark.asyncio
async def test_comment_save_returns_server_defaults(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
) -> None:
    """Комментарий возвращается с идентификатором и временем создания."""
    task = await TasksRepository(db_session).save(
        data={
            "project_id": project.id,
            "stage_id": stage.id,
            "number": 2,
            "title": "Задача комментария",
            "position": 2000.0,
        }
    )

    comment = await TaskCommentsRepository(db_session).save(
        task_id=task.id,
        author_name="Автор",
        body_md="Текст комментария",
    )

    assert comment.id is not None
    assert isinstance(comment.created_at, datetime)


@pytest.mark.asyncio
async def test_activity_save_returns_server_defaults(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
) -> None:
    """Запись истории возвращается заполненной."""
    task = await TasksRepository(db_session).save(
        data={
            "project_id": project.id,
            "stage_id": stage.id,
            "number": 3,
            "title": "Задача истории",
            "position": 3000.0,
        }
    )

    activity = await TaskActivityRepository(db_session).save(
        task_id=task.id,
        event_type=TaskActivityEventType.COMMENT_ADDED,
        from_value=None,
        to_value="Создана",

    )

    assert activity.id is not None
    assert isinstance(activity.created_at, datetime)


@pytest.mark.asyncio
async def test_project_member_save_returns_server_defaults(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    """Участие в проекте возвращается заполненным."""
    other = await UsersRepository(db_session).save(
        data={
            "username": "member",
            "password_hash": "hash",
            "last_name": "Участников",
            "first_name": "Пётр",
            "is_active": True,
        }
    )

    member = await ProjectMembersRepository(db_session).save(
        data={
            "project_id": project.id,
            "user_id": other.id,
            "role": ProjectRole.MEMBER,
        }
    )

    assert isinstance(member.created_at, datetime)
    assert member.user_id == other.id


@pytest.mark.asyncio
async def test_api_token_create_returns_server_defaults(
    db_session: AsyncSession,
    user: User,
) -> None:
    """Токен доступа возвращается с идентификатором и таймстемпами."""
    token = await ApiTokensRepository(db_session).create(
        user_id=user.id,
        name="Ноутбук",
        token_hash="hash-of-secret",
        prefix="tt_abcde",
        scope=ApiTokenScope.READ,
        expires_at=None,
    )

    assert_persisted(token)
    assert token.scope is ApiTokenScope.READ


@pytest.mark.asyncio
async def test_saved_values_survive_a_fresh_read(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
) -> None:
    """Возвращённые значения совпадают с тем, что реально лежит в базе.

    Именно это гарантирует, что удаление дополнительного SELECT не подменило
    server-defaults значениями, придуманными в Python.
    """
    repository = TasksRepository(db_session)
    task = await repository.save(
        data={
            "project_id": project.id,
            "stage_id": stage.id,
            "number": 4,
            "title": "Задача сверки",
            "position": 4000.0,
        }
    )
    returned_created_at = task.created_at

    await db_session.flush()
    stored: Task | None = await repository.get_by_id(task_id=task.id)

    assert stored is not None
    assert stored.created_at == returned_created_at
    assert stored.title == "Задача сверки"


@pytest.mark.asyncio
async def test_updated_at_advances_on_update(
    db_session: AsyncSession,
    project: Project,
) -> None:
    """Обновление действительно двигает серверный `updated_at`.

    Без этого проверка «поле заполнено» прошла бы и на устаревшем значении,
    оставшемся от вставки.
    """
    repository = DocumentsRepository(db_session)
    document: Document = await repository.create(
        data={
            "project_id": project.id,
            "slug": "touch",
            "title": "Документ",
            "content_md": "текст",
        }
    )
    before = document.updated_at

    updated = await repository.update(document=document, data={"content_md": "новый текст"})

    assert updated.updated_at >= before


@pytest.fixture
def sql_log(db_session: AsyncSession):
    """Считает SQL-запросы, реально ушедшие в PostgreSQL."""
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.split()))

    engine = db_session.get_bind().engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    yield statements
    event.remove(engine, "before_cursor_execute", before_cursor_execute)


@pytest.mark.asyncio
async def test_save_issues_a_single_insert(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    sql_log: list[str],
) -> None:
    """Обычная запись выполняет один INSERT и не дочитывает результат.

    Раньше после вставки шёл отдельный SELECT ради серверных умолчаний:
    два обращения к базе там, где достаточно одного.
    """
    sql_log.clear()

    task = await TasksRepository(db_session).save(
        data={
            "project_id": project.id,
            "stage_id": stage.id,
            "number": 41,
            "title": "Задача одного запроса",
            "position": 4100.0,
        }
    )

    assert_persisted(task)
    inserts = [item for item in sql_log if item.upper().startswith("INSERT")]
    selects = [item for item in sql_log if item.upper().startswith("SELECT")]
    assert len(inserts) == 1, f"Ожидался один INSERT, выполнено: {sql_log}"
    assert not selects, f"После вставки выполнен лишний SELECT: {selects}"
    assert "RETURNING" in inserts[0].upper(), "Серверные значения не пришли из RETURNING."


@pytest.mark.asyncio
async def test_update_issues_a_single_update(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    sql_log: list[str],
) -> None:
    """Обычное обновление выполняет один UPDATE и не дочитывает результат."""
    task = await TasksRepository(db_session).save(
        data={
            "project_id": project.id,
            "stage_id": stage.id,
            "number": 42,
            "title": "Задача обновления",
            "position": 4200.0,
        }
    )
    sql_log.clear()

    updated = await TasksRepository(db_session).update(task=task, data={"title": "Изменена"})

    assert updated.title == "Изменена"
    assert isinstance(updated.updated_at, datetime)
    updates = [item for item in sql_log if item.upper().startswith("UPDATE")]
    selects = [item for item in sql_log if item.upper().startswith("SELECT")]
    assert len(updates) == 1, f"Ожидался один UPDATE, выполнено: {sql_log}"
    assert not selects, f"После обновления выполнен лишний SELECT: {selects}"


@pytest.mark.asyncio
async def test_batch_insert_does_not_run_per_row_queries(
    db_session: AsyncSession,
    project: Project,
    sql_log: list[str],
) -> None:
    """Массовая вставка стадий не превращается в N запросов на строку."""
    sql_log.clear()

    stages = await ProjectStagesRepository(db_session).save_many(
        items=[
            {
                "project_id": project.id,
                "name": f"Пакетная {index}",
                "order_index": 20 + index,
                "color": "#58a6ff",
                "is_done_stage": False,
            }
            for index in range(5)
        ]
    )

    assert len(stages) == 5
    selects = [item for item in sql_log if item.upper().startswith("SELECT")]
    assert not selects, f"Массовая вставка дочитывает строки по одной: {selects}"
