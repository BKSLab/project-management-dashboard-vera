"""Единый контракт содержательных источников и связей внутри проекта.

Реестр используется чтением PostgreSQL, FTS, индексатором, агентом и
проверкой покрытия модели. Политика новой таблицы должна быть задана явно.
"""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from src.knowledge.chunking import chunk_markdown
from src.knowledge.documents import KnowledgeDocument
from src.utils.checklists import checklist_text

SCHEMA_VERSION = 2


class SourceType(StrEnum):
    PROJECT = "project"
    TASK = "task"
    DOCUMENT = "document"
    COMMENT = "comment"
    ATTACHMENT = "attachment"
    MILESTONE = "milestone"
    RISK = "risk"
    WBS_NODE = "wbs_node"
    STAGE = "stage"
    STICKER = "sticker"
    MEMBER = "member"
    ACTIVITY = "activity"
    DEADLINE_CHANGE = "deadline_change"
    ANALYTICS_REPORT = "analytics_report"


@dataclass(frozen=True)
class SourcePolicy:
    table: str
    scope: str
    kind: SourceType | None
    label: str
    fields: tuple[str, ...]
    semantic: tuple[str, ...] = ()
    title_field: str = "title"


def policy(table, scope, kind, label, fields, semantic="", title="title"):
    return SourcePolicy(
        table, scope, kind, label, tuple(fields.split()), tuple(semantic.split()), title
    )


POLICIES = (
    policy(
        "projects",
        "self",
        SourceType.PROJECT,
        "Проект",
        "id owner_id key name description_md status start_date due_date description_sections due_date_has_been_set created_at updated_at",
        "description_md",
        "name",
    ),
    policy(
        "tasks",
        "project",
        SourceType.TASK,
        "Задача",
        "id project_id stage_id wbs_node_id number title description_md checklist checklist_revision priority role assignee start_date due_date baseline_start_date baseline_due_date completed_at position wbs_position created_at updated_at",
        "description_md checklist",
    ),
    policy(
        "documents",
        "project",
        SourceType.DOCUMENT,
        "Документ",
        "id project_id slug title content_md origin_attachment_id created_at updated_at",
        "content_md",
    ),
    policy(
        "task_comments",
        "task",
        SourceType.COMMENT,
        "Комментарий",
        "id task_id author_name body_md created_at",
        "author_name body_md",
        "author_name",
    ),
    policy(
        "task_attachments",
        "task",
        SourceType.ATTACHMENT,
        "Вложение",
        "id task_id original_name storage_key content_type size created_at",
        "",
        "original_name",
    ),
    policy(
        "project_milestones",
        "project",
        SourceType.MILESTONE,
        "Веха",
        "id project_id title description_md due_date status wbs_node_id created_at updated_at",
        "description_md",
    ),
    policy(
        "project_risks",
        "project",
        SourceType.RISK,
        "Риск",
        "id project_id task_id title description mitigation_plan response_plan probability impact risk_level status response_strategy owner_user_id review_date source created_at updated_at",
        "description mitigation_plan response_plan",
    ),
    policy(
        "wbs_nodes",
        "project",
        SourceType.WBS_NODE,
        "Раздел ИСР",
        "id project_id parent_id title position created_at updated_at",
    ),
    policy(
        "project_stages",
        "project",
        SourceType.STAGE,
        "Стадия канбана",
        "id project_id name order_index color is_done_stage",
        "",
        "name",
    ),
    policy(
        "project_stickers",
        "project",
        SourceType.STICKER,
        "Стикер",
        "id project_id body color created_by_user_id created_by_username_snapshot created_by_display_name_snapshot revision created_at updated_at",
        "body created_by_display_name_snapshot",
        "body",
    ),
    policy(
        "project_members",
        "project",
        SourceType.MEMBER,
        "Участник команды",
        "id project_id user_id role created_at updated_at",
        "role",
    ),
    policy(
        "task_activity",
        "task",
        SourceType.ACTIVITY,
        "История задачи",
        "id task_id event_type from_value to_value created_at",
        "event_type from_value to_value",
        "event_type",
    ),
    policy(
        "project_deadline_changes",
        "project",
        SourceType.DEADLINE_CHANGE,
        "История срока проекта",
        "id project_id previous_due_date new_due_date changed_by_user_id changed_by_name comment created_at",
        "previous_due_date new_due_date changed_by_name comment",
        "comment",
    ),
    policy(
        "analytics_reports",
        "project",
        SourceType.ANALYTICS_REPORT,
        "Сохранённый аналитический свод",
        "id project_id created_by_user_id created_by_display_name_snapshot llm_model payload context_summary created_at",
        "payload context_summary",
        "created_at",
    ),
    # Связи входят в граф обоих концов; голые идентификаторы не образуют embeddings.
    policy("document_links", "task", None, "Документ задачи", "id document_id task_id"),
    policy("project_sticker_task_links", "task", None, "Стикер задачи", "sticker_id task_id"),
    policy(
        "task_dependencies",
        "project",
        None,
        "Зависимость задач",
        "id project_id predecessor_task_id successor_task_id dependency_type lag_days created_at",
    ),
    policy(
        "task_participants",
        "task",
        None,
        "Назначение участника",
        "id task_id project_member_id role created_at updated_at",
    ),
    # Только проектная публичная идентичность. Контакты, пароли и токены сюда не попадают.
    policy(
        "users",
        "user",
        None,
        "Профиль участника",
        "id username first_name last_name middle_name is_active",
        "username first_name last_name middle_name",
    ),
    policy(
        "knowledge_attachment_texts",
        "attachment",
        None,
        "Извлечённый текст",
        "attachment_id text status detail original_chars content_hash updated_at",
    ),
)
POLICY_BY_TABLE = {item.table: item for item in POLICIES}
POLICY_BY_TYPE = {item.kind: item for item in POLICIES if item.kind}
EXCLUDED_TABLES = {
    "api_tokens": "Секреты и авторизация не являются знаниями проекта.",
    "knowledge_index_jobs": "Служебная очередь синхронизации.",
}
EXCLUDED_FIELDS = {
    "analytics_reports": {"duration_ms": "Техническая длительность генерации."},
    "documents": {"search_vector": "Производный FTS-индекс."},
    "task_comments": {"search_vector": "Производный FTS-индекс."},
    "project_stickers": {
        key: "Визуальная геометрия доски." for key in ("canvas_x", "canvas_y", "height", "width")
    },
    "projects": {
        key: "Оформление/сортировка либо производный индекс."
        for key in ("color", "icon", "order_index", "search_vector")
    },
    "tasks": {
        key: "Визуальная геометрия либо производный индекс."
        for key in ("canvas_x", "canvas_y", "search_vector")
    },
    "users": {
        key: "Данные учётной записи вне публичной проектной идентичности."
        for key in (
            "avatar_key",
            "created_at",
            "email",
            "password_hash",
            "phone",
            "telegram",
            "updated_at",
        )
    },
}

