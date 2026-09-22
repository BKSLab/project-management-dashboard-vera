"""Исполнение проектных инструментов с журналом, правами и общим commit."""

import json
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel, ValidationError

from src.agent.actions import ProjectAction
from src.agent.tools import AgentToolContext
from src.exceptions.access import AccessServiceError
from src.exceptions.agent_tools import (
    AgentToolAccessError,
    AgentToolConflictError,
    AgentToolOperationError,
    AgentToolsServiceError,
)
from src.exceptions.base import RepositoryError, ServiceError
from src.schemas.agent_tools import AgentToolRunSchema
from src.services.agent_action_helpers import checked_document, checked_task
from src.services.agent_tool_scope import AgentProjectToolScope, AgentProjectToolScopeFactory

logger = logging.getLogger(__name__)


class AgentActionsService:
    """Один контракт действий для внутренних инструментов и MCP-адаптера."""

    def __init__(
        self, *, scope: AgentProjectToolScopeFactory, actions: Sequence[ProjectAction]
    ) -> None:
        self.scope = scope
        self.actions = {action.name: action for action in actions}
        if len(self.actions) != len(actions):
            raise ValueError("Имена проектных действий должны быть уникальны.")

    async def execute(
        self, *, context: AgentToolContext, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Исполняет разрешённый инструмент или сохраняет запрос подтверждения.

        Args:
            context: Проект, участник и ключ исполнения от доверенного транспорта.
            name: Имя зарегистрированной операции.
            arguments: Аргументы, которые пройдут строгую схему операции.
        Returns:
            Данные чтения либо сохранённое действие с состоянием и результатом.
        Raises:
            AgentToolsServiceError: При отказе доступа, конфликте или ошибке хранения.
        """
        definition = self._definition(name)
        try:
            parameters = definition.parameters.model_validate(arguments)
        except ValidationError as error:
            raise AgentToolConflictError("Аргументы не соответствуют схеме инструмента.") from error
        payload = parameters.model_dump(mode="json", exclude_unset=True)
        request_id = self._request_id(context, name, payload) if definition.mutating else None
        logger.info(
            "🚀 Инструмент %s, проект=%s, участник=%s.", name, context.project_id, context.user_id
        )
        async with self._scope() as db:
            actor = await self._authorize(db, context, definition)
            if not definition.mutating:
                return await definition.handler(db, actor, parameters)
            await self._require_execution(db, actor)
            await db.runs.lock_request(actor.project_id, actor.user_id, request_id)
            previous = await db.runs.get_request(actor.project_id, actor.user_id, request_id)
            if previous is not None:
                if previous.tool_name != name or previous.arguments != payload:
                    raise AgentToolConflictError(
                        "Ключ вызова уже использован с другими аргументами."
                    )
                if previous.status in {"completed", "pending", "rejected"}:
                    return self._result(previous)
            if definition.requires_confirmation:
                result = {
                    "preview": await self._preview(db, actor, parameters),
                    "message": "Требуется решение участника по сохранённым параметрам действия.",
                }
                state = "pending"
            else:
                result = await definition.handler(db, actor, parameters)
                state = "completed"
            if previous is None:
                row = await db.runs.save(
                    dict(
                        id=uuid4(),
                        project_id=actor.project_id,
                        user_id=actor.user_id,
                        message_id=actor.message_id,
                        request_id=request_id,
                        tool_name=name,
                        title=definition.title,
                        arguments=payload,
                        status=state,
                        result=result,
                    )
                )
            else:
                row = await db.runs.update(previous.id, dict(status=state, result=result))
            response = self._result(row)
            await db.unit_of_work.commit()
            logger.info("✅ Инструмент %s: %s, действие=%s.", name, state, row.id)
            return response

    async def decide(
        self,
        *,
        context: AgentToolContext,
        action_id: UUID,
        decision: str,
        conversation_id: int | None = None,
    ) -> AgentToolRunSchema:
        """Выполняет конкретное сохранённое действие после решения участника.

        Args:
            context: Участник и проект из аутентифицированного транспорта.
            action_id: ID подготовленного действия.
            decision: approve или reject; аргументы действия здесь не принимаются.
            conversation_id: Диалог из HTTP-маршрута; None для MCP-действия.
        Returns:
            Идемпотентный результат решения; чат продолжится из очереди.
        Raises:
            AgentToolsServiceError: При конфликте состояния, отказе доступа или ошибке записи.
        """
        if not context.can_write or decision not in {"approve", "reject"}:
            raise AgentToolAccessError("Транспорт не разрешает решение по действию.")
        async with self._scope() as db:
            await db.access.ensure_project_access(
                project_id=context.project_id, user_id=context.user_id
            )
            # Сначала блокируем диалог и реплику, затем действие: такой же порядок
            # использует worker, поэтому решение не образует цикл блокировок.
            if conversation_id is not None:
                conversation = await db.conversations.get_owned(
                    conversation_id, context.project_id, context.user_id, lock=True
                )
                if conversation is None:
                    raise AgentToolAccessError("Диалог недоступен.")
                latest = await db.messages.get_page(conversation_id, before_id=None, limit=1)
                if not latest:
                    raise AgentToolAccessError("Диалог не содержит ответов.")
                message = await db.messages.get_for_update(latest[0].id)
            else:
                message = None
            row = await db.runs.get_owned(action_id, context.project_id, context.user_id)
            if row is None or (message is None and row.message_id is not None):
                raise AgentToolAccessError("Действие недоступно в этом контексте.")
            if message is not None and row.message_id != message.id:
                raise AgentToolConflictError(
                    "Диалог уже продолжился. Запросите действие в текущем обсуждении."
                )
            if row.status in {"completed", "rejected"}:
                if (row.status == "completed") != (decision == "approve"):
                    raise AgentToolConflictError("По действию уже принято другое решение.")
                return AgentToolRunSchema.model_validate(row)
            if row.status != "pending" or (
                message is not None and message.status not in {"completed", "failed"}
            ):
                raise AgentToolConflictError(
                    "Дождитесь завершения ответа и обновите состояние действия."
                )
            definition = self._definition(row.tool_name)
            actor = await self._authorize(db, context, definition)
            if decision == "approve":
                parameters = definition.parameters.model_validate(row.arguments)
                if await self._preview(db, actor, parameters) != row.result.get("preview", {}):
                    raise AgentToolConflictError(
                        "Объект изменился после предложения. Отклоните действие и запросите актуальное."
                    )
                result = await definition.handler(db, actor, parameters)
                state = "completed"
            else:
                result = {"message": "Участник отклонил действие. Изменения не применены."}
                state = "rejected"
            result = {**result, "participant_decision": decision}
            updated = await db.runs.update(row.id, {"status": state, "result": result})
            response = AgentToolRunSchema.model_validate(updated)
            if message is not None:
                remaining = await db.runs.get_for_messages([message.id])
                if not any(item.status == "pending" for item in remaining):
                    await db.messages.resume(message.id)
            await db.unit_of_work.commit()
            return response

    def _definition(self, name: str) -> ProjectAction:
        definition = self.actions.get(name)
        if definition is None:
            raise AgentToolConflictError("Инструмент отсутствует в реестре.")
        return definition

    @staticmethod
    def _request_id(context: AgentToolContext, name: str, payload: dict) -> UUID:
        if not context.can_write:
            raise AgentToolAccessError("Этому вызову не разрешено изменять проект.")
        if context.message_id is not None:
            value = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return uuid5(NAMESPACE_URL, f"project-agent:{context.message_id}:{name}:{value}")
        if context.request_id is None:
            raise AgentToolConflictError(
                "Для изменяющего MCP-вызова необходим стабильный request_id."
            )
        return context.request_id

    @staticmethod
    async def _authorize(
        db: AgentProjectToolScope, context: AgentToolContext, definition: ProjectAction
    ) -> AgentToolContext:
        if context.user_id is None:
            raise AgentToolAccessError("Инструменту необходим аутентифицированный участник.")
        grant = await db.access.ensure_project_access(
            project_id=context.project_id, user_id=context.user_id
        )
        if definition.owner_only and not grant.is_owner:
            raise AgentToolAccessError("Действие доступно только владельцу проекта.")
        user = await db.users.get_by_id(context.user_id)
        if user is None or not user.is_active:
            raise AgentToolAccessError("Пользователь больше не активен.")
        name = (
            " ".join(part for part in (user.last_name, user.first_name, user.middle_name) if part)
            or user.username
        )
        return replace(context, username=user.username, display_name=name)

    @staticmethod
    async def _require_execution(db: AgentProjectToolScope, context: AgentToolContext) -> None:
        if context.message_id is None:
            return
        message = await db.messages.get_for_update(context.message_id)
        if message is None or message.status != "processing" or message.run_id != context.run_id:
            raise AgentToolConflictError("Попытка ответа больше не активна.")
        conversation = await db.conversations.get_owned(
            message.conversation_id, context.project_id, context.user_id
        )
        if conversation is None:
            raise AgentToolAccessError("Попытка принадлежит другому проекту или участнику.")

    @staticmethod
    def _result(row) -> dict[str, Any]:
        return {"action": AgentToolRunSchema.model_validate(row).model_dump(mode="json")}

    @staticmethod
    async def _preview(
        db: AgentProjectToolScope, context: AgentToolContext, parameters: BaseModel
    ) -> dict:
        payload = parameters.model_dump(mode="json", exclude_unset=True)
        targets = {}
        if task_id := payload.get("task_id"):
            task = await checked_task(db, context, task_id)
            targets["task"] = {
                "id": task.id,
                "key": task.key,
                "title": task.title,
                "start_date": task.start_date.isoformat() if task.start_date else None,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "updated_at": task.updated_at.isoformat(),
            }
            if (
                "expected_updated_at" in payload
                and task.updated_at != parameters.expected_updated_at
            ):
                raise AgentToolConflictError("Задача изменилась; получите свежую версию.")
        if document_id := payload.get("document_id"):
            await checked_document(db, context, document_id)
            document = await db.documents.get_document(document_id)
            targets["document"] = {
                "id": document.id,
                "title": document.title,
                "updated_at": document.updated_at.isoformat(),
            }
        if comment_id := payload.get("comment_id"):
            from_comment = await db.comments.get_comment(comment_id)
            await checked_task(db, context, from_comment.task_id)
            targets["comment"] = from_comment.model_dump(mode="json")
        if sticker_id := payload.get("sticker_id"):
            items = await db.stickers.list_stickers(context.project_id)
            sticker = next((item for item in items if item.id == sticker_id), None)
            if sticker is None:
                raise AgentToolAccessError("Стикер недоступен.")
            if sticker.revision != payload["revision"]:
                raise AgentToolConflictError("Стикер изменился; получите свежую версию.")
            targets["sticker"] = {
                "id": sticker.id,
                "body": sticker.body,
                "revision": sticker.revision,
            }
        if member_id := payload.get("user_id"):
            items = await db.members.get_member_list(context.project_id)
            member = next((item for item in items if item.user.id == member_id), None)
            if member is None:
                raise AgentToolAccessError("Участник недоступен.")
            targets["member"] = member.model_dump(mode="json")
        if stage_id := payload.get("stage_id"):
            stage = await db.stages.get_stage_in_project(context.project_id, stage_id)
            targets["stage"] = {"id": stage.id, "name": stage.name}
        if node_id := payload.get("node_id"):
            items = (await db.wbs.get_structure(context.project_id)).nodes
            node = next((item for item in items if item.id == node_id), None)
            if node is None:
                raise AgentToolAccessError("Раздел ИСР недоступен.")
            targets["node"] = node.model_dump(mode="json")
        for field, label, fetch in (
            ("milestone_id", "milestone", db.milestones.list_milestones),
            ("dependency_id", "dependency", db.dependencies.list_dependencies),
        ):
            if entity_id := payload.get(field):
                entity = next(
                    (item for item in await fetch(context.project_id) if item.id == entity_id), None
                )
                if entity is None:
                    raise AgentToolAccessError("Объект недоступен в этом проекте.")
                targets[label] = entity.model_dump(mode="json")
        if risk_id := payload.get("risk_id"):
            risk = await db.risks.get_risk(
                project_id=context.project_id, user_id=context.user_id, risk_id=risk_id
            )
            targets["risk"] = {
                "id": risk.id,
                "title": risk.title,
                "updated_at": risk.updated_at.isoformat(),
            }
        if attachment_id := payload.get("attachment_id"):
            attachment = next(
                (
                    item
                    for item in await db.attachments.get_attachments(payload["task_id"])
                    if item.id == attachment_id
                ),
                None,
            )
            if attachment is None:
                raise AgentToolAccessError("Файл недоступен.")
            targets["attachment"] = attachment.model_dump(mode="json")
        if "changes" in payload and isinstance(payload["changes"], list):
            targets["tasks"] = []
            for change in parameters.changes:
                task = await checked_task(db, context, change.task_id)
                if task.updated_at != change.expected_updated_at:
                    raise AgentToolConflictError(
                        "Задача календаря изменилась; получите новый preview."
                    )
                targets["tasks"].append(
                    {
                        "id": task.id,
                        "key": task.key,
                        "title": task.title,
                        "start_date": str(task.start_date) if task.start_date else None,
                        "due_date": str(task.due_date) if task.due_date else None,
                    }
                )
            targets["task_count"] = len(parameters.changes)
        return targets

    @asynccontextmanager
    async def _scope(self) -> AsyncIterator[AgentProjectToolScope]:
        try:
            async with self.scope() as db:
                yield db
        except AccessServiceError as error:
            raise AgentToolAccessError(str(error)) from error
        except RepositoryError as error:
            raise AgentToolsServiceError(str(error)) from error
        except ServiceError as error:
            if isinstance(error, AgentToolsServiceError):
                raise
            raise AgentToolOperationError(error) from error
