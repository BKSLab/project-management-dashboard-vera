from pathlib import Path

import pytest

from src.exceptions.task_attachments import TaskAttachmentStorageError
from src.storage.task_attachments import TaskAttachmentStorage


@pytest.mark.asyncio
async def test_save_resolve_and_delete_file(tmp_path: Path) -> None:
    storage = TaskAttachmentStorage(root=tmp_path / "uploads")

    storage_key = await storage.save(task_id=12, extension=".pdf", content=b"content")
    stored_path = storage.resolve(storage_key)

    assert storage_key.startswith("tasks/12/")
    assert stored_path.suffix == ".pdf"
    assert stored_path.read_bytes() == b"content"

    await storage.delete(storage_key)

    assert stored_path.exists() is False


def test_resolve_rejects_path_traversal(tmp_path: Path) -> None:
    storage = TaskAttachmentStorage(root=tmp_path / "uploads")

    with pytest.raises(TaskAttachmentStorageError):
        storage.resolve("../outside.pdf")
