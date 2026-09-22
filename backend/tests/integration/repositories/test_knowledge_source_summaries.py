"""Настоящие SQL: изоляция кэша, обновление версии, FTS и удаление оригинала."""

from sqlalchemy import delete, select

from src.db.models import Document, KnowledgeIndexJob, KnowledgeSourceSummary
from src.knowledge.catalog import build_catalog
from src.repositories.knowledge_source_summaries import KnowledgeSourceSummariesRepository
from src.repositories.knowledge_sources import KnowledgeSourcesRepository


async def test_cache_is_versioned_and_full_text_search_finds_omitted_detail(db_session, project):
    document = Document(
        project_id=project.id,
        slug="conditions",
        title="Условия поставки",
        content_md="Общие условия. " * 2000 + " Алмазокомплект привезут 25 октября.",
    )
    db_session.add(document)
    await db_session.flush()
    sources = KnowledgeSourcesRepository(db_session)
    cache = KnowledgeSourceSummariesRepository(db_session)
    source_id = f"document:{document.id}"
    source = build_catalog(project.id, await sources.get_project_rows(project.id)).sources[
        source_id
    ]
    data = {
        "project_id": project.id,
        "source_id": source_id,
        "document_id": document.id,
        "attachment_id": None,
        "content_hash": source.summary_hash,
        "summary": "Документ об условиях поставки.",
    }
    await db_session.execute(
        delete(KnowledgeIndexJob).where(KnowledgeIndexJob.project_id == project.id)
    )
    await cache.save(data)
    await cache.save(data)
    assert (
        not (
            await db_session.execute(
                select(KnowledgeIndexJob).where(KnowledgeIndexJob.project_id == project.id)
            )
        )
        .scalars()
        .all()
    )
    assert (
        len(
            (
                await db_session.execute(
                    select(KnowledgeSourceSummary).where(
                        KnowledgeSourceSummary.project_id == project.id
                    )
                )
            )
            .scalars()
            .all()
        )
        == 1
    )
    catalog = build_catalog(project.id, await sources.get_project_rows(project.id))
    assert catalog.sources[source_id].summary == data["summary"]
    assert "Алмазокомплект" not in data["summary"]
    assert source_id in {
        item["source_id"] for item in await sources.search(project.id, "Алмазокомплект")
    }
    assert not (await sources.get_project_rows(project.id + 10000)).get(
        "knowledge_source_summaries"
    )
    document.content_md = "Обновлённые условия."
    await db_session.flush()
    catalog = build_catalog(project.id, await sources.get_project_rows(project.id))
    assert catalog.sources[source_id].summary is None
    await cache.save(
        {
            **data,
            "content_hash": catalog.sources[source_id].summary_hash,
            "summary": "Новое описание.",
        }
    )
    assert (
        build_catalog(project.id, await sources.get_project_rows(project.id))
        .sources[source_id]
        .summary
        == "Новое описание."
    )
    await db_session.execute(delete(Document).where(Document.id == document.id))
    assert (
        await db_session.execute(
            select(KnowledgeSourceSummary).where(KnowledgeSourceSummary.project_id == project.id)
        )
    ).scalars().all() == []
