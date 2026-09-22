from typing import Any

from sqlalchemy import Result, insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.agent_conversations import AgentConversation
from src.exceptions.agent_conversations import AgentConversationsRepositoryError


class AgentConversationsRepository:
    """Хранение диалогов; транзакцией владеет сервис."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def get_page(
        self, project_id: int, user_id: int, *, offset: int, limit: int
    ) -> list[AgentConversation]:
        """Возвращает страницу диалогов участника.

        Args:
            project_id: Проект поиска.
            user_id: Владелец переписки.
            offset: Смещение страницы.
            limit: Максимум строк.
        Returns:
            Диалоги от недавних к старым.
        Raises:
            AgentConversationsRepositoryError: При ошибке PostgreSQL.
        """
        result = await self._execute(
            select(AgentConversation)
            .where(
                AgentConversation.project_id == project_id,
                AgentConversation.user_id == user_id,
            )
            .order_by(AgentConversation.updated_at.desc(), AgentConversation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars())

    async def get_owned(
        self, conversation_id: int, project_id: int, user_id: int, *, lock: bool = False
    ) -> AgentConversation | None:
        """Находит диалог только внутри области доступа.

        Args:
            conversation_id: ID диалога.
            project_id: Проект из серверного контекста.
            user_id: Пользователь из серверного контекста.
            lock: Сериализовать изменение диалога до конца транзакции.
        Returns:
            Доступный диалог либо None.
        Raises:
            AgentConversationsRepositoryError: При ошибке PostgreSQL.
        """
        statement = select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.project_id == project_id,
            AgentConversation.user_id == user_id,
        )
        if lock:
            statement = statement.with_for_update()
        return (await self._execute(statement)).scalar_one_or_none()

    async def get_by_id(self, conversation_id: int) -> AgentConversation | None:
        """Читает область задания для worker-а, который затем проверяет участие.

        Args:
            conversation_id: ID из сохранённого задания.
        Returns:
            Диалог либо None после каскадного удаления.
        Raises:
            AgentConversationsRepositoryError: При ошибке PostgreSQL.
        """
        return (
            await self._execute(
                select(AgentConversation).where(AgentConversation.id == conversation_id)
            )
        ).scalar_one_or_none()

    async def save(self, data: dict[str, Any]) -> AgentConversation:
        """Сохраняет диалог в текущей транзакции.

        Args:
            data: Поля нового диалога.
        Returns:
            Запись с серверными значениями.
        Raises:
            AgentConversationsRepositoryError: При ошибке PostgreSQL.
        """
        return (
            await self._execute(
                insert(AgentConversation).values(**data).returning(AgentConversation)
            )
        ).scalar_one()

    async def update(self, conversation_id: int, data: dict[str, Any]) -> None:
        """Обновляет название или память диалога без промежуточного commit.

        Args:
            conversation_id: ID изменяемого диалога.
            data: Проверенные сервисом поля.
        Raises:
            AgentConversationsRepositoryError: При ошибке PostgreSQL.
        """
        await self._execute(
            update(AgentConversation).where(AgentConversation.id == conversation_id).values(**data)
        )

    async def _execute(self, statement: Any) -> Result[Any]:
        try:
            return await self.db_session.execute(statement)
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise AgentConversationsRepositoryError(
                "Не удалось выполнить запрос к диалогам."
            ) from error
