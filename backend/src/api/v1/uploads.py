"""Чтение multipart-файлов на границе транспорта.

Разбор `UploadFile` — задача транспорта: это форма запроса, а не бизнес-
правило. Здесь файл читается с ограничением и гарантированно закрывается,
а превышение лимита превращается в ответ 4xx.

Доменные правила — сколько файлов допустимо, какие расширения
индексируются, что делать с пустым файлом — остаются в сервисе: они
одинаковы для любого способа доставки файла.
"""

import logging
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)

TOO_LARGE_MESSAGE = "Размер файла превышает допустимые {limit_mb} МБ."


@dataclass(frozen=True, slots=True)
class UploadedFile:
    """Прочитанный multipart-файл.

    Attributes:
        name: Исходное имя файла из запроса.
        content: Прочитанное содержимое.
    """

    name: str
    content: bytes


async def read_upload(upload: UploadFile, *, max_size: int) -> UploadedFile:
    """Читает файл, не загружая в память больше разрешённого.

    Читается ``max_size + 1`` байт: одного лишнего байта достаточно,
    чтобы отличить файл на пределе от превышающего его, и при этом не
    поднимать в память файл произвольного размера.

    Args:
        upload: Файл из multipart-запроса.
        max_size: Предельный размер в байтах.

    Returns:
        Имя и содержимое файла.

    Raises:
        HTTPException: Если файл превышает предельный размер.
    """
    content = await upload.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=TOO_LARGE_MESSAGE.format(limit_mb=max_size // 1024 // 1024),
        )
    return UploadedFile(name=upload.filename or "", content=content)


async def read_uploads(uploads: list[UploadFile], *, max_size: int) -> list[UploadedFile]:
    """Читает набор файлов запроса с тем же ограничением."""
    return [await read_upload(upload, max_size=max_size) for upload in uploads]


async def close_uploads(uploads: list[UploadFile]) -> None:
    """Закрывает файлы запроса независимо от исхода обработки."""
    for upload in uploads:
        await upload.close()
