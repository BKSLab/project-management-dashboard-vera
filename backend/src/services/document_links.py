import logging

from src.exceptions.document_links import (
    DocumentLinkAlreadyExistsError,
    DocumentLinkAlreadyExistsRepositoryError,
    DocumentLinkNotFoundError,
    DocumentLinkProjectMismatchError,
    DocumentLinksRepositoryError,
    DocumentLinksServiceError,
)
from src.exceptions.documents import DocumentNotFoundError, DocumentsRepositoryError
from src.exceptions.projects import ProjectsRepositoryError
from src.exceptions.tasks import TaskNotFoundError, TasksRepositoryError
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.schemas.document_links import (
    DocumentLinkSchema,
    LinkedDocumentSchema,
    LinkedTaskSchema,
)
from src.services.tasks import build_task_key

logger = logging.getLogger(__name__)

RepositoryErrors = (
    DocumentLinksRepositoryError,
    DocumentsRepositoryError,
    ProjectsRepositoryError,
    TasksRepositoryError,
)


class DocumentLinksService:
    """Сервис сценариев работы со связями документов и задач."""

    def __init__(
        self,
        document_links_repository: DocumentLinksRepository,
        documents_repository: DocumentsRepository,
        tasks_repository: TasksRepository,
        projects_repository: ProjectsRepository,
        members_repository: ProjectMembersRepository,
    ):
        self.document_links_repository = document_links_repository
        self.documents_repository = documents_repository
        self.tasks_repository = tasks_repository
        self.projects_repository = projects_repository
        self.members_repository = members_repository

    async def create_link(
        self,
        document_id: int,
        task_id: int,
        user_id: int,
    ) -> DocumentLinkSchema:
        """Связывает документ с задачей одного проекта.

        У маршрута нет идентификатора проекта в пути, поэтому доступ здесь
        проверяет сервис, а не Depends-слой.

        Args:
            document_id: Идентификатор документа.
            task_id: Идентификатор задачи.
            user_id: Идентификатор пользователя.

        Returns:
            Созданная связь.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            TaskNotFoundError: Если задача не найдена.
            DocumentLinkProjectMismatchError: Если документ и задача из разных проектов.
            DocumentLinkAlreadyExistsError: Если такая связь уже существует.
            DocumentLinksServiceError: Если создать связь не удалось.
        """
        try:
            document = await self.documents_repository.get_by_id(document_id=document_id)
            if document is None:
                raise DocumentNotFoundError(document_id=document_id)
            # Недоступный документ неотличим от отсутствующего.
            if (
                await self.members_repository.get(
                    project_id=document.project_id,
                    user_id=user_id,
                )
                is None
            ):
                raise DocumentNotFoundError(document_id=document_id)
            task = await self.tasks_repository.get_by_id(task_id=task_id)
            if task is None:
                raise TaskNotFoundError(task_id=task_id)
            if document.project_id != task.project_id:
                raise DocumentLinkProjectMismatchError(
                    document_id=document_id,
                    task_id=task_id,
                )
            link = await self.document_links_repository.create(
                data={"document_id": document_id, "task_id": task_id}
            )
            return DocumentLinkSchema.model_validate(link)
        except (
            DocumentNotFoundError,
            TaskNotFoundError,
            DocumentLinkProjectMismatchError,
        ):
            raise
        except DocumentLinkAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Связь документа id=%s уже существует.", error.document_id)
            raise DocumentLinkAlreadyExistsError(document_id=error.document_id) from error
        except RepositoryErrors as error:
            logger.error("❌ Ошибка создания связи документа id=%s.", document_id, exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error

    async def delete_link(self, link_id: int) -> None:
        """Удаляет связь документа с задачей.

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
        except RepositoryErrors as error:
            logger.error("❌ Ошибка удаления связи документа id=%s.", link_id, exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error

    async def get_links_for_document(self, document_id: int) -> list[LinkedTaskSchema]:
        """Возвращает задачи, связанные с документом.

        Args:
            document_id: Идентификатор документа.

        Returns:
            Связанные задачи.

        Raises:
            DocumentNotFoundError: Если документ не найден.
            DocumentLinksServiceError: Если получить связи не удалось.
        """
        try:
            document = await self.documents_repository.get_by_id(document_id=document_id)
            if document is None:
                raise DocumentNotFoundError(document_id=document_id)
            links = await self.document_links_repository.get_for_document(document_id=document_id)
            tasks = await self.tasks_repository.get_by_ids(
                task_ids={link.task_id for link in links}
            )
            tasks_by_id = {task.id: task for task in tasks}
            project = await self.projects_repository.get_by_id(project_id=document.project_id)
            project_key = project.key if project else ""

            result: list[LinkedTaskSchema] = []
            for link in links:
                task = tasks_by_id.get(link.task_id)
                if task is None:
                    continue
                result.append(
                    LinkedTaskSchema(
                        link_id=link.id,
                        task_id=task.id,
                        key=build_task_key(project_key=project_key, number=task.number),
                        title=task.title,
                    )
                )
            return result
        except DocumentNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения связей документа id=%s.", document_id, exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error

    async def get_links_for_task(self, task_id: int) -> list[LinkedDocumentSchema]:
        """Возвращает документы, связанные с задачей.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            Связанные документы.

        Raises:
            TaskNotFoundError: Если задача не найдена.
            DocumentLinksServiceError: Если получить связи не удалось.
        """
        try:
            if await self.tasks_repository.get_by_id(task_id=task_id) is None:
                raise TaskNotFoundError(task_id=task_id)
            links = await self.document_links_repository.get_for_task(task_id=task_id)
            documents = await self.documents_repository.get_by_ids(
                document_ids={link.document_id for link in links}
            )
            documents_by_id = {document.id: document for document in documents}

            result: list[LinkedDocumentSchema] = []
            for link in links:
                document = documents_by_id.get(link.document_id)
                if document is None:
                    continue
                result.append(
                    LinkedDocumentSchema(
                        link_id=link.id,
                        document_id=document.id,
                        slug=document.slug,
                        title=document.title,
                    )
                )
            return result
        except TaskNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения связей задачи id=%s.", task_id, exc_info=True)
            raise DocumentLinksServiceError(str(error)) from error
