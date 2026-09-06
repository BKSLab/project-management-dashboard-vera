from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.tasks import (
    TaskChecklistConflictError,
    TaskChecklistValidationError,
    TasksServiceError,
)
from src.schemas.task_checklists import TaskChecklistSchema
from src.schemas.tasks import TaskCreateSchema, TaskUpdateSchema
from src.utils.checklists import checklist_context
from tests.unit.services.test_tasks_service import build_service, make_task


def checklist():
    return TaskChecklistSchema(
        title="Приёмка", items=[{"text": "Проверить результат"}, {"text": "Подписать акт"}]
    ).model_dump(mode="json")


def setup_service():
    task = make_task()
    task.checklist = checklist()
    task.checklist_revision = 2
    service = build_service()
    service.tasks_repository.get_for_update.return_value = task
    service.tasks_repository.get_by_id.return_value = task

    def update(*, task, data):
        for key, value in data.items():
            setattr(task, key, value)
        return task

    service.tasks_repository.update.side_effect = update
    return service, task


def test_schema_preserves_null_omission_and_stable_ids_and_rejects_invalid_values():
    data = checklist()
    saved = TaskCreateSchema(title="Задача", checklist=data)
    assert saved.checklist.items[0].id != saved.checklist.items[1].id
    assert TaskUpdateSchema(title="Изменено").model_dump(exclude_unset=True) == {
        "title": "Изменено"
    }
    assert TaskUpdateSchema(checklist=None, checklist_revision=2).model_dump(
        exclude_unset=True
    ) == {"checklist": None, "checklist_revision": 2}
    for bad in (
        {"checklist": None},
        {"checklist_revision": 2},
        {"checklist": data, "checklist_revision": -1},
    ):
        with pytest.raises(ValidationError):
            TaskUpdateSchema(**bad)
    for bad in (
        {"title": " "},
        {"items": [{"text": " "}]},
        {"items": [{"text": "a\x00b"}]},
        {"items": [data["items"][0], data["items"][0]]},
        {"items": [{"text": "x"}] * 101},
        {"items": [{"text": "x", "is_completed": "false"}]},
    ):
        with pytest.raises(ValidationError):
            TaskChecklistSchema(**bad)


async def test_update_reorders_edits_completes_and_removes_items_atomically():
    service, task = setup_service()
    data = checklist()
    first, second = task.checklist["items"]
    data["items"] = [
        {**second, "text": "Акт подписан", "is_completed": True},
        {"id": str(uuid4()), "text": "Архивировать", "is_completed": False},
    ]
    result = await service.update_task(
        task_id=task.id, data={"checklist": data, "checklist_revision": 2}
    )
    assert result.checklist_revision == 3
    assert str(result.checklist.items[0].id) == second["id"]
    assert result.checklist.items[0].is_completed
    assert all(str(item.id) != first["id"] for item in result.checklist.items)
    service.tasks_repository.get_for_update.assert_awaited_once_with(task_id=task.id)
    service.knowledge_events.upsert.assert_awaited_once()
    service.activity_repository.save.assert_awaited_once()
    service.unit_of_work.commit.assert_awaited_once()


async def test_delete_keeps_revision_and_regular_task_edit_preserves_checklist():
    service, task = setup_service()
    await service.update_task(task_id=task.id, data={"title": "Новый заголовок"})
    assert task.checklist is not None and task.checklist_revision == 2
    result = await service.update_task(
        task_id=task.id, data={"checklist": None, "checklist_revision": 2}
    )
    assert result.checklist is None and result.checklist_revision == 3


async def test_conflict_never_overwrites_a_concurrent_change():
    service, task = setup_service()
    before = task.checklist
    with pytest.raises(TaskChecklistConflictError):
        await service.update_task(
            task_id=task.id, data={"checklist": None, "checklist_revision": 1}
        )
    assert task.checklist == before
    service.tasks_repository.update.assert_not_awaited()
    service.unit_of_work.commit.assert_not_awaited()
    service.unit_of_work.rollback.assert_awaited_once()


async def test_outbox_failure_rolls_back_checklist_and_history():
    service, task = setup_service()
    service.knowledge_events.upsert = AsyncMock(
        side_effect=KnowledgeEventsServiceError("outbox failed")
    )
    with pytest.raises(TasksServiceError):
        await service.update_task(
            task_id=task.id, data={"checklist": None, "checklist_revision": 2}
        )
    service.unit_of_work.commit.assert_not_awaited()
    service.unit_of_work.rollback.assert_awaited_once()


async def test_direct_service_requires_valid_checklist_and_version():
    service, task = setup_service()
    for data in (
        {"checklist": None},
        {"checklist": {"items": [{"text": " "}]}, "checklist_revision": 2},
    ):
        with pytest.raises(TaskChecklistValidationError):
            await service.update_task(task_id=task.id, data=data)
    service.tasks_repository.update.assert_not_awaited()


def test_context_reports_unfinished_items_without_claiming_task_completion():
    value = checklist()
    value["items"][0]["is_completed"] = True
    context = checklist_context(value, limit=1)
    assert context["completed_items"] == 1 and context["total_items"] == 2
    assert context["included_items"] == 1
    assert "id" not in context["items"][0]
