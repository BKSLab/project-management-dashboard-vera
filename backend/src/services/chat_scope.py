"""Явные зависимости короткой операции чата."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from src.repositories.chat_attachments import ChatAttachmentsRepository
from src.repositories.chat_entity_lookup import ChatEntityLookupRepository
from src.repositories.chat_events import ChatEventsRepository
from src.repositories.chat_message_entities import ChatMessageEntitiesRepository
from src.repositories.chat_message_mentions import ChatMessageMentionsRepository
from src.repositories.chat_messages import ChatMessagesRepository
from src.repositories.chat_participants import ChatParticipantsRepository
from src.repositories.chat_reactions import ChatReactionsRepository
from src.repositories.chat_read_states import ChatReadStatesRepository
from src.repositories.project_chats import ProjectChatsRepository
from src.repositories.unit_of_work import UnitOfWork
from src.services.auth import AuthService


@dataclass
class ChatScope:
    """Ни один экземпляр scope не живёт вместе с WebSocket."""

    chats: ProjectChatsRepository
    messages: ChatMessagesRepository
    entities: ChatMessageEntitiesRepository
    entity_lookup: ChatEntityLookupRepository
    mentions: ChatMessageMentionsRepository
    attachments: ChatAttachmentsRepository
    reactions: ChatReactionsRepository
    reads: ChatReadStatesRepository
    events: ChatEventsRepository
    participants: ChatParticipantsRepository
    auth: AuthService
    unit_of_work: UnitOfWork


ChatScopeFactory = Callable[[], AbstractAsyncContextManager[ChatScope]]
