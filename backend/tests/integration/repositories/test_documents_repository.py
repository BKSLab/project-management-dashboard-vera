import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.projects import Project
from src.repositories.documents import DocumentsRepository


@pytest.mark.asyncio
async def test_search_on_real_postgres_supports_prefix_and_highlight(
    db_session: AsyncSession,
    project: Project,
) -> None:
    repository = DocumentsRepository(db_session)
    document = await repository.create(
        data={
            "project_id": project.id,
            "slug": "guide",
            "title": "Руководство",
            "content_md": "Пользовательская инструкция по работе с системой.",
        }
    )

    documents = await repository.get_by_project(project_id=project.id, search="пользова")
    highlights = await repository.get_search_highlights(
        document_ids=[document.id],
        search="пользова",
    )

    assert [item.id for item in documents] == [document.id]
    assert highlights[document.id]["search_match_source"] == "content"
    assert "__FTS_START__" in highlights[document.id]["search_excerpt"]
