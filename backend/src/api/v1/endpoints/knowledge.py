import logging

from fastapi import APIRouter, HTTPException, status

from src.dependencies.access import AccessibleProjectDep
from src.dependencies.services import ProjectAgentServiceDep
from src.exceptions.knowledge import KnowledgeServiceError
from src.schemas.knowledge import (
    KnowledgeAnswerSchema,
    KnowledgeAskSchema,
    KnowledgeReindexSchema,
    KnowledgeStatusSchema,
)

router = APIRouter(prefix="/projects/{project_id}/knowledge", tags=["project knowledge"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=KnowledgeStatusSchema)
async def get_knowledge_status(
    project: AccessibleProjectDep,
    service: ProjectAgentServiceDep,
) -> KnowledgeStatusSchema:
    """Возвращает готовность семантического индекса доступного проекта."""
    try:
        return await service.get_status(project.id)
    except KnowledgeServiceError as error:
        logger.exception("❌ Не удалось получить статус базы знаний проекта id=%s.", project.id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post("/ask", response_model=KnowledgeAnswerSchema)
async def ask_project_agent(
    project: AccessibleProjectDep,
    data: KnowledgeAskSchema,
    service: ProjectAgentServiceDep,
) -> KnowledgeAnswerSchema:
    """Отвечает на вопрос только по данным доступного проекта."""
    try:
        return await service.ask(
            project=project,
            question=data.question,
            history=data.history,
        )
    except KnowledgeServiceError as error:
        logger.exception("❌ Project Agent проекта id=%s не ответил.", project.id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=KnowledgeReindexSchema,
)
async def reindex_project_knowledge(
    project: AccessibleProjectDep,
    service: ProjectAgentServiceDep,
) -> KnowledgeReindexSchema:
    """Ставит полную пересборку индекса проекта в постоянную очередь."""
    try:
        await service.reindex(project.id)
        return KnowledgeReindexSchema()
    except KnowledgeServiceError as error:
        logger.exception("❌ Не удалось поставить reindex проекта id=%s.", project.id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
