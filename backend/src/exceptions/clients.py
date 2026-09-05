"""Исключения слоя внешних клиентов.

Клиент не знает, каким HTTP-ответом обернётся его сбой: это решает сервис,
который его вызвал. Поэтому ошибки клиентов не наследуются от `ServiceError`
и собственного HTTP-контракта не несут — статус по умолчанию наследуется от
`ApplicationError` и используется только как страховка, если ошибка всё же
дойдёт до границы транспорта.
"""

from src.exceptions.base import ApplicationError


class ClientError(ApplicationError):
    """Базовое исключение обращения к внешней системе."""

    detail = "Ошибка обращения к внешнему сервису."


class LlmClientError(ClientError):
    """Chat completions API недоступен или вернул неразобранный ответ."""

    detail = "Ошибка обращения к LLM API."


class VisionClientError(ClientError):
    """Vision API недоступен или вернул неразобранный ответ."""

    detail = "Ошибка обращения к vision API."


class EmbeddingClientError(ClientError):
    """API эмбеддингов недоступен или вернул неполный набор векторов."""

    detail = "Ошибка обращения к API эмбеддингов."


class VectorStoreClientError(ClientError):
    """Векторная база недоступна или отклонила операцию."""

    detail = "Ошибка обращения к векторной базе."
