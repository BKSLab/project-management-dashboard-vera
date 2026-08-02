from typing import Annotated

from fastapi import Depends

from src.core.settings import get_settings
from src.storage.task_attachments import TaskAttachmentStorage


def get_task_attachment_storage() -> TaskAttachmentStorage:
    """Создаёт адаптер локального каталога файлов задач."""
    return TaskAttachmentStorage(root=get_settings().app.uploads_path)


TaskAttachmentStorageDep = Annotated[
    TaskAttachmentStorage,
    Depends(get_task_attachment_storage),
]
