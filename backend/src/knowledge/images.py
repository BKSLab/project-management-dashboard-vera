from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_SIDE = 2048
JPEG_QUALITY = 90


def prepare_image_base64(content: bytes) -> str:
    """Готовит изображение к отправке в vision-модель.

    Кадр приводится к RGB и уменьшается до MAX_IMAGE_SIDE по большей стороне:
    модели всё равно масштабируют вход, а трафик и стоимость запроса растут
    линейно по числу пикселей.

    Args:
        content: Бинарное содержимое файла изображения.

    Returns:
        JPEG-изображение в base64 без префикса data URL.

    Raises:
        ValueError: Если файл не является поддерживаемым изображением.
    """
    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            prepared = image.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError(f"Не удалось открыть изображение: {error}") from error

    prepared.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buffer = BytesIO()
    prepared.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return base64.b64encode(buffer.getvalue()).decode("ascii")
