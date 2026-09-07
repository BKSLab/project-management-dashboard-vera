"""Один проектный SQL-срез и FTS по тому же реестру источников."""

from collections import defaultdict

from sqlalchemy import Integer, Text, cast, func, literal, select, true, union_all
from sqlalchemy.dialects.postgresql import JSONB, REGCONFIG, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Base
from src.db.models.knowledge_attachment_texts import KnowledgeAttachmentText
from src.exceptions.knowledge import KnowledgeIndexJobsRepositoryError
from src.knowledge.catalog import POLICIES, SourcePolicy, SourceType


def _select_rows(rule: SourcePolicy, project_id: int):
    """Строит SELECT только по явно разрешённым полям и путям принадлежности."""
    tables = Base.metadata.tables
    table = tables[rule.table]
    from_clause = table
    if rule.scope == "self":
        condition = table.c.id == project_id
    elif rule.scope == "project":
        condition = table.c.project_id == project_id
    elif rule.scope == "task":
        tasks = tables["tasks"]
        from_clause = table.join(tasks, table.c.task_id == tasks.c.id)
        condition = tasks.c.project_id == project_id
    elif rule.scope == "user":
        members = tables["project_members"]
        from_clause = table.join(members, members.c.user_id == table.c.id)
        condition = members.c.project_id == project_id
    else:
        attachments, tasks = tables["task_attachments"], tables["tasks"]
        from_clause = table.join(attachments, table.c.attachment_id == attachments.c.id).join(
            tasks, attachments.c.task_id == tasks.c.id
        )
        condition = tasks.c.project_id == project_id
    fields = [part for name in rule.fields for part in (literal(name), table.c[name])]
    if rule.table == "tasks" or rule.scope == "task":
        projects = tables["projects"]
        tasks = tables["tasks"]
        number = table.c.number if rule.table == "tasks" else tasks.c.number
        project_key = select(projects.c.key).where(projects.c.id == project_id).scalar_subquery()
        fields.extend([literal("task_key"), func.concat(project_key, "-", number)])
    if rule.table == "project_members":
        users = tables["users"]
        from_clause = from_clause.join(users, table.c.user_id == users.c.id)
        for name in ("username", "first_name", "last_name", "middle_name"):
            fields.extend([literal(name), users.c[name]])
    if rule.table == "task_attachments":
        cache = tables["knowledge_attachment_texts"]
        from_clause = from_clause.outerjoin(cache, table.c.id == cache.c.attachment_id)
        fields.extend([literal("extracted_text"), cache.c.text])
    return (
        select(
            literal(rule.table).label("table_name"),
            literal(rule.kind.value if rule.kind else "").label("entity_type"),
            cast(func.jsonb_build_object(*fields), JSONB).label("data"),
        )
        .select_from(from_clause)
        .where(condition)
    )


class KnowledgeSourcesRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_project_rows(self, project_id: int) -> dict[str, list[dict]]:
        """Один statement даёт согласованный снимок, включая связи и пустые разделы."""
        try:
            rows = await self.db_session.execute(
                union_all(*[_select_rows(rule, project_id) for rule in POLICIES])
            )
            result = defaultdict(list)
            for table, _, data in rows:
                result[table].append(data)
            return dict(result)
        except SQLAlchemyError as error:
            raise KnowledgeIndexJobsRepositoryError(
                "Не удалось прочитать источники проекта."
            ) from error

    async def search(
        self,
        project_id: int,
        query: str,
        *,
        entity_type: SourceType | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> list[dict]:
        """FTS всех источников, независимо от доступности embeddings и Qdrant.

        Проектные FK ограничивают объём до построения tsvector. Извлечённый
        текст файлов хранится локально и участвует в этом же поиске.
        """
        rules = [
            rule
            for rule in POLICIES
            if rule.kind and (entity_type is None or rule.kind == entity_type)
        ]
        sources = union_all(*[_select_rows(rule, project_id) for rule in rules]).subquery()
        searchable = sources.c.data.op("-")(literal("storage_key"))
        language = cast(literal("russian"), REGCONFIG)
        search_text = cast(searchable, Text)
        # Один tsvector ограничен PostgreSQL по размеру и позициям. Окна с
        # перекрытием сохраняют поиск в хвосте больших файлов без обрезки.
        parts = (
            func.generate_series(0, cast(func.floor(func.length(search_text) / 16000), Integer))
            .table_valued("part")
            .render_derived()
            .lateral()
        )
        vector = func.to_tsvector(
            language, func.substr(search_text, parts.c.part * 16000 + 1, 18048)
        )
        terms = func.websearch_to_tsquery(language, query)
        rank = func.max(func.ts_rank_cd(vector, terms))
        entity_id = sources.c.data["id"].astext
        try:
            rows = await self.db_session.execute(
                select(sources.c.entity_type, entity_id, rank.label("rank"))
                .select_from(sources.join(parts, true()))
                .where(vector.op("@@")(terms))
                .group_by(sources.c.entity_type, entity_id)
                .order_by(rank.desc(), sources.c.entity_type, entity_id)
                .offset(offset)
                .limit(limit)
            )
            return [
                {"source_id": f"{kind}:{id_}", "rank": float(score)} for kind, id_, score in rows
            ]
        except SQLAlchemyError as error:
            raise KnowledgeIndexJobsRepositoryError(
                "Не удалось выполнить поиск по источникам проекта."
            ) from error

    async def save_extraction(self, data: dict) -> None:
        """Сохраняет результат файла; транзакцией управляет владелец DB-области."""
        statement = insert(KnowledgeAttachmentText).values(**data)
        try:
            await self.db_session.execute(
                statement.on_conflict_do_update(
                    index_elements=[KnowledgeAttachmentText.attachment_id],
                    set_={**data, "updated_at": func.now()},
                )
            )
        except SQLAlchemyError as error:
            raise KnowledgeIndexJobsRepositoryError(
                "Не удалось сохранить результат извлечения файла."
            ) from error
