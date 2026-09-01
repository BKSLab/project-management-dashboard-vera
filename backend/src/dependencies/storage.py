from typing import Annotated

from fastapi import Depends

from src.core.settings import get_settings
from src.storage.avatars import AvatarStorage
from src.storage.task_attachments import TaskAttachmentStorage


def get_task_attachment_storage() -> TaskAttachmentStorage:
    """Создаёт адаптер локального каталога файлов задач."""
    return TaskAttachmentStorage(root=get_settings().app.uploads_path)


def get_avatar_storage() -> AvatarStorage:
    """Создаёт адаптер локального каталога фотографий профиля."""
    return AvatarStorage(root=get_settings().auth.avatars_path)


AvatarStorageDep = Annotated[AvatarStorage, Depends(get_avatar_storage)]
TaskAttachmentStorageDep = Annotated[
    TaskAttachmentStorage,
    Depends(get_task_attachment_storage),
]
