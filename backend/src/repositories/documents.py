import logging

from sqlalchemy import Result, func, select, union
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.db.models.documents import Document
from src.exceptions.documents import (
    DocumentSlugAlreadyExistsRepositoryError,
    DocumentsRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name
from src.utils.fts import (
    EXCERPT_HEADLINE_OPTIONS,
    HIGHLIGHT_START,
    TITLE_HEADLINE_OPTIONS,
    build_ts_query,
    mark_literal_match,
)

logger = logging.getLogger(__name__)


class DocumentsRepository:
    """Репозиторий для работы с документами в базе данных."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self, search: str | None = None) -> list[Document]:
        """Возвращает документы с опциональным поисковым фильтром.

        Args:
            search: Полнотекстовый запрос или ``None``.

        Returns:
            Список найденных документов.

        Raises:
            DocumentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(Document).order_by(Document.title)
            search_text = search.strip() if search else ""
            if search_text:
                ts_query = build_ts_query(search_text)
                escaped_slug = (
                    search_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                )
                document_fts = aliased(Document)
                document_by_slug = aliased(Document)
                matching_document_ids = union(
                    select(document_fts.id).where(
                        document_fts.search_vector.op("@@")(ts_query),
                    ),
                    select(document_by_slug.id).where(
                        document_by_slug.slug.ilike(f"%{escaped_slug}%", escape="\\"),
                    ),
                )
                stmt = stmt.where(Document.id.in_(matching_document_ids))
            result: Result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить список документов.", exc_info=True)
            raise DocumentsRepositoryError(
                error_details="Ошибка при получении списка документов."
            ) from error

    async def get_search_highlights(
        self,
        document_ids: list[int],
        search: str,
    ) -> dict[int, dict[str, str]]:
        """Возвращает источник и размеченный фрагмент совпадения для документов.

        Args:
            document_ids: Идентификаторы отображаемых документов.
            search: Полнотекстовый запрос.

        Returns:
            Поисковый контекст по идентификаторам документов.

        Raises:
            DocumentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not document_ids or not search.strip():
            return {}

        try:
            ts_query = build_ts_query(search)
            title_vector = func.to_tsvector("russian", func.coalesce(Document.title, ""))
            content_vector = func.to_tsvector("russian", func.coalesce(Document.content_md, ""))
            stmt = select(
                Document.id,
                Document.slug,
                title_vector.op("@@")(ts_query).label("title_matches"),
                content_vector.op("@@")(ts_query).label("content_matches"),
                func.ts_headline("russian", Document.title, ts_query, TITLE_HEADLINE_OPTIONS).label(
                    "title_headline"
                ),
                func.ts_headline(
                    "russian", Document.content_md, ts_query, EXCERPT_HEADLINE_OPTIONS
                ).label("content_headline"),
            ).where(Document.id.in_(document_ids))
            rows = (await self.db_session.execute(stmt)).mappings().all()

            highlights: dict[int, dict[str, str]] = {}
            for row in rows:
                data: dict[str, str] = {}
                if HIGHLIGHT_START in row["title_headline"]:
                    data["search_title"] = row["title_headline"]

                if row["title_matches"]:
                    data["search_match_source"] = "title"
                elif row["content_matches"]:
                    data["search_match_source"] = "content"
                    data["search_excerpt"] = row["content_headline"]
                else:
                    marked_slug = mark_literal_match(row["slug"], search.strip())
                    if marked_slug is not None:
                        data["search_match_source"] = "slug"
                        data["search_excerpt"] = marked_slug

                if data:
                    highlights[row["id"]] = data
            return highlights
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось подготовить подсветку документов.", exc_info=True)
            raise DocumentsRepositoryError(
                error_details="Ошибка при подготовке подсветки результатов поиска документов."
            ) from error

    async def get_by_slug(self, slug: str) -> Document | None:
        """Возвращает документ по slug.

        Args:
            slug: URL-идентификатор документа.

        Returns:
            Найденный документ или ``None``.

        Raises:
            DocumentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(Document).where(Document.slug == slug)
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить документ slug=%s.", slug, exc_info=True)
            raise DocumentsRepositoryError(
                error_details=f"Ошибка при получении документа. slug={slug}."
            ) from error

    async def get_by_slug_or_id(
        self,
        slug: str | None = None,
        document_id: int | None = None,
    ) -> Document | None:
        """Возвращает документ по одному переданному идентификатору.

        Args:
            slug: Опциональный URL-идентификатор.
            document_id: Опциональный числовой идентификатор.

        Returns:
            Найденный документ или ``None``.

        Raises:
            DocumentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = select(Document)
            if document_id is not None:
                stmt = stmt.where(Document.id == document_id)
            elif slug is not None:
                stmt = stmt.where(Document.slug == slug)
            else:
                return None
            result: Result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить документ по идентификатору.", exc_info=True)
            raise DocumentsRepositoryError("Ошибка получения документа.") from error

    async def get_by_ids(self, document_ids: set[int]) -> list[Document]:
        """Возвращает документы по набору идентификаторов.

        Args:
            document_ids: Идентификаторы документов.

        Returns:
            Найденные документы.

        Raises:
            DocumentsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not document_ids:
            return []
        try:
            result: Result = await self.db_session.execute(
                select(Document).where(Document.id.in_(document_ids))
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить набор документов.", exc_info=True)
            raise DocumentsRepositoryError("Ошибка получения набора документов.") from error

    async def create(self, slug: str, title: str, content_md: str) -> Document:
        """Создаёт новый документ.

        Args:
            slug: Уникальный URL-идентификатор.
            title: Заголовок документа.
            content_md: Markdown-содержимое.

        Returns:
            Сохранённый документ.

        Raises:
            DocumentSlugAlreadyExistsRepositoryError: Если slug уже занят.
            DocumentsRepositoryError: Если сохранить документ не удалось.
        """
        try:
            document = Document(slug=slug, title=title, content_md=content_md)
            self.db_session.add(document)
            await self.db_session.commit()
            await self.db_session.refresh(document)
            return document
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) == "ix_documents_slug":
                logger.warning("⚠️ Документ со slug=%s уже существует.", slug)
                raise DocumentSlugAlreadyExistsRepositoryError(slug=slug) from error
            logger.error("❌ Ограничение БД не позволило создать документ.", exc_info=True)
            raise DocumentsRepositoryError(
                error_details=f"Ошибка ограничения БД при создании документа. slug={slug}."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось создать документ slug=%s.", slug, exc_info=True)
            raise DocumentsRepositoryError(
                error_details=f"Ошибка при создании документа. slug={slug}."
            ) from error

    async def update(self, document: Document, data: dict) -> Document:
        """Обновляет поля документа и сохраняет изменения.

        Args:
            document: Изменяемая ORM-модель документа.
            data: Новые значения полей.

        Returns:
            Обновлённый документ.

        Raises:
            DocumentSlugAlreadyExistsRepositoryError: Если новый slug уже занят.
            DocumentsRepositoryError: Если обновить документ не удалось.
        """
        new_slug = data.get("slug")
        try:
            for field, value in data.items():
                setattr(document, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(document)
            return document
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) == "ix_documents_slug" and isinstance(
                new_slug, str
            ):
                logger.warning("⚠️ Документ со slug=%s уже существует.", new_slug)
                raise DocumentSlugAlreadyExistsRepositoryError(slug=new_slug) from error
            logger.error(
                "❌ Ограничение БД не позволило обновить документ id=%s.",
                document.id,
                exc_info=True,
            )
            raise DocumentsRepositoryError(
                error_details=f"Ошибка ограничения БД при обновлении документа. id={document.id}."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить документ id=%s.", document.id, exc_info=True)
            raise DocumentsRepositoryError(
                error_details=f"Ошибка при обновлении документа. id={document.id}."
            ) from error

    async def delete(self, document: Document) -> None:
        """Удаляет документ.

        Args:
            document: Удаляемая ORM-модель документа.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            DocumentsRepositoryError: Если удалить документ не удалось.
        """
        try:
            await self.db_session.delete(document)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить документ id=%s.", document.id, exc_info=True)
            raise DocumentsRepositoryError(
                error_details=f"Ошибка при удалении документа. id={document.id}."
            ) from error
