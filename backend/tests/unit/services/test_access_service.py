"""Правила доступа к объектам проекта.

Проверяется сервис, а не Depends-слой: правило одно и то же для HTTP и MCP,
и жить оно должно в одном месте.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.project_members import ProjectMember, ProjectRole
from src.exceptions.access import (
    AccessServiceError,
    ProjectOwnerRequiredError,
    ResourceNotAvailableError,
)
from src.exceptions.projects import ProjectsRepositoryError
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.services.access import AccessService

PROJECT_ID = 5
USER_ID = 1
FOREIGN_PROJECT_ID = 42


# Объекты по умолчанию принадлежат доступному проекту; отсутствие объекта
# задаётся явной передачей ``None``.
MISSING = object()


def build_service(
    *,
    member_role: ProjectRole | None = ProjectRole.MEMBER,
    task=MISSING,
    stage=MISSING,
    document=MISSING,
    comment=MISSING,
    link=MISSING,
    members_error: Exception | None = None,
):
    """Собирает сервис доступа на дублёрах репозиториев."""
    task = SimpleNamespace(id=7, project_id=PROJECT_ID) if task is MISSING else task
    stage = SimpleNamespace(id=8, project_id=PROJECT_ID) if stage is MISSING else stage
    document = SimpleNamespace(id=9, project_id=PROJECT_ID) if document is MISSING else document
    comment = SimpleNamespace(id=10, task_id=7) if comment is MISSING else comment
    link = SimpleNamespace(id=11, document_id=9) if link is MISSING else link
    members = AsyncMock(spec=ProjectMembersRepository)
    if members_error is not None:
        members.get.side_effect = members_error
    else:
        members.get.return_value = (
            None
            if member_role is None
            else ProjectMember(project_id=PROJECT_ID, user_id=USER_ID, role=member_role)
        )

    tasks = AsyncMock(spec=TasksRepository)
    tasks.get_by_id.return_value = task
    stages = AsyncMock(spec=ProjectStagesRepository)
    stages.get_by_id.return_value = stage
    documents = AsyncMock(spec=DocumentsRepository)
    documents.get_by_id.return_value = document
    comments = AsyncMock(spec=TaskCommentsRepository)
    comments.get_by_id.return_value = comment
    links = AsyncMock(spec=DocumentLinksRepository)
    links.get_by_id.return_value = link

    return AccessService(
        members_repository=members,
        tasks_repository=tasks,
        stages_repository=stages,
        documents_repository=documents,
        comments_repository=comments,
        links_repository=links,
    )


async def test_member_gets_project_access() -> None:
    """Участник проекта получает разрешение без роли владельца."""
    service = build_service(member_role=ProjectRole.MEMBER)

    grant = await service.ensure_project_access(project_id=PROJECT_ID, user_id=USER_ID)

    assert grant.project_id == PROJECT_ID
    assert grant.resource_id == PROJECT_ID
    assert grant.is_owner is False


async def test_owner_is_marked_as_owner() -> None:
    """Владелец проекта помечается в разрешении."""
    service = build_service(member_role=ProjectRole.OWNER)

    grant = await service.ensure_project_access(project_id=PROJECT_ID, user_id=USER_ID)

    assert grant.is_owner is True


async def test_non_member_cannot_reach_the_project() -> None:
    """Чужой проект недоступен и неотличим от несуществующего."""
    service = build_service(member_role=None)

    with pytest.raises(ResourceNotAvailableError) as error:
        await service.ensure_project_access(project_id=PROJECT_ID, user_id=USER_ID)

    assert error.value.status_code == 404


async def test_member_is_not_an_owner() -> None:
    """Обычный участник не выполняет действия владельца."""
    service = build_service(member_role=ProjectRole.MEMBER)

    with pytest.raises(ProjectOwnerRequiredError) as error:
        await service.ensure_project_ownership(project_id=PROJECT_ID, user_id=USER_ID)

    assert error.value.status_code == 403


async def test_owner_passes_ownership_check() -> None:
    """Владелец проходит проверку владения."""
    service = build_service(member_role=ProjectRole.OWNER)

    grant = await service.ensure_project_ownership(project_id=PROJECT_ID, user_id=USER_ID)

    assert grant.is_owner is True


async def test_non_member_gets_not_found_before_ownership_check() -> None:
    """Для чужого проекта отвечает 404, а не 403.

    Иначе по коду ответа выяснялось бы, что проект существует.
    """
    service = build_service(member_role=None)

    with pytest.raises(ResourceNotAvailableError):
        await service.ensure_project_ownership(project_id=PROJECT_ID, user_id=USER_ID)


@pytest.mark.parametrize(
    ("method", "kwargs", "resource_id"),
    [
        ("ensure_task_access", {"task_id": 7}, 7),
        ("ensure_stage_access", {"stage_id": 8}, 8),
        ("ensure_document_access", {"document_id": 9}, 9),
        ("ensure_comment_access", {"comment_id": 10}, 10),
        ("ensure_link_access", {"link_id": 11}, 11),
    ],
)
async def test_nested_resource_resolves_to_its_project(
    method: str,
    kwargs: dict,
    resource_id: int,
) -> None:
    """Доступ к вложенному объекту сводится к доступу к его проекту."""
    service = build_service(member_role=ProjectRole.MEMBER)

    grant = await getattr(service, method)(user_id=USER_ID, **kwargs)

    assert grant.project_id == PROJECT_ID
    assert grant.resource_id == resource_id


@pytest.mark.parametrize(
    ("method", "kwargs", "missing"),
    [
        ("ensure_task_access", {"task_id": 7}, {"task": None}),
        ("ensure_stage_access", {"stage_id": 8}, {"stage": None}),
        ("ensure_document_access", {"document_id": 9}, {"document": None}),
        ("ensure_comment_access", {"comment_id": 10}, {"comment": None}),
        ("ensure_link_access", {"link_id": 11}, {"link": None}),
    ],
)
async def test_missing_resource_is_not_found(
    method: str,
    kwargs: dict,
    missing: dict,
) -> None:
    """Несуществующий объект отвечает 404 до проверки членства."""
    service = build_service(member_role=ProjectRole.MEMBER, **missing)

    with pytest.raises(ResourceNotAvailableError):
        await getattr(service, method)(user_id=USER_ID, **kwargs)


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("ensure_task_access", {"task_id": 7}),
        ("ensure_stage_access", {"stage_id": 8}),
        ("ensure_document_access", {"document_id": 9}),
        ("ensure_comment_access", {"comment_id": 10}),
        ("ensure_link_access", {"link_id": 11}),
    ],
)
async def test_foreign_resource_is_indistinguishable_from_missing(
    method: str,
    kwargs: dict,
) -> None:
    """Существующий чужой объект отвечает тем же 404, что и отсутствующий."""
    service = build_service(member_role=None)

    with pytest.raises(ResourceNotAvailableError) as error:
        await getattr(service, method)(user_id=USER_ID, **kwargs)

    assert error.value.status_code == 404
    assert error.value.detail == "Объект не найден."


async def test_orphan_comment_is_not_found() -> None:
    """Комментарий без задачи недоступен, а не приводит к ошибке."""
    service = build_service(member_role=ProjectRole.MEMBER, task=None)

    with pytest.raises(ResourceNotAvailableError):
        await service.ensure_comment_access(comment_id=10, user_id=USER_ID)


async def test_orphan_link_is_not_found() -> None:
    """Связь без документа недоступна, а не приводит к ошибке."""
    service = build_service(member_role=ProjectRole.MEMBER, document=None)

    with pytest.raises(ResourceNotAvailableError):
        await service.ensure_link_access(link_id=11, user_id=USER_ID)


async def test_repository_failure_is_not_an_access_denial() -> None:
    """Сбой базы не превращается в 404.

    Иначе временная недоступность PostgreSQL выглядела бы как отсутствие
    объекта, и причину искали бы в правах, а не в инфраструктуре.
    """
    service = build_service(members_error=ProjectsRepositoryError("сбой БД"))

    with pytest.raises(AccessServiceError) as error:
        await service.ensure_project_access(project_id=PROJECT_ID, user_id=USER_ID)

    assert not isinstance(error.value, ResourceNotAvailableError)
    assert error.value.status_code == 500


async def test_access_grant_is_immutable() -> None:
    """Разрешение нельзя доправить после выдачи."""
    service = build_service(member_role=ProjectRole.MEMBER)

    grant = await service.ensure_project_access(project_id=PROJECT_ID, user_id=USER_ID)

    with pytest.raises((AttributeError, TypeError)):
        grant.is_owner = True
