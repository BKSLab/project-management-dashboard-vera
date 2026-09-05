import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies.access import ProjectIdPath, require_project_access
from src.dependencies.auth import require_write_scope
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


@router.get(
    "/status",
    dependencies=[Depends(require_project_access)],
    response_model=KnowledgeStatusSchema,
)
async def get_knowledge_status(
    project_id: ProjectIdPath,
    service: ProjectAgentServiceDep,
) -> KnowledgeStatusSchema:
    """Возвращает готовность семантического индекса доступного проекта."""
    try:
        return await service.get_status(project_id)
    except KnowledgeServiceError as error:
        logger.exception("❌ Не удалось получить статус базы знаний проекта id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/ask",
    dependencies=[Depends(require_project_access)],
    response_model=KnowledgeAnswerSchema,
)
async def ask_project_agent(
    project_id: ProjectIdPath,
    data: KnowledgeAskSchema,
    service: ProjectAgentServiceDep,
) -> KnowledgeAnswerSchema:
    """Отвечает на вопрос только по данным доступного проекта."""
    try:
        return await service.ask(
            project_id=project_id,
            question=data.question,
            history=data.history,
        )
    except KnowledgeServiceError as error:
        logger.exception("❌ Project Agent проекта id=%s не ответил.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/reindex",
    dependencies=[Depends(require_project_access), Depends(require_write_scope)],
    status_code=status.HTTP_202_ACCEPTED,
    response_model=KnowledgeReindexSchema,
)
async def reindex_project_knowledge(
    project_id: ProjectIdPath,
    service: ProjectAgentServiceDep,
) -> KnowledgeReindexSchema:
    """Ставит полную пересборку индекса проекта в постоянную очередь."""
    try:
        await service.reindex(project_id)
        return KnowledgeReindexSchema()
    except KnowledgeServiceError as error:
        logger.exception("❌ Не удалось поставить reindex проекта id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
