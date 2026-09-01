import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.wbs_nodes import WbsNode
from src.exceptions.wbs_nodes import WbsNodesRepositoryError

logger = logging.getLogger(__name__)


class WbsNodesRepository:
    """Репозиторий структурных узлов ИСР."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_project(self, project_id: int) -> list[WbsNode]:
        """Возвращает все узлы ИСР проекта.

        Дерево проекта невелико, поэтому оно всегда загружается целиком: это
        позволяет сервису считать номера, проверять циклы и строить ответ без
        рекурсивных запросов и N+1.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Узлы проекта, упорядоченные по уровню и позиции.

        Raises:
            WbsNodesRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(WbsNode)
                .where(WbsNode.project_id == project_id)
                .order_by(WbsNode.parent_id, WbsNode.position, WbsNode.id)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить структуру ИСР проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise WbsNodesRepositoryError(
                f"Ошибка получения структуры ИСР проекта id={project_id}."
            ) from error

    async def get_by_id(self, node_id: int) -> WbsNode | None:
        """Возвращает узел ИСР по идентификатору.

        Args:
            node_id: Идентификатор узла.

        Returns:
            Найденный узел или ``None``.

        Raises:
            WbsNodesRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(WbsNode).where(WbsNode.id == node_id)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить узел ИСР id=%s.", node_id, exc_info=True)
            raise WbsNodesRepositoryError(f"Ошибка получения узла ИСР id={node_id}.") from error

    async def save(self, data: dict) -> WbsNode:
        """Создаёт узел ИСР и возвращает сохранённую модель.

        Args:
            data: Поля нового узла.

        Returns:
            Сохранённый узел.

        Raises:
            WbsNodesRepositoryError: Если сохранить узел не удалось.
        """
        try:
            node = WbsNode(**data)
            self.db_session.add(node)
            await self.db_session.commit()
            await self.db_session.refresh(node)
            return node
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить узел ИСР.", exc_info=True)
            raise WbsNodesRepositoryError("Ошибка сохранения узла ИСР.") from error

    async def update(self, node: WbsNode, data: dict) -> WbsNode:
        """Обновляет узел ИСР и возвращает сохранённую модель.

        Args:
            node: Изменяемая ORM-модель узла.
            data: Новые значения полей.

        Returns:
            Обновлённый узел.

        Raises:
            WbsNodesRepositoryError: Если обновить узел не удалось.
        """
        try:
            for field, value in data.items():
                setattr(node, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(node)
            return node
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить узел ИСР id=%s.", node.id, exc_info=True)
            raise WbsNodesRepositoryError(f"Ошибка обновления узла ИСР id={node.id}.") from error

    async def update_positions(self, positions: dict[int, float]) -> None:
        """Переприсваивает позиции набору узлов одной транзакцией.

        Используется при уплотнении разреженных позиций, когда между соседями
        не остаётся свободного промежутка.

        Args:
            positions: Соответствие идентификатора узла новой позиции.

        Returns:
            ``None`` после успешного обновления.

        Raises:
            WbsNodesRepositoryError: Если обновить позиции не удалось.
        """
        if not positions:
            return
        try:
            result: Result = await self.db_session.execute(
                select(WbsNode).where(WbsNode.id.in_(positions))
            )
            for node in result.scalars().all():
                node.position = positions[node.id]
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить позиции узлов ИСР.", exc_info=True)
            raise WbsNodesRepositoryError("Ошибка обновления позиций узлов ИСР.") from error

    async def delete(self, node: WbsNode) -> None:
        """Удаляет узел ИСР вместе с дочерними узлами.

        Args:
            node: Удаляемая ORM-модель узла.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            WbsNodesRepositoryError: Если удалить узел не удалось.
        """
        try:
            await self.db_session.delete(node)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить узел ИСР id=%s.", node.id, exc_info=True)
            raise WbsNodesRepositoryError(f"Ошибка удаления узла ИСР id={node.id}.") from error
