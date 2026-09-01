import logging

import httpx

from src.exceptions.knowledge import KnowledgeProviderError

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Клиент OpenAI-совместимого embeddings API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        url: str,
        api_key: str,
        model: str,
        timeout: int,
    ) -> None:
        self.http_client = http_client
        self.url = url
        self.model = model
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Возвращает векторы в том же порядке, что и входные тексты."""
        if not texts:
            return []
        try:
            response = await self.http_client.post(
                self.url,
                headers=self.headers,
                json={"model": self.model, "input": texts},
                timeout=self.timeout,
            )
            response.raise_for_status()
            items = sorted(response.json()["data"], key=lambda item: item.get("index", 0))
            vectors = [item["embedding"] for item in items]
            if len(vectors) != len(texts) or any(not vector for vector in vectors):
                raise ValueError("Embedding API вернул неполный набор векторов.")
            logger.info(
                "✅ Получено %s embeddings моделью %s, dim=%s.",
                len(vectors),
                self.model,
                len(vectors[0]),
            )
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            logger.error("❌ Ошибка embedding API: %s", error, exc_info=True)
            raise KnowledgeProviderError(str(error)) from error

    async def get_embedding(self, text: str) -> list[float]:
        """Возвращает embedding одного текста."""
        return (await self.get_embeddings([text]))[0]
