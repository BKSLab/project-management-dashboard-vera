from __future__ import annotations

import base64
from pathlib import Path

IMAGE_MEDIA_TYPES = {
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def build_image_data_url(filename: str, content: bytes) -> str:
    """Кодирует исходное изображение для прямой отправки в vision-модель.

    Args:
        filename: Имя файла, определяющее MIME-тип изображения.
        content: Бинарное содержимое файла изображения.

    Returns:
        Data URL с исходными байтами без локального декодирования или обработки.

    Raises:
        ValueError: Если расширение не поддерживается или файл пуст.
    """
    suffix = Path(filename).suffix.lower()
    media_type = IMAGE_MEDIA_TYPES.get(suffix)
    if media_type is None:
        raise ValueError(f"Неподдерживаемое расширение изображения: {suffix or 'отсутствует'}.")
    if not content:
        raise ValueError("Изображение не содержит данных.")
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{media_type};base64,{encoded}"
