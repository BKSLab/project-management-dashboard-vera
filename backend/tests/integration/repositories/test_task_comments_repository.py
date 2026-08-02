import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_comments import TaskCommentsRepository


@pytest.mark.asyncio
async def test_search_on_real_postgres_finds_task_by_comment_prefix(
    db_session: AsyncSession,
) -> None:
    stage = await KanbanStagesRepository(db_session).save(
        data={
            "name": "В работе",
            "order_index": 1,
            "color": "#F5B800",
            "is_done_stage": False,
        }
    )
    task = await KanbanTasksRepository(db_session).save(
        data={"stage_id": stage.id, "title": "Карточка", "position": 1.0}
    )
    repository = TaskCommentsRepository(db_session)
    await repository.save(
        task_id=task.id,
        author_name="Борис",
        body_md="Нужно проверить пользовательский сценарий.",
    )

    task_ids = await repository.search_task_ids(search="пользова")
    highlights = await repository.get_search_highlights(
        task_ids=[task.id],
        search="пользова",
    )

    assert task_ids == {task.id}
    assert highlights[task.id]["search_match_source"] == "comment"
    assert "__FTS_START__" in highlights[task.id]["search_excerpt"]
