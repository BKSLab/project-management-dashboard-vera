import json

from src.clients.qdrant import KnowledgeSearchHit
from src.db.models.knowledge_index_jobs import KnowledgeEntityType, KnowledgeIndexOperation
from src.knowledge.documents import build_risk_chunks
from src.services.project_agent import AgentOutput, AgentToolPlan
from tests.unit.knowledge.test_knowledge_index import build_service as build_index
from tests.unit.knowledge.test_knowledge_index import make_job
from tests.unit.knowledge.test_project_agent import build_service as build_agent
from tests.unit.services.test_project_risks_service import risk


def test_risk_chunks_include_both_plans_and_survive_task_context_removal():
    saved = risk(task_id=7, mitigation_plan="Превентивные меры", response_plan="Резервный адаптер")
    chunks = build_risk_chunks(saved, target_chars=250, overlap_chars=30)
    text = "\n".join(chunk.text for chunk in chunks)
    assert "Превентивные меры" in text and "Резервный адаптер" in text
    assert all(
        chunk.payload["entity_type"] == "risk" and chunk.payload["task_id"] is None
        for chunk in chunks
    )
    assert chunks == build_risk_chunks(saved, target_chars=250, overlap_chars=30)


async def test_risk_index_preparation_and_missing_record_cleanup(tmp_path):
    service, _, _, runtime, _, _ = build_index(tmp_path)
    service.risks_repository.get_by_id.return_value = risk()
    job = make_job(KnowledgeIndexOperation.UPSERT, KnowledgeEntityType.RISK, 12)
    action = await service.prepare(job)
    assert action.documents
    runtime.embedding_client.get_embeddings.assert_not_awaited()
    service.risks_repository.get_by_id.assert_awaited_once_with(project_id=1, risk_id=12)
    service.risks_repository.get_by_id.return_value = None
    await service.process(job)
    runtime.qdrant_client.delete_entity.assert_awaited_once_with(
        project_id=1, entity_type="risk", entity_id=12
    )
    runtime.qdrant_client.upsert_documents.assert_not_awaited()


async def test_semantic_risks_are_reloaded_from_sql_and_deleted_or_foreign_hits_are_dropped():
    service, project, runtime, db = build_agent()
    runtime.qdrant_client.search.return_value = [
        KnowledgeSearchHit(
            score=0.9,
            payload={
                "entity_type": "risk",
                "entity_id": str(id_),
                "source_id": f"risk:{id_}",
                "text": "Устаревший HIGH и старый план",
            },
        )
        for id_ in (12, 13, 14)
    ]
    db.risks.get_by_ids.return_value = [
        risk(
            id=12,
            project_id=project.id,
            probability="LOW",
            impact="LOW",
            risk_level="LOW",
            status="CLOSED",
            mitigation_plan="Актуальный план",
        )
    ]

    async def answer(*, schema, content, **kwargs):
        if schema is AgentToolPlan:
            return AgentToolPlan(entity_type="risk", search_query="CRM")
        data = json.loads(content)
        candidates = data["retrieval_context"]
        assert len(candidates) == 1
        record = candidates[0]["semantic_fragment"]
        assert record["status"] == "CLOSED" and record["risk_level"] == "LOW"
        assert record["mitigation_plan"] == "Актуальный план"
        assert "Устаревший" not in content
        return AgentOutput(answer="Риск закрыт.", source_ids=[candidates[0]["source_handle"]])

    runtime.llm_client.get_structured_response.side_effect = answer
    result = await service.ask(project_id=project.id, question="Что с риском CRM?", history=[])
    assert [source.source_id for source in result.sources] == ["risk:12"]
    db.risks.get_by_ids.assert_awaited_once_with(project_id=project.id, risk_ids={12, 13, 14})