FIELD_LABELS = {
    "description_md": "Описание",
    "description": "Описание",
    "content_md": "Содержание",
    "checklist": "Чек-лист",
    "body_md": "Комментарий",
    "body": "Заметка",
    "mitigation_plan": "План снижения риска",
    "response_plan": "План при наступлении",
    "author_name": "Автор",
    "created_by_display_name_snapshot": "Автор",
    "role": "Роль",
    "event_type": "Изменение",
    "from_value": "Было",
    "to_value": "Стало",
    "previous_due_date": "Прежний срок",
    "new_due_date": "Новый срок",
    "changed_by_name": "Автор изменения",
    "comment": "Причина",
    "payload": "Выводы модели",
    "context_summary": "Контекст на момент анализа",
}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()


@dataclass
class ProjectSource:
    project_id: int
    kind: SourceType
    entity_id: int
    title: str
    text: str
    properties: dict
    parent_source_id: str | None
    relations: list[dict] = field(default_factory=list)

    @property
    def source_id(self) -> str:
        return f"{self.kind}:{self.entity_id}"

    @property
    def source_hash(self) -> str:
        return digest(
            [SCHEMA_VERSION, self.text, self.properties, self.parent_source_id, self.relations]
        )

    def payload(self) -> dict:
        task_ids = {
            int(link["source_id"].split(":")[1])
            for link in self.relations
            if link["source_id"].startswith("task:")
        }
        if self.kind is SourceType.TASK:
            task_ids.add(self.entity_id)
        owner_task_id = (
            self.properties.get("task_id")
            if self.kind in {SourceType.COMMENT, SourceType.ATTACHMENT, SourceType.ACTIVITY}
            else None
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "project_id": str(self.project_id),
            "entity_type": self.kind.value,
            "entity_id": str(self.entity_id),
            "source_id": self.source_id,
            "title": self.title,
            "parent_source_id": self.parent_source_id,
            "related_source_ids": sorted({link["source_id"] for link in self.relations}),
            "relations": self.relations,
            "task_ids": [str(value) for value in sorted(task_ids)],
            "owner_task_id": str(owner_task_id) if owner_task_id else None,
            "task_id": str(owner_task_id or self.entity_id)
            if owner_task_id or self.kind is SourceType.TASK
            else None,
            "document_slug": self.properties.get("slug"),
            "properties": {
                key: value
                for key, value in self.properties.items()
                if key
                not in {
                    "description_md",
                    "description_sections",
                    "description",
                    "content_md",
                    "body_md",
                    "body",
                    "checklist",
                    "payload",
                    "context_summary",
                    "mitigation_plan",
                    "response_plan",
                }
            },
            "updated_at": self.properties.get("updated_at") or self.properties.get("created_at"),
            "source_hash": self.source_hash,
            "provenance": "generated_analysis"
            if self.kind is SourceType.ANALYTICS_REPORT
            else "project_record",
        }

    def chunks(self, target_chars: int, overlap_chars: int) -> list[KnowledgeDocument]:
        chunks = chunk_markdown(self.text, target_chars=target_chars, overlap_chars=overlap_chars)
        payload = self.payload()
        return [
            KnowledgeDocument(
                point_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"project-knowledge:{self.project_id}:{self.source_id}:{index}",
                    )
                ),
                text=f"{self.title}\n{chunk.text}",
                payload={
                    **payload,
                    "chunk_index": index,
                    "chunks_count": len(chunks),
                    "heading": chunk.heading,
                    "text": f"{self.title}\n{chunk.text}",
                    "text_hash": digest(f"{self.title}\n{chunk.text}"),
                },
            )
            for index, chunk in enumerate(chunks)
        ]


