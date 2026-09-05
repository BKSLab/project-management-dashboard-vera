"""Подготовка выдачи файла задачи до начала передачи.

Скачивание — долгоживущий ответ: он длится столько, сколько клиент качает
файл. Если в графе зависимостей маршрута есть request-scoped сессия, она
остаётся занятой всё это время, и медленный клиент удерживает соединение
с PostgreSQL до конца передачи.

Поэтому вся работа с базой выполняется здесь, в короткой области, а в
фазу передачи уходит только неизменяемый результат: путь, тип, имя и
заголовки.
"""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path

from src.exceptions.access import AccessServiceError
from src.exceptions.auth import AuthServiceError
from src.exceptions.task_attachments import TaskAttachmentsServiceError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AttachmentDownload:
    """Готовый к выдаче файл без единой ссылки на состояние базы.

    Attributes:
        path: Проверенный абсолютный путь файла на диске.
        media_type: MIME-тип для заголовка ответа.
        filename: Исходное имя файла для клиента.
        previewable: Можно ли безопасно показать файл inline.
    """

    path: Path
    media_type: str
    filename: str
    previewable: bool

    @property
    def disposition(self) -> str:
        """Возвращает способ показа: inline либо скачивание."""
        return "inline" if self.previewable else "attachment"


class AttachmentDownloadService:
    """Готовит выдачу файла задачи в одной короткой области базы.

    Сервис не получает сессию: он владеет фабрикой коротких областей и
    закрывает область до того, как начнётся передача файла.
    """

    def __init__(
        self,
        *,
        scope: Callable[[], AbstractAsyncContextManager["AttachmentDownloadScope"]],
    ) -> None:
        self.scope = scope

    async def prepare(
        self,
        *,
        task_id: int,
        attachment_id: int,
        session_token: str | None,
        bearer_secret: str | None,
    ) -> AttachmentDownload:
        """Проверяет доступ и возвращает неизменяемое описание файла.

        Args:
            task_id: Идентификатор задачи.
            attachment_id: Идентификатор файла задачи.
            session_token: Значение cookie сессии, если оно предъявлено.
            bearer_secret: Секрет из заголовка ``Authorization``.

        Returns:
            Данные, достаточные для выдачи файла без обращения к базе.

        Raises:
            AuthServiceError: Если учётные данные недействительны.
            AccessServiceError: Если задача недоступна пользователю.
            TaskAttachmentsServiceError: Если файл не найден или недоступен.
        """
        async with self.scope() as unit:
            principal = await unit.resolve_principal(
                session_token=session_token,
                bearer_secret=bearer_secret,
            )
            await unit.ensure_task_access(task_id=task_id, user_id=principal.user_id)
            content = await unit.load_attachment_content(
                task_id=task_id,
                attachment_id=attachment_id,
            )
            return AttachmentDownload(
                path=content.path,
                media_type=content.content_type,
                filename=content.original_name,
                previewable=content.previewable,
            )


class AttachmentDownloadScope:
    """Одна короткая область базы для подготовки выдачи файла.

    Узкий набор операций вместо доступа к произвольным репозиториям:
    иначе глобальный service locator был бы просто заменён локальным.
    """

    def __init__(self, *, auth_service, access_service, attachments_service) -> None:
        self._auth_service = auth_service
        self._access_service = access_service
        self._attachments_service = attachments_service

    async def resolve_principal(self, *, session_token: str | None, bearer_secret: str | None):
        """Определяет пользователя запроса."""
        return await self._auth_service.resolve_principal(
            session_token=session_token,
            bearer_secret=bearer_secret,
        )

    async def ensure_task_access(self, *, task_id: int, user_id: int):
        """Проверяет доступ пользователя к задаче."""
        return await self._access_service.ensure_task_access(task_id=task_id, user_id=user_id)

    async def load_attachment_content(self, *, task_id: int, attachment_id: int):
        """Возвращает проверенный путь и метаданные файла."""
        return await self._attachments_service.get_attachment_content(
            task_id=task_id,
            attachment_id=attachment_id,
        )


DOWNLOAD_ERRORS = (AuthServiceError, AccessServiceError, TaskAttachmentsServiceError)
