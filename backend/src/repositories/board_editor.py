"""Хранилище metadata и транзакционный перенос доски."""

import logging

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.board_shapes import BoardShape
from src.db.models.project_boards import ProjectBoard
from src.db.models.project_stickers import ProjectSticker
from src.exceptions.project_boards import ProjectBoardsRepositoryError
from src.exceptions.unit_of_work import UnitOfWorkRepositoryError
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.board_editor import BoardEditorMetadata

logger = logging.getLogger(__name__)


class BoardPromotionUnitOfWork(UnitOfWork):
    """Вложенное создание проекта делает flush, общий commit делает promotion."""

    async def commit(self) -> None:
        try:
            await self.db_session.flush()
        except SQLAlchemyError as error:
            raise UnitOfWorkRepositoryError(
                "Ошибка подготовки проекта к переносу доски."
            ) from error


class BoardEditorRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_board(self, board_id: int, *, lock: bool = False) -> ProjectBoard | None:
        """Перечитывает строку; lock сериализует metadata, перенос и batch редактора."""
        try:
            query = (
                select(ProjectBoard)
                .where(
                    ProjectBoard.id == board_id,
                    ProjectBoard.archived_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
            if lock:
                query = query.with_for_update()
            return (await self.db_session.execute(query)).scalar_one_or_none()
        except SQLAlchemyError as error:
            raise ProjectBoardsRepositoryError("Ошибка чтения metadata доски.") from error

    async def refs_exist(self, board_id: int, refs: set[tuple[str, int]]) -> bool:
        """Ссылки только внутри доски; key-share защищает их от удаления до commit."""
        try:
            for kind, model in (("shape", BoardShape), ("sticker", ProjectSticker)):
                ids = {object_id for ref_kind, object_id in refs if ref_kind == kind}
                if not ids:
                    continue
                query = (
                    select(model.id)
                    .where(
                        model.board_id == board_id,
                        model.id.in_(ids),
                    )
                    .with_for_update(read=True, key_share=True)
                )
                existing = set((await self.db_session.execute(query)).scalars())
                if existing != ids:
                    return False
            return True
        except SQLAlchemyError as error:
            raise ProjectBoardsRepositoryError("Ошибка проверки объектов metadata.") from error

    async def save_metadata(self, board: ProjectBoard, metadata: BoardEditorMetadata) -> None:
        """Вызывать только после блокировки строки и проверки revision."""
        try:
            board.editor_metadata = metadata.model_dump(mode="json")
            board.revision += 1
            await self.db_session.flush()
        except SQLAlchemyError as error:
            raise ProjectBoardsRepositoryError("Ошибка сохранения metadata доски.") from error

    async def bump_revision(self, board: ProjectBoard) -> None:
        """Вызывать под блокировкой строки при изменении сцены без metadata."""
        try:
            board.revision += 1
            await self.db_session.flush()
        except SQLAlchemyError as error:
            raise ProjectBoardsRepositoryError("Ошибка сохранения ревизии доски.") from error

    async def remove_project_default_boards(self, project_id: int) -> list[int]:
        """Удаляет только пустую доску нового незакоммиченного проекта."""
        try:
            result = await self.db_session.execute(
                delete(ProjectBoard)
                .where(
                    ProjectBoard.project_id == project_id,
                    ~select(BoardShape.id).where(BoardShape.board_id == ProjectBoard.id).exists(),
                    ~select(ProjectSticker.id)
                    .where(ProjectSticker.board_id == ProjectBoard.id)
                    .exists(),
                )
                .returning(ProjectBoard.id)
            )
            return list(result.scalars())
        except SQLAlchemyError as error:
            raise ProjectBoardsRepositoryError("Ошибка замены пустой доски проекта.") from error

    async def move_stickers_to_project(self, board_id: int, project_id: int) -> None:
        try:
            await self.db_session.execute(
                update(ProjectSticker)
                .where(ProjectSticker.board_id == board_id)
                .values(
                    project_id=project_id,
                    revision=ProjectSticker.revision + 1,
                    updated_at=func.now(),
                )
            )
        except SQLAlchemyError as error:
            raise ProjectBoardsRepositoryError("Ошибка переноса стикеров в проект.") from error

    async def attach_to_new_project(self, board: ProjectBoard, project_id: int) -> None:
        """ORM flush получает timestamps из RETURNING (Base.eager_defaults)."""
        try:
            board.project_id = project_id
            board.position = 0
            board.revision += 1
            await self.db_session.flush()
        except SQLAlchemyError as error:
            raise ProjectBoardsRepositoryError("Ошибка переноса доски в проект.") from error
