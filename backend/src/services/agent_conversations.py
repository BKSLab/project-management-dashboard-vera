"""Сохранение диалогов и выполнение ответов из постоянной очереди."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

from pydantic import BaseModel, Field

from src.agent.tools import AgentToolContext
from src.clients.llm import LlmClient
from src.db.models.agent_conversations import AgentConversation
from src.db.models.agent_messages import AgentMessage
from src.exceptions.access import AccessServiceError, ResourceNotAvailableError
from src.exceptions.agent_conversations import (
    AgentConversationBusyError,
    AgentConversationNotFoundError,
    AgentConversationsServiceError,
    AgentMessageConflictError,
)
from src.exceptions.base import RepositoryError
from src.prompts.agent_memory import AGENT_MEMORY_PROMPT
from src.schemas.agent_conversations import (
    AgentConversationListSchema,
    AgentConversationSchema,
    AgentMessageAcceptedSchema,
    AgentMessageCreateSchema,
    AgentMessagePageSchema,
    AgentMessageSchema,
)
from src.schemas.agent_files import AgentFileSchema
from src.schemas.agent_tools import AgentToolRunSchema
from src.schemas.knowledge import KnowledgeAnswerSchema, KnowledgeChatMessageSchema
from src.services.db_scope import AgentConversationScope, AgentConversationScopeFactory
from src.services.project_agent import ProjectAgentService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentConversationConfig:
    """Явные бюджеты обработки и памяти диалога."""

    turn_timeout_seconds: float
    history_messages: int
    summary_batch_size: int


class ConversationMemory(BaseModel):
    """Память о разговоре, которая никогда не индексируется как факт проекта."""

    summary: str = Field(min_length=1, max_length=12000)


class AgentConversationsService:
    """Владеет транзакциями диалогов; освобождает БД перед каждым вызовом модели."""

    DEFAULT_TITLE = "Новый диалог"
    HISTORY_MESSAGE_CHARS = 8000

    def __init__(
        self,
        *,
        scope: AgentConversationScopeFactory,
        agent: ProjectAgentService,
        llm_client: LlmClient,
        config: AgentConversationConfig,
    ) -> None:
        self.scope = scope
        self.agent = agent
        self.llm_client = llm_client
        self.config = config

    async def list_conversations(
        self, *, project_id: int, user_id: int, offset: int, limit: int
    ) -> AgentConversationListSchema:
        """Возвращает страницу личных диалогов доступного проекта.

        Args:
            project_id: Проект из маршрута.
            user_id: Текущий пользователь.
            offset: Смещение страницы.
            limit: Размер страницы.
        Returns:
            Доступные диалоги и смещение продолжения.
        Raises:
            AgentConversationsServiceError: При отказе доступа или ошибке хранения.
        """
        async with self._scope() as db:
            await db.access.ensure_project_access(project_id=project_id, user_id=user_id)
            rows = await db.conversations.get_page(
                project_id, user_id, offset=offset, limit=limit + 1
            )
            return AgentConversationListSchema(
                items=[AgentConversationSchema.model_validate(row) for row in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    async def create_conversation(
        self, *, project_id: int, user_id: int
    ) -> AgentConversationSchema:
        """Открывает отдельный личный разговор в проекте.

        Args:
            project_id: Проект из маршрута.
            user_id: Автор из аутентифицированной сессии.
        Returns:
            Сохранённый диалог.
        Raises:
            AgentConversationsServiceError: При отказе доступа или ошибке хранения.
        """
        async with self._scope() as db:
            await db.access.ensure_project_access(project_id=project_id, user_id=user_id)
            row = await db.conversations.save(
                dict(project_id=project_id, user_id=user_id, title=self.DEFAULT_TITLE)
            )
            result = AgentConversationSchema.model_validate(row)
            await db.unit_of_work.commit()
            return result

    async def get_messages(
        self,
        *,
        project_id: int,
        user_id: int,
        conversation_id: int,
        before_id: int | None,
        limit: int,
    ) -> AgentMessagePageSchema:
        """Восстанавливает переписку, включая состояние незавершённого ответа.

        Args:
            project_id: Проект из маршрута.
            user_id: Текущий пользователь.
            conversation_id: Выбранный диалог.
            before_id: Граница чтения ранних реплик.
            limit: Размер страницы.
        Returns:
            Хронологическая страница и курсор ранних реплик.
        Raises:
            AgentConversationsServiceError: При отказе доступа или ошибке хранения.
        """
        async with self._scope() as db:
            await self._require(db, project_id, user_id, conversation_id)
            rows = await db.messages.get_page(conversation_id, before_id=before_id, limit=limit + 1)
            page = rows[:limit]
            actions = await db.runs.get_for_messages([row.id for row in page])
            return AgentMessagePageSchema(
                items=[
                    AgentMessageSchema.model_validate(row).model_copy(
                        update={
                            "actions": [
                                AgentToolRunSchema.model_validate(action)
                                for action in actions
                                if action.message_id == row.id
                            ]
                        }
                    )
                    for row in reversed(page)
                ],
                next_before_id=page[-1].id if len(rows) > limit else None,
            )

    async def send_message(
        self, *, project_id: int, user_id: int, conversation_id: int, data: AgentMessageCreateSchema
    ) -> AgentMessageAcceptedSchema:
        """Атомарно сохраняет вопрос и очередь ответа; повтор идемпотентен.

        Args:
            project_id: Проект из маршрута.
            user_id: Текущий пользователь, которого модель не может подменить.
            conversation_id: Диалог вопроса.
            data: Текст и ключ отправки без клиентской истории.
        Returns:
            Сохранённые вопрос и ответ в очереди.
        Raises:
            AgentConversationBusyError: Если предыдущий ответ ещё готовится.
            AgentMessageConflictError: Если ключ отправки повторён с другим текстом.
            AgentConversationsServiceError: При отказе доступа или ошибке хранения.
        """
        async with self._scope() as db:
            conversation = await self._require(db, project_id, user_id, conversation_id, lock=True)
            existing = await db.messages.get_request(conversation_id, data.request_id)
            if existing:
                result = self._accepted(existing)
                if (
                    result.user_message.content != data.content
                    or [item.id for item in result.user_message.files] != data.file_ids
                ):
                    raise AgentMessageConflictError("Ключ отправки использован для другого текста.")
                return result
            if await db.messages.get_active(conversation_id):
                raise AgentConversationBusyError("Диалог уже имеет незавершённый ответ.")
            latest = await db.messages.get_page(conversation_id, before_id=None, limit=1)
            if latest:
                await db.runs.reject_pending(latest[0].id)
            common = dict(conversation_id=conversation_id, request_id=data.request_id)
            files = []
            for file_id in data.file_ids:
                uploaded = await db.uploads.get(file_id)
                if uploaded is None or uploaded.conversation_id != conversation_id:
                    raise AgentConversationNotFoundError("Файл принадлежит другому диалогу.")
                files.append(AgentFileSchema.model_validate(uploaded).model_dump(mode="json"))
            rows = await db.messages.save_pair(
                [
                    {
                        **common,
                        "role": "user",
                        "content": data.content,
                        "status": "completed",
                        "files": files,
                    },
                    {**common, "role": "assistant", "content": "", "status": "queued", "files": []},
                ]
            )
            title = (
                data.content[:120]
                if conversation.title == self.DEFAULT_TITLE
                else conversation.title
            )
            await db.conversations.update(conversation_id, {"title": title})
            result = self._accepted(rows)
            for file_id in data.file_ids:
                await db.uploads.bind_message(file_id, result.user_message.id)
            await db.unit_of_work.commit()
            return result

    async def retry_message(
        self, *, project_id: int, user_id: int, conversation_id: int, message_id: int
    ) -> AgentMessageSchema:
        """Повторяет последний неудачный ответ без дублирования вопроса.

        Args:
            project_id: Проект из маршрута.
            user_id: Текущий пользователь.
            conversation_id: Диалог ответа.
            message_id: Реплика, которую нужно повторить.
        Returns:
            Та же реплика в очереди.
        Raises:
            AgentMessageConflictError: Если диалог уже продолжился или ответ не завершился ошибкой.
            AgentConversationsServiceError: При отказе доступа или ошибке хранения.
        """
        async with self._scope() as db:
            await self._require(db, project_id, user_id, conversation_id, lock=True)
            latest = await db.messages.get_page(conversation_id, before_id=None, limit=1)
            if not latest or latest[0].id != message_id:
                raise AgentMessageConflictError("Можно повторить только последний ответ.")
            if latest[0].status in {"queued", "processing"}:
                return AgentMessageSchema.model_validate(latest[0])
            if latest[0].role != "assistant" or latest[0].status != "failed":
                raise AgentMessageConflictError("Ответ не ожидает повтора.")
            result = AgentMessageSchema.model_validate(await db.messages.retry(message_id))
            await db.unit_of_work.commit()
            return result

    async def process_next(self) -> bool:
        """Выполняет один ответ независимо от времени жизни браузерного запроса.

        Returns:
            True, если очередь содержала задание.
        Raises:
            AgentConversationsServiceError: Если недоступна сама очередь.
        """
        async with self._scope() as db:
            await db.messages.fail_expired(self.config.turn_timeout_seconds)
            message = await db.messages.claim_next(uuid4())
            await db.unit_of_work.commit()
        if message is None:
            return False
        logger.info(
            "🤖 Начало ответа агента id=%s, диалог=%s.", message.id, message.conversation_id
        )
        try:
            async with asyncio.timeout(self.config.turn_timeout_seconds):
                answer = await self._generate(message)
                await self._finish(message, answer=answer)
            logger.info("✅ Ответ агента id=%s сохранён.", message.id)
        except asyncio.CancelledError:
            try:
                await self._finish(
                    message, error="Подготовка ответа прервалась. Можно повторить запрос."
                )
            except Exception:
                # Недоступная БД не должна скрывать отмену и мешать lifespan
                # закрыть остальные ресурсы. Состояние восстановит fail_expired.
                logger.error(
                    "❌ Не удалось сохранить остановку ответа id=%s.", message.id, exc_info=True
                )
            raise
        except Exception:
            # Граница фонового задания: незнакомая ошибка тоже должна стать видимой
            # в сохранённой реплике, а не оставить бесконечный индикатор ожидания.
            logger.error("❌ Ответ агента id=%s не подготовлен.", message.id, exc_info=True)
            await self._finish(
                message, error="Не удалось подготовить ответ. Можно повторить запрос."
            )
        return True

    async def _generate(self, message: AgentMessage) -> KnowledgeAnswerSchema:
        async with self._scope() as db:
            conversation = await db.conversations.get_by_id(message.conversation_id)
            if conversation is None:
                raise AgentConversationNotFoundError("Диалог задания удалён.")
            await self._require(db, conversation.project_id, conversation.user_id, conversation.id)
            user = await db.users.get_by_id(conversation.user_id)
            if user is None or not user.is_active:
                raise AgentConversationNotFoundError("Участник задания больше недоступен.")
            actor = {
                "user_id": user.id,
                "username": user.username,
                "name": " ".join(
                    part for part in (user.last_name, user.first_name, user.middle_name) if part
                )
                or user.username,
            }
            pair = await db.messages.get_request(conversation.id, message.request_id)
            question = next(item for item in pair if item.role == "user")
            recent = await db.messages.get_history(
                conversation.id, before_id=question.id, limit=self.config.history_messages
            )
            action_history = [
                AgentToolRunSchema.model_validate(item).model_dump(mode="json")
                for item in await db.runs.get_for_messages(
                    [message.id, *[item.id for item in recent]]
                )
            ]
            current_actions = await db.runs.get_for_messages([message.id])
            # После решения карточки worker только объясняет результат. Продолжение
            # не получает нового разрешения записи из исходной команды пользователя.
            can_write = not any("participant_decision" in item.result for item in current_actions)
        summary = conversation.summary
        through_id = conversation.summary_through_id
        boundary = recent[-1].id if recent else question.id
        while True:
            async with self._scope() as db:
                await self._require(
                    db, conversation.project_id, conversation.user_id, conversation.id
                )
                earlier = await db.messages.get_for_summary(
                    conversation.id,
                    after_id=through_id,
                    before_id=boundary,
                    limit=self.config.summary_batch_size,
                )
            if not earlier:
                break
            memory = await self.llm_client.get_structured_response(
                system_prompt=AGENT_MEMORY_PROMPT,
                content=json.dumps(
                    {
                        "previous_summary": summary,
                        "messages": [self._history(item).model_dump() for item in earlier],
                    },
                    ensure_ascii=False,
                ),
                schema=ConversationMemory,
                max_completion_tokens=4000,
            )
            summary = memory.summary.replace("\x00", "")
            through_id = earlier[-1].id
            async with self._scope() as db:
                await self._require(
                    db, conversation.project_id, conversation.user_id, conversation.id
                )
                await db.conversations.update(
                    conversation.id, {"summary": summary, "summary_through_id": through_id}
                )
                await db.unit_of_work.commit()
        return await self.agent.ask(
            project_id=conversation.project_id,
            question=question.content,
            history=[self._history(item) for item in reversed(recent)],
            memory=summary,
            actor=actor,
            execution=AgentToolContext(
                project_id=conversation.project_id,
                user_id=conversation.user_id,
                can_write=can_write,
                message_id=message.id,
                run_id=message.run_id,
            ),
            action_history=action_history,
            uploaded_files=[file for item in [*reversed(recent), question] for file in item.files],
        )

    async def _finish(
        self,
        message: AgentMessage,
        *,
        answer: KnowledgeAnswerSchema | None = None,
        error: str | None = None,
    ) -> None:
        async with self._scope() as db:
            if answer is not None:
                conversation = await db.conversations.get_by_id(message.conversation_id)
                if conversation is None:
                    return
                await self._require(
                    db, conversation.project_id, conversation.user_id, conversation.id
                )
            data = (
                {"status": "failed", "error": error}
                if error
                else {
                    "status": "completed",
                    "content": answer.answer.replace("\x00", ""),
                    "sources": [source.model_dump(mode="json") for source in answer.sources],
                    "error": None,
                }
            )
            await db.messages.finish(message.id, message.run_id, data)
            await db.unit_of_work.commit()

    @staticmethod
    async def _require(
        db: AgentConversationScope,
        project_id: int,
        user_id: int,
        conversation_id: int,
        *,
        lock: bool = False,
    ) -> AgentConversation:
        await db.access.ensure_project_access(project_id=project_id, user_id=user_id)
        conversation = await db.conversations.get_owned(
            conversation_id, project_id, user_id, lock=lock
        )
        if conversation is None:
            raise AgentConversationNotFoundError(f"Недоступный диалог id={conversation_id}.")
        return conversation

    @classmethod
    def _history(cls, message: AgentMessage) -> KnowledgeChatMessageSchema:
        content = message.content
        if message.role == "assistant" and message.sources:
            # Карточка без текста тоже должна оставаться понятной при уточнении
            # «измени эту задачу» и при свёртке раннего разговора в память.
            references = [
                f"{source.get('source_id', '')}: {source.get('title', '')}"
                for source in message.sources[:20]
            ]
            content = "Показаны карточки: " + "; ".join(references) + "\n" + content
        if not content.strip():
            content = "Ответ показан карточкой действия."
        if len(content) > cls.HISTORY_MESSAGE_CHARS:
            content = (
                content[: cls.HISTORY_MESSAGE_CHARS - 64]
                + "\n[Длинная реплика сокращена в контексте модели.]"
            )
        return KnowledgeChatMessageSchema(role=message.role, content=content)

    @staticmethod
    def _accepted(rows: list[AgentMessage]) -> AgentMessageAcceptedSchema:
        by_role = {row.role: AgentMessageSchema.model_validate(row) for row in rows}
        return AgentMessageAcceptedSchema(
            user_message=by_role["user"], assistant_message=by_role["assistant"]
        )

    @asynccontextmanager
    async def _scope(self) -> AsyncIterator[AgentConversationScope]:
        try:
            async with self.scope() as db:
                yield db
        except ResourceNotAvailableError as error:
            raise AgentConversationNotFoundError(str(error)) from error
        except (RepositoryError, AccessServiceError) as error:
            raise AgentConversationsServiceError(str(error)) from error
