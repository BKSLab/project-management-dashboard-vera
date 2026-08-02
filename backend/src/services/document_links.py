import logging

from src.exceptions.document_links import (
    DocumentLinkAlreadyExistsError,
    DocumentLinkAlreadyExistsRepositoryError,
    DocumentLinkInvalidError,
    DocumentLinkNotFoundError,
    DocumentLinksRepositoryError,
    DocumentLinksServiceError,
)
from src.exceptions.documents import DocumentNotFoundError, DocumentsRepositoryError
from src.exceptions.kanban_tasks import KanbanTaskNotFoundError, KanbanTasksRepositoryError
from src.exceptions.wbs import WbsItemNotFoundError, WbsRepositoryError
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.wbs import WbsRepository
from src.schemas.document_links import (
    DocumentLinkSchema,
    LinkedDocumentSchema,
    LinkedTargetSchema,
)

logger = logging.getLogger(__name__)


class DocumentLinksService:
    """Сервис бизнес-логики связей документов с задачами/узлами ИСР."""

    def __init__(
        self,
        document_links_repository: DocumentLinksRepository,
        documents_repository: DocumentsRepository,
        tasks_repository: KanbanTasksRepository,
        wbs_repository: WbsRepository,
    ):
        self.document_links_repository = document_links_repository
        self.documents_repository = documents_repository
        self.tasks_repository = tasks_repository
        self.wbs_repository = wbs_repository

    async def create_link(
        self, document_id: int, kanban_task_id: int | None, wbs_item_id: int | None
    ) -> DocumentLinkSchema:
        """Создаёт связь документа ровно с одной целевой сущностью.

        Args:
            document_id: Идентификатор документа.
            kanban_task_id: Идентификатор задачи или ``None``.
            wbs_item_id: Идентификатор узла ИСР или ``None``.

        Returns:
            Созданная связь документа.

        Raises:
            DocumentLinkInvalidError: Если передано не ровно одно целевое поле.
            DocumentNotFoundError: Если документ не найден.
            KanbanTaskNotFoundError: Если задача не найдена.
            WbsItemNotFoundError: Если узел ИСР не найден.
            DocumentLinksServiceError: Если операция с БД завершилась ошибкой.
        """
        try:
            if (kanban_task_id is None) == (wbs_item_id is None):
                raise DocumentLinkInvalidError()
            if await self.documents_repository.get_by_slug_or_id(document_id=document_id) is None:
                raise DocumentNotFoundError(slug=str(document_id))
            if (
                kanban_task_id is not None
                and await self.tasks_repository.get_by_id(task_id=kanban_task_id) is None
            ):
                raise KanbanTaskNotFoundError(task_id=kanban_task_id)
            if (
                wbs_item_id is not None
                and await self.wbs_repository.get_by_id(item_id=wbs_item_id) is None
            ):
                raise WbsItemNotFoundError(item_id=wbs_item_id)
            link = await self.document_links_repository.create(
                data={
                    "document_id": document_id,
                    "kanban_task_id": kanban_task_id,
                    "wbs_item_id": wbs_item_id,
                }
            )
            return DocumentLinkSchema.model_validate(link)
        except DocumentLinkAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Связь документа id=%s уже существует.", error.document_id)
            raise DocumentLinkAlreadyExistsError(document_id=error.document_id) from error
        except (
            DocumentLinkInvalidError,
            DocumentNotFoundError,
            KanbanTaskNotFoundError,
            WbsItemNotFoundError,
        ):
            raise
        except (
            DocumentLinksRepositoryError,
            DocumentsRepositoryError,
            KanbanTasksRepositoryError,
            WbsRepositoryError,
        ) as error:
            logger.error("❌ Ошибка создания связи документа.", exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error

    async def delete_link(self, link_id: int) -> None:
        """Удаляет связь документа.

        Args:
            link_id: Идентификатор связи.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            DocumentLinkNotFoundError: Если связь не найдена.
            DocumentLinksServiceError: Если удалить связь не удалось.
        """
        try:
            link = await self.document_links_repository.get_by_id(link_id=link_id)
            if link is None:
                raise DocumentLinkNotFoundError(link_id=link_id)
            await self.document_links_repository.delete(link=link)
        except DocumentLinkNotFoundError:
            raise
        except DocumentLinksRepositoryError as error:
            logger.error("❌ Ошибка удаления связи id=%s.", link_id, exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error

    async def get_links_for_document(self, document_id: int) -> list[LinkedTargetSchema]:
        """Возвращает целевые сущности, связанные с документом.

        Args:
            document_id: Идентификатор документа.

        Returns:
            Список связанных задач и узлов ИСР.

        Raises:
            DocumentLinksServiceError: Если получить связи не удалось.
        """
        try:
            links = await self.document_links_repository.get_for_document(document_id=document_id)
            tasks = await self.tasks_repository.get_by_ids(
                task_ids={link.kanban_task_id for link in links if link.kanban_task_id is not None}
            )
            wbs_items = await self.wbs_repository.get_by_ids(
                item_ids={link.wbs_item_id for link in links if link.wbs_item_id is not None}
            )
            tasks_by_id = {task.id: task for task in tasks}
            wbs_by_id = {item.id: item for item in wbs_items}
            result: list[LinkedTargetSchema] = []
            for link in links:
                task = tasks_by_id.get(link.kanban_task_id) if link.kanban_task_id else None
                wbs_item = wbs_by_id.get(link.wbs_item_id) if link.wbs_item_id else None
                if task is not None:
                    title = task.title
                elif wbs_item is not None:
                    title = f"{wbs_item.code} {wbs_item.title}"
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
        except (
            DocumentLinksRepositoryError,
            KanbanTasksRepositoryError,
            WbsRepositoryError,
        ) as error:
            logger.error("❌ Ошибка получения связей документа id=%s.", document_id, exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error

    async def get_links_for_document_slug(self, slug: str) -> list[LinkedTargetSchema]:
        """Возвращает связи документа, найденного по slug.

        Args:
            slug: URL-идентификатор документа.

        Returns:
            Список связанных задач и узлов ИСР.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            DocumentLinksServiceError: Если получить связи не удалось.
        """
        try:
            document = await self.documents_repository.get_by_slug(slug=slug)
            if document is None:
                raise DocumentNotFoundError(slug=slug)
        except DocumentNotFoundError:
            raise
        except DocumentsRepositoryError as error:
            logger.error("❌ Ошибка получения связей документа slug=%s.", slug, exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error
        return await self.get_links_for_document(document_id=document.id)

    async def get_links_for_task(self, kanban_task_id: int) -> list[LinkedDocumentSchema]:
        """Возвращает документы, связанные с задачей.

        Args:
            kanban_task_id: Идентификатор задачи канбана.

        Returns:
            Список связанных документов.

        Raises:
            KanbanTaskNotFoundError: Если задача не найдена.
            DocumentLinksServiceError: Если получить связи не удалось.
        """
        try:
            if await self.tasks_repository.get_by_id(task_id=kanban_task_id) is None:
                raise KanbanTaskNotFoundError(task_id=kanban_task_id)
            links = await self.document_links_repository.get_for_task(kanban_task_id=kanban_task_id)
            documents = await self.documents_repository.get_by_ids(
                document_ids={link.document_id for link in links}
            )
            documents_by_id = {document.id: document for document in documents}
            return [
                LinkedDocumentSchema(
                    link_id=link.id,
                    document_id=link.document_id,
                    slug=documents_by_id[link.document_id].slug,
                    title=documents_by_id[link.document_id].title,
                )
                for link in links
                if link.document_id in documents_by_id
            ]
        except KanbanTaskNotFoundError:
            raise
        except (
            DocumentLinksRepositoryError,
            DocumentsRepositoryError,
            KanbanTasksRepositoryError,
        ) as error:
            logger.error("❌ Ошибка получения связей задачи id=%s.", kanban_task_id, exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error
