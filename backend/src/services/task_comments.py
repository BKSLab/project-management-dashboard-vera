import logging

from src.db.models.task_activity import TaskActivityEventType
from src.exceptions.kanban_tasks import KanbanTaskNotFoundError, KanbanTasksRepositoryError
from src.exceptions.task_activity import TaskActivityRepositoryError
from src.exceptions.task_comments import (
    TaskCommentNotFoundError,
    TaskCommentsRepositoryError,
    TaskCommentsServiceError,
)
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.schemas.task_comments import CommentSchema

logger = logging.getLogger(__name__)


class TaskCommentsService:
    """Сервис сценариев работы с комментариями задач."""

    def __init__(
        self,
        comments_repository: TaskCommentsRepository,
        tasks_repository: KanbanTasksRepository,
        activity_repository: TaskActivityRepository,
    ):
        self.comments_repository = comments_repository
        self.tasks_repository = tasks_repository
        self.activity_repository = activity_repository

    async def get_comments(self, task_id: int) -> list[CommentSchema]:
        """Возвращает комментарии существующей задачи.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            Комментарии задачи в хронологическом порядке.

        Raises:
            KanbanTaskNotFoundError: Если задача не найдена.
            TaskCommentsServiceError: Если получить комментарии не удалось.
        """
        try:
            if await self.tasks_repository.get_by_id(task_id=task_id) is None:
                raise KanbanTaskNotFoundError(task_id=task_id)
            comments = await self.comments_repository.get_for_task(task_id=task_id)
            return [CommentSchema.model_validate(comment) for comment in comments]
        except KanbanTaskNotFoundError:
            raise
        except (TaskCommentsRepositoryError, KanbanTasksRepositoryError) as error:
            logger.error("❌ Ошибка получения комментариев задачи id=%s.", task_id, exc_info=True)
            raise TaskCommentsServiceError(str(error)) from error

    async def add_comment(
        self,
        task_id: int,
        author_name: str | None,
        body_md: str,
    ) -> CommentSchema:
        """Добавляет комментарий и событие истории задачи.

        Args:
            task_id: Идентификатор задачи.
            author_name: Необязательная подпись автора.
            body_md: Текст комментария в Markdown.

        Returns:
            Созданный комментарий.

        Raises:
            KanbanTaskNotFoundError: Если задача не найдена.
            TaskCommentsServiceError: Если добавить комментарий не удалось.
        """
        try:
            if await self.tasks_repository.get_by_id(task_id=task_id) is None:
                raise KanbanTaskNotFoundError(task_id=task_id)
            comment = await self.comments_repository.save(
                task_id=task_id,
                author_name=author_name,
                body_md=body_md,
            )
            await self.activity_repository.save(
                task_id=task_id,
                event_type=TaskActivityEventType.COMMENT_ADDED,
                from_value=None,
                to_value=body_md[:255],
            )
            return CommentSchema.model_validate(comment)
        except KanbanTaskNotFoundError:
            raise
        except (
            TaskCommentsRepositoryError,
            KanbanTasksRepositoryError,
            TaskActivityRepositoryError,
        ) as error:
            logger.error("❌ Ошибка добавления комментария задачи id=%s.", task_id, exc_info=True)
            raise TaskCommentsServiceError(str(error)) from error

    async def delete_comment(self, comment_id: int) -> None:
        """Удаляет комментарий по идентификатору.

        Args:
            comment_id: Идентификатор комментария.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            TaskCommentNotFoundError: Если комментарий не найден.
            TaskCommentsServiceError: Если удалить комментарий не удалось.
        """
        try:
            comment = await self.comments_repository.get_by_id(comment_id=comment_id)
            if comment is None:
                raise TaskCommentNotFoundError(comment_id=comment_id)
            await self.comments_repository.delete(comment=comment)
        except TaskCommentNotFoundError:
            raise
        except TaskCommentsRepositoryError as error:
            logger.error("❌ Ошибка удаления комментария id=%s.", comment_id, exc_info=True)
            raise TaskCommentsServiceError(str(error)) from error