@dataclass
class ProjectCatalog:
    project_id: int
    rows: dict[str, list[dict]]
    sources: dict[str, ProjectSource]

    @property
    def counts(self) -> dict[str, int]:
        found = Counter(source.kind.value for source in self.sources.values())
        return {kind.value: found[kind.value] for kind in SourceType}

    def link(self, left: str, right: str, relation: str, reverse: str, **attributes) -> None:
        # Оба конца разрешаются по актуальному каталогу ОДНОГО проекта.
        if left not in self.sources or right not in self.sources or left == right:
            return
        for source_id, target_id, name in ((left, right, relation), (right, left, reverse)):
            link = {"source_id": target_id, "relation": name, **attributes}
            if link not in self.sources[source_id].relations:
                self.sources[source_id].relations.append(link)


def build_catalog(project_id: int, rows: dict[str, list[dict]]) -> ProjectCatalog:
    catalog = ProjectCatalog(project_id, rows, {})
    project = next(iter(rows.get("projects", [])), None)
    if project is None or project["id"] != project_id:
        return catalog
    users = {user["id"]: user for user in rows.get("users", [])}
    attachments_text = {
        item["attachment_id"]: item for item in rows.get("knowledge_attachment_texts", [])
    }
    task_keys = {row["id"]: f"{project['key']}-{row['number']}" for row in rows.get("tasks", [])}
    for rule in POLICIES:
        if rule.kind is None:
            continue
        for row in rows.get(rule.table, []):
            properties = {
                key: value
                for key, value in row.items()
                if key not in {"storage_key", "extracted_text"}
            }
            title = str(row.get(rule.title_field) or rule.label).strip()
            if rule.title_field in rule.semantic:
                # Стикер/комментарий уже входит в текст целиком; коротко только название.
                title = title[:200]
            if rule.kind is SourceType.PROJECT:
                title = f"{project['key']} · {title}"
            elif rule.kind is SourceType.TASK:
                title = f"{task_keys[row['id']]} · {title}"
            elif rule.kind is SourceType.RISK:
                title = f"RISK-{row['id']} · {title}"
            text_parts = [f"Тип: {rule.label}", f"Проект: {project['key']}", f"# {title}"]
            if row.get("task_id") in task_keys:
                text_parts.append(f"Задача: {task_keys[row['task_id']]}")
            for name in rule.semantic:
                value = row.get(name)
                if value is None or value == "":
                    continue
                if name == "checklist":
                    text_parts.append(checklist_text(value))
                else:
                    rendered = (
                        json.dumps(value, ensure_ascii=False, indent=2)
                        if isinstance(value, (dict, list))
                        else str(value)
                    )
                    text_parts.append(f"## {FIELD_LABELS.get(name, name)}\n{rendered}")
            if rule.kind is SourceType.MEMBER:
                user = users.get(row["user_id"], {})
                properties["user"] = user
                title = " ".join(
                    user.get(part) or "" for part in ("last_name", "first_name", "middle_name")
                ).strip() or user.get("username", "Участник")
                text_parts.extend([f"Имя: {title}", f"Логин: {user.get('username', '')}"])
            if rule.kind is SourceType.ATTACHMENT:
                extracted = attachments_text.get(row["id"], {})
                properties["extraction"] = {
                    key: value
                    for key, value in extracted.items()
                    if key not in {"text", "attachment_id", "updated_at"}
                }
                if extracted.get("text"):
                    text_parts.append(f"## Содержимое файла\n{extracted['text']}")
                else:
                    properties["extraction"].setdefault("status", "pending")
            if rule.kind is SourceType.ANALYTICS_REPORT:
                text_parts.insert(
                    0,
                    "Сохранённый вывод AI на дату создания. Это исторический анализ, не первичные факты.",
                )
            parent = None if rule.kind is SourceType.PROJECT else f"project:{project_id}"
            if rule.scope == "task":
                parent = f"task:{row['task_id']}"
            if rule.kind is SourceType.WBS_NODE and row.get("parent_id"):
                parent = f"wbs_node:{row['parent_id']}"
            source = ProjectSource(
                project_id, rule.kind, row["id"], title, "\n\n".join(text_parts), properties, parent
            )
            catalog.sources[source.source_id] = source
    for source in list(catalog.sources.values()):
        if source.parent_source_id:
            catalog.link(source.source_id, source.parent_source_id, "belongs_to", "contains")
    for row in rows.get("tasks", []):
        catalog.link(f"task:{row['id']}", f"stage:{row['stage_id']}", "in_stage", "has_task")
        catalog.link(
            f"task:{row['id']}", f"wbs_node:{row.get('wbs_node_id')}", "in_wbs", "has_task"
        )
    for row in rows.get("project_risks", []):
        catalog.link(f"risk:{row['id']}", f"task:{row.get('task_id')}", "risk_of", "has_risk")
        for member in rows.get("project_members", []):
            if member["user_id"] == row.get("owner_user_id"):
                catalog.link(f"risk:{row['id']}", f"member:{member['id']}", "owned_by", "owns_risk")
    for row in rows.get("document_links", []):
        catalog.link(
            f"document:{row['document_id']}",
            f"task:{row['task_id']}",
            "document_of",
            "has_document",
        )
    for row in rows.get("project_sticker_task_links", []):
        catalog.link(
            f"sticker:{row['sticker_id']}", f"task:{row['task_id']}", "note_of", "has_sticker"
        )
    for row in rows.get("task_dependencies", []):
        catalog.link(
            f"task:{row['predecessor_task_id']}",
            f"task:{row['successor_task_id']}",
            "precedes",
            "depends_on",
            dependency_type=row["dependency_type"],
            lag_days=row["lag_days"],
        )
    for row in rows.get("task_participants", []):
        catalog.link(
            f"task:{row['task_id']}",
            f"member:{row['project_member_id']}",
            "participant",
            "participates_in",
            role=row["role"],
        )
    for row in rows.get("project_milestones", []):
        catalog.link(
            f"milestone:{row['id']}",
            f"wbs_node:{row.get('wbs_node_id')}",
            "in_wbs",
            "has_milestone",
        )
    for row in rows.get("documents", []):
        catalog.link(
            f"document:{row['id']}",
            f"attachment:{row.get('origin_attachment_id')}",
            "derived_from",
            "represented_by",
        )
    for member in rows.get("project_members", []):
        if member["user_id"] == project["owner_id"]:
            catalog.link(f"project:{project_id}", f"member:{member['id']}", "managed_by", "manages")
    for source in catalog.sources.values():
        source.relations.sort(key=lambda link: (link["relation"], link["source_id"], digest(link)))
    return catalog
