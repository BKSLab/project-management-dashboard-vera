from typing import Annotated

from fastapi import Depends

from src.dependencies.db_session import DbSessionDep
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.kanban import KanbanRepository
from src.repositories.wbs import WbsRepository


def get_documents_repository(session: DbSessionDep) -> DocumentsRepository:
    return DocumentsRepository(session)


def get_kanban_repository(session: DbSessionDep) -> KanbanRepository:
    return KanbanRepository(session)


def get_wbs_repository(session: DbSessionDep) -> WbsRepository:
    return WbsRepository(session)


def get_document_links_repository(session: DbSessionDep) -> DocumentLinksRepository:
    return DocumentLinksRepository(session)


DocumentsRepositoryDep = Annotated[
    DocumentsRepository, Depends(get_documents_repository)
]
KanbanRepositoryDep = Annotated[
    KanbanRepository, Depends(get_kanban_repository)
]
WbsRepositoryDep = Annotated[
    WbsRepository, Depends(get_wbs_repository)
]
DocumentLinksRepositoryDep = Annotated[
    DocumentLinksRepository, Depends(get_document_links_repository)
]
