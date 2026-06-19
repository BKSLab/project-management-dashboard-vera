import logging

from src.exceptions.services import DocumentLinkInvalidError, DocumentLinkNotFoundError
from src.repositories.document_links import DocumentLinksRepository
from src.schemas.document_links import (
    DocumentLinkSchema,
    LinkedDocumentSchema,
    LinkedTargetSchema,
)

logger = logging.getLogger(__name__)


class DocumentLinksService:
    """Сервис бизнес-логики связей документов с задачами/узлами ИСР."""

    def __init__(self, document_links_repository: DocumentLinksRepository):
        self.document_links_repository = document_links_repository

    async def create_link(
        self, document_id: int, kanban_task_id: int | None, wbs_item_id: int | None
    ) -> DocumentLinkSchema:
        if (kanban_task_id is None) == (wbs_item_id is None):
            raise DocumentLinkInvalidError()

        link = await self.document_links_repository.create(
            data={
                "document_id": document_id,
                "kanban_task_id": kanban_task_id,
                "wbs_item_id": wbs_item_id,
            }
        )
        return DocumentLinkSchema.model_validate(link)

    async def delete_link(self, link_id: int) -> None:
        link = await self.document_links_repository.get_by_id(link_id=link_id)
        if link is None:
            raise DocumentLinkNotFoundError(link_id=link_id)
        await self.document_links_repository.delete(link=link)

    async def get_links_for_document(self, document_id: int) -> list[LinkedTargetSchema]:
        links = await self.document_links_repository.get_for_document(document_id=document_id)
        result = []
        for link in links:
            if link.kanban_task_id is not None and link.kanban_task is not None:
                title = link.kanban_task.title
            elif link.wbs_item_id is not None and link.wbs_item is not None:
                title = f"{link.wbs_item.code} {link.wbs_item.title}"
            else:
                continue
            result.append(
                LinkedTargetSchema(
                    link_id=link.id,
                    kanban_task_id=link.kanban_task_id,
                    wbs_item_id=link.wbs_item_id,
                    title=title,
                )
            )
        return result

    async def get_links_for_task(self, kanban_task_id: int) -> list[LinkedDocumentSchema]:
        links = await self.document_links_repository.get_for_task(kanban_task_id=kanban_task_id)
        return [
            LinkedDocumentSchema(
                link_id=link.id,
                document_id=link.document_id,
                slug=link.document.slug,
                title=link.document.title,
            )
            for link in links
            if link.document is not None
        ]
