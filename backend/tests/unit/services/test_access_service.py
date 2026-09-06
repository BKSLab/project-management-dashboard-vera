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


# Вложенные объекты: метод доступа, его аргумент, ожидаемый resource_id
# и то, как в дублёре задаётся отсутствие объекта.
NESTED_RESOURCES = (
    ("ensure_task_access", {"task_id": 7}, 7, {"task": None}),
    ("ensure_stage_access", {"stage_id": 8}, 8, {"stage": None}),
    ("ensure_document_access", {"document_id": 9}, 9, {"document": None}),
    ("ensure_comment_access", {"comment_id": 10}, 10, {"comment": None}),
    ("ensure_link_access", {"link_id": 11}, 11, {"link": None}),
)


async def test_project_access_reflects_membership_and_ownership() -> None:
    """Участник получает разрешение, владелец помечается, чужой не проходит.

    Три состояния одного use case проверяются вместе: разрешение — это
    один объект, и смысл имеет вся его форма, а не отдельные поля.
    """
    member_grant = await build_service(
        member_role=ProjectRole.MEMBER
    ).ensure_project_access(project_id=PROJECT_ID, user_id=USER_ID)
    assert (member_grant.project_id, member_grant.resource_id, member_grant.is_owner) == (
        PROJECT_ID,
        PROJECT_ID,
        False,
    )

    owner_grant = await build_service(member_role=ProjectRole.OWNER).ensure_project_access(
        project_id=PROJECT_ID, user_id=USER_ID
    )
    assert owner_grant.is_owner is True

    with pytest.raises(ResourceNotAvailableError) as error:
        await build_service(member_role=None).ensure_project_access(
            project_id=PROJECT_ID, user_id=USER_ID
        )
    assert error.value.status_code == 404


async def test_ownership_check_separates_absence_from_insufficient_role() -> None:
    """Владелец проходит, участник получает 403, чужой — 404.

    Порядок важен: для чужого проекта ответ обязан быть 404, иначе по
    коду ответа выяснялось бы, что проект существует.
    """
    owner_grant = await build_service(member_role=ProjectRole.OWNER).ensure_project_ownership(
        project_id=PROJECT_ID, user_id=USER_ID
    )
    assert owner_grant.is_owner is True

    with pytest.raises(ProjectOwnerRequiredError) as forbidden:
        await build_service(member_role=ProjectRole.MEMBER).ensure_project_ownership(
            project_id=PROJECT_ID, user_id=USER_ID
        )
    assert forbidden.value.status_code == 403

    with pytest.raises(ResourceNotAvailableError):
        await build_service(member_role=None).ensure_project_ownership(
            project_id=PROJECT_ID, user_id=USER_ID
        )


async def test_nested_resource_access_follows_one_rule_for_every_resource() -> None:
    """Доступ к вложенному объекту сводится к доступу к его проекту.

    Правило одно на все ресурсы, поэтому и тест один: доступный объект
    отдаёт разрешение своего проекта, а отсутствующий и чужой отвечают
    одинаковым 404 с одинаковой формулировкой. Прогон по всему списку
    показывает сразу все ресурсы, где правило нарушено.
    """
    problems: list[str] = []
    for method, kwargs, resource_id, missing in NESTED_RESOURCES:
        grant = await getattr(build_service(member_role=ProjectRole.MEMBER), method)(
            user_id=USER_ID, **kwargs
        )
        if (grant.project_id, grant.resource_id) != (PROJECT_ID, resource_id):
            problems.append(f"{method}: разрешение {grant} вместо проекта {PROJECT_ID}")

        absent = build_service(member_role=ProjectRole.MEMBER, **missing)
        try:
            await getattr(absent, method)(user_id=USER_ID, **kwargs)
        except ResourceNotAvailableError:
            pass
        else:
            problems.append(f"{method}: отсутствующий объект доступен")

        foreign = build_service(member_role=None)
        try:
            await getattr(foreign, method)(user_id=USER_ID, **kwargs)
        except ResourceNotAvailableError as error:
            if (error.status_code, error.detail) != (404, "Объект не найден."):
                problems.append(f"{method}: чужой объект отличим — {error.status_code} {error.detail}")
        else:
            problems.append(f"{method}: чужой объект доступен")

    assert not problems, (
        "Правило доступа к вложенным объектам нарушено: " + "; ".join(problems)
    )


async def test_orphan_resource_is_not_found_instead_of_failing() -> None:
    """Объект без родителя недоступен, а не приводит к ошибке."""
    with pytest.raises(ResourceNotAvailableError):
        await build_service(member_role=ProjectRole.MEMBER, task=None).ensure_comment_access(
            comment_id=10, user_id=USER_ID
        )

    with pytest.raises(ResourceNotAvailableError):
        await build_service(member_role=ProjectRole.MEMBER, document=None).ensure_link_access(
            link_id=11, user_id=USER_ID
        )


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
