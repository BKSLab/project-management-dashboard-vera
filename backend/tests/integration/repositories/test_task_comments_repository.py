import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository


@pytest.mark.asyncio
async def test_search_on_real_postgres_finds_task_by_comment_prefix(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    task = await TasksRepository(db_session).save(
        data={
            "project_id": stage.project_id,
            "stage_id": stage.id,
            "number": 1,
            "title": "Карточка",
            "priority": "MEDIUM",
            "position": 1.0,
        }
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
