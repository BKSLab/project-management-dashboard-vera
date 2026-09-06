import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.projects import Project
from src.repositories.documents import DocumentsRepository


@pytest.mark.asyncio
async def test_ranked_search_orders_and_bounds_results(db_session: AsyncSession, project: Project) -> None:
    """Поиск с префиксом и подсветкой, приоритет совпадения в заголовке, точный slug."""

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

    repository = DocumentsRepository(db_session)
    content_match = await repository.create(
        data={
            "project_id": project.id,
            "slug": "register",
            "title": "Рабочий реестр",
            "content_md": "Описание рисков проекта и мер реагирования.",
        }
    )
    title_match = await repository.create(
        data={
            "project_id": project.id,
            "slug": "risk-policy",
            "title": "Риски проекта",
            "content_md": "Краткий документ.",
        }
    )

    documents = await repository.search_ranked(
        project_id=project.id,
        search="риски",
        limit=1,
    )

    assert [item.id for item in documents] == [title_match.id]
    assert content_match.id != title_match.id

    repository = DocumentsRepository(db_session)
    document = await repository.create(
        data={
            "project_id": project.id,
            "slug": "adr-0042",
            "title": "Архитектурное решение",
            "content_md": "Текст решения.",
        }
    )

    documents = await repository.search_ranked(
        project_id=project.id,
        search="adr-0042",
        limit=30,
    )

    assert [item.id for item in documents] == [document.id]
