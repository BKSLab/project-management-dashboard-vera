from typing import Annotated

from fastapi import Depends

from src.dependencies.repositories import (
    DocumentLinksRepositoryDep,
    DocumentsRepositoryDep,
    KanbanRepositoryDep,
    WbsRepositoryDep,
)
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.kanban import KanbanService
from src.services.wbs import WbsService


async def get_documents_service(
    documents_repository: DocumentsRepositoryDep
) -> DocumentsService:
    return DocumentsService(documents_repository=documents_repository)


async def get_kanban_service(
    kanban_repository: KanbanRepositoryDep,
    wbs_repository: WbsRepositoryDep,
) -> KanbanService:
    return KanbanService(kanban_repository=kanban_repository, wbs_repository=wbs_repository)


async def get_wbs_service(
    wbs_repository: WbsRepositoryDep,
    kanban_repository: KanbanRepositoryDep,
) -> WbsService:
    return WbsService(wbs_repository=wbs_repository, kanban_repository=kanban_repository)


async def get_document_links_service(
    document_links_repository: DocumentLinksRepositoryDep
) -> DocumentLinksService:
    return DocumentLinksService(document_links_repository=document_links_repository)


DocumentsServiceDep = Annotated[
    DocumentsService, Depends(get_documents_service)
]
KanbanServiceDep = Annotated[
    KanbanService, Depends(get_kanban_service)
]
WbsServiceDep = Annotated[
    WbsService, Depends(get_wbs_service)
]
DocumentLinksServiceDep = Annotated[
    DocumentLinksService, Depends(get_document_links_service)
]
