import logging

from sqlalchemy import Result, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.task_comments import TaskComment
from src.exceptions.task_comments import TaskCommentsRepositoryError
from src.utils.fts import (
    EXCERPT_HEADLINE_OPTIONS,
    HIGHLIGHT_START,
    TITLE_HEADLINE_OPTIONS,
    build_ts_query,
)

logger = logging.getLogger(__name__)


class TaskCommentsRepository:
    """Репозиторий комментариев задач канбана."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_for_task(self, task_id: int) -> list[TaskComment]:
        """Возвращает комментарии задачи в хронологическом порядке.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            Комментарии задачи.

        Raises:
            TaskCommentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(TaskComment)
                .where(TaskComment.task_id == task_id)
                .order_by(TaskComment.created_at)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить комментарии задачи id=%s.", task_id, exc_info=True)
            raise TaskCommentsRepositoryError(
                f"Ошибка получения комментариев задачи id={task_id}."
            ) from error

    async def get_all(self) -> list[TaskComment]:
        """Возвращает все комментарии для построения агрегатов карточек.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Комментарии всех задач.

        Raises:
            TaskCommentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(TaskComment).order_by(TaskComment.task_id, TaskComment.created_at)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить комментарии задач.", exc_info=True)
            raise TaskCommentsRepositoryError("Ошибка получения комментариев задач.") from error

    async def get_by_id(self, comment_id: int) -> TaskComment | None:
        """Возвращает комментарий по идентификатору.

        Args:
            comment_id: Идентификатор комментария.

        Returns:
            Найденный комментарий или ``None``.

        Raises:
            TaskCommentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(TaskComment).where(TaskComment.id == comment_id)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить комментарий id=%s.", comment_id, exc_info=True)
            raise TaskCommentsRepositoryError(
                f"Ошибка получения комментария id={comment_id}."
            ) from error

    async def search_task_ids(self, search: str) -> set[int]:
        """Возвращает id задач с совпадениями в комментариях.

        Args:
            search: Полнотекстовый запрос.

        Returns:
            Идентификаторы задач с совпадениями.

        Raises:
            TaskCommentsRepositoryError: Если поиск завершился ошибкой.
        """
        try:
            ts_query = build_ts_query(search)
            result: Result = await self.db_session.execute(
                select(TaskComment.task_id).where(TaskComment.search_vector.op("@@")(ts_query))
            )
            return set(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось выполнить FTS-поиск комментариев.", exc_info=True)
            raise TaskCommentsRepositoryError("Ошибка поиска по комментариям.") from error

    async def get_search_highlights(
        self,
        task_ids: list[int],
        search: str,
    ) -> dict[int, dict[str, str]]:
        """Возвращает последнее подсвеченное совпадение комментария для каждой задачи.

        Args:
            task_ids: Идентификаторы отображаемых задач.
            search: Полнотекстовый запрос.

        Returns:
            Поисковый контекст по идентификаторам задач.

        Raises:
            TaskCommentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not task_ids or not search.strip():
            return {}
        try:
            ts_query = build_ts_query(search)
            stmt = (
                select(
                    TaskComment.task_id,
                    func.ts_headline(
                        "russian", TaskComment.body_md, ts_query, EXCERPT_HEADLINE_OPTIONS
                    ).label("body_headline"),
                    func.ts_headline(
                        "russian",
                        func.coalesce(TaskComment.author_name, ""),
                        ts_query,
                        TITLE_HEADLINE_OPTIONS,
                    ).label("author_headline"),
                )
                .where(
                    TaskComment.task_id.in_(task_ids),
                    TaskComment.search_vector.op("@@")(ts_query),
                )
                .order_by(TaskComment.task_id, TaskComment.created_at.desc())
            )
            rows = (await self.db_session.execute(stmt)).mappings().all()
            highlights: dict[int, dict[str, str]] = {}
            for row in rows:
                task_id = row["task_id"]
                if task_id in highlights:
                    continue
                if HIGHLIGHT_START in row["body_headline"]:
                    highlights[task_id] = {
                        "search_match_source": "comment",
                        "search_excerpt": row["body_headline"],
                    }
                elif HIGHLIGHT_START in row["author_headline"]:
                    highlights[task_id] = {
                        "search_match_source": "comment_author",
                        "search_excerpt": row["author_headline"],
                    }
            return highlights
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подготовить подсветку комментариев.", exc_info=True)
            raise TaskCommentsRepositoryError("Ошибка подсветки комментариев.") from error

    async def save(self, task_id: int, author_name: str | None, body_md: str) -> TaskComment:
        """Создаёт комментарий задачи.

        Args:
            task_id: Идентификатор задачи.
            author_name: Необязательная подпись автора.
            body_md: Текст комментария.

        Returns:
            Сохранённый комментарий.

        Raises:
            TaskCommentsRepositoryError: Если сохранить комментарий не удалось.
        """
        try:
            comment = TaskComment(task_id=task_id, author_name=author_name, body_md=body_md)
            self.db_session.add(comment)
            await self.db_session.commit()
            await self.db_session.refresh(comment)
            return comment
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось сохранить комментарий задачи id=%s.", task_id, exc_info=True
            )
            raise TaskCommentsRepositoryError(
                f"Ошибка сохранения комментария задачи id={task_id}."
            ) from error

    async def delete(self, comment: TaskComment) -> None:
        """Удаляет комментарий задачи.

        Args:
            comment: Удаляемая ORM-модель комментария.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            TaskCommentsRepositoryError: Если удалить комментарий не удалось.
        """
        try:
            await self.db_session.delete(comment)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить комментарий id=%s.", comment.id, exc_info=True)
            raise TaskCommentsRepositoryError(
                f"Ошибка удаления комментария id={comment.id}."
            ) from error
