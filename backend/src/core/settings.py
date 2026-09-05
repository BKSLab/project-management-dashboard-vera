from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SettingsBase(BaseSettings):
    """Базовые правила чтения настроек из окружения и локального .env."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )


class AppSettings(SettingsBase):
    """Настройки HTTP-приложения и его инфраструктуры."""

    app_name: str = "Project Task Tracker"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    mcp_path: str = "/mcp"
    # Хосты, с которых принимается MCP: защита от DNS-rebinding в SDK
    # иначе разрешает только localhost и ломает доступ по адресу сервера.
    mcp_allowed_hosts: list[str] = [
        "localhost",
        "localhost:*",
        "127.0.0.1",
        "127.0.0.1:*",
    ]
    mcp_allowed_origins: list[str] = []
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    logging_config_path: Path = BASE_DIR / "logging.ini"
    uploads_path: Path = BASE_DIR / "uploads"


class AuthSettings(SettingsBase):
    """Настройки аутентификации.

    Секрет подписи не имеет значения по умолчанию намеренно: приложение
    должно падать на старте, а не уезжать в прод с общеизвестным ключом.
    """

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_ttl_hours: int = 24 * 14
    registration_invite_code: SecretStr
    api_token_default_ttl_days: int = 90
    api_token_max_active: int = 10
    session_cookie_name: str = "tracker_session"
    session_cookie_secure: bool = False
    avatars_path: Path = BASE_DIR / "uploads" / "avatars"


class HttpClientSettings(SettingsBase):
    """Пределы общего исходящего HTTP-клиента внешних API.

    Значения фиксируют текущее поведение httpx как осознанный baseline:
    нагрузочных данных пока нет, поэтому важно не конкретное число, а то,
    что предел задан явно и меняется в одном месте. Пересматривать по
    измеренной конкурентности внешних вызовов.
    """

    http_max_connections: int = Field(default=100, ge=1)
    http_max_keepalive_connections: int = Field(default=20, ge=0)
    http_keepalive_expiry: float = Field(default=5.0, gt=0)


class LlmSettings(SettingsBase):
    """Настройки OpenAI-совместимого API для Project Agent.

    Worst-case одного вызова считается как ``llm_timeout × llm_retries``
    плюс экспоненциальный backoff между попытками. При значениях по
    умолчанию это ``300 × 3 = 900`` секунд ожидания upstream. Расхождение
    этого бюджета с timeout-ом nginx на ``/api/`` зафиксировано в
    ``docs/AI_TIMEOUT_BUDGET_DECISION.md``.
    """

    llm_api_key: SecretStr
    llm_api_url: str
    llm_model: str = "google/gemini-3.7-flash"
    agent_model: str = "google/gemini-3.7-flash"
    llm_timeout: int = 300
    llm_retries: int = 3
    vision_model: str = "google/gemini-3.7-flash"
    vision_max_tokens: int = 4000
    task_rephrase_file_max_chars: int = Field(default=5000, ge=500, le=50_000)

    @property
    def headers(self) -> dict[str, str]:
        """Возвращает заголовки авторизации для LLM API."""
        return {
            "Authorization": f"Bearer {self.llm_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }


class EmbeddingSettings(SettingsBase):
    """Настройки OpenAI-совместимого API эмбеддингов.

    Клиент эмбеддингов не повторяет запрос, поэтому его worst-case равен
    одному ``embedding_timeout``: 120 секунд при значении по умолчанию.
    """

    embedding_api_key: SecretStr
    embedding_api_url: str
    embedding_model: str = "openai/text-embedding-3-large"
    embedding_dim: int = 3072
    embedding_timeout: int = 120


class KnowledgeSettings(SettingsBase):
    """Настройки семантического индекса и фонового индексатора."""

    knowledge_enabled: bool = True
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr = SecretStr("")
    # Собственный SDK Qdrant не повторяет запрос, поэтому worst-case вызова
    # равен одному этому таймауту.
    qdrant_timeout: float = Field(default=30.0, gt=0)
    qdrant_collection_prefix: str = "project"
    qdrant_score_threshold: float = 0.35
    knowledge_index_poll_seconds: float = 2.0
    knowledge_index_max_attempts: int = 5
    knowledge_job_retention_days: int = 30
    knowledge_embedding_batch_size: int = 32
    knowledge_chunk_target_chars: int = 2200
    knowledge_chunk_overlap_chars: int = 300
    knowledge_agent_semantic_limit: int = 10
    knowledge_vision_enabled: bool = True
    knowledge_extract_max_chars: int = 350_000


class DBSettings(SettingsBase):
    """Настройки подключения к PostgreSQL.

    Параметры пула заданы явно, а не оставлены умолчаниям SQLAlchemy:
    поведение при исчерпании пула — решение проекта, а не библиотеки.

    Общий предел соединений считается как
    ``(pool_size + pool_max_overflow) × число процессов`` и должен помещаться
    в ``max_connections`` PostgreSQL с операционным запасом. Текущий baseline
    рассчитан на один worker: ``(5 + 10) × 1 = 15``. При увеличении числа
    процессов формулу обязательно пересчитать.
    """

    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: SecretStr
    postgres_name: str

    # Постоянные соединения пула: покрывают обычную конкурентность запросов.
    pool_size: int = Field(default=5, ge=1)
    # Временные соединения сверх пула на всплеск нагрузки.
    pool_max_overflow: int = Field(default=10, ge=0)
    # Сколько ждать свободного соединения. Короткое ожидание превращает
    # исчерпание пула в быструю явную ошибку вместо зависшего запроса.
    pool_timeout: float = Field(default=5.0, gt=0)
    # Проверка соединения перед выдачей: защищает от разрывов со стороны
    # PostgreSQL и промежуточных прокси.
    pool_pre_ping: bool = True
    # Возраст соединения, после которого оно пересоздаётся (30 минут).
    pool_recycle: int = Field(default=1800, gt=0)

    @property
    def url_connect(self) -> str:
        """Возвращает DSN асинхронного драйвера PostgreSQL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_name}"
        )


class Settings(BaseSettings):
    """Агрегатор настроек приложения по доменам."""

    db: DBSettings = Field(default_factory=DBSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    http_client: HttpClientSettings = Field(default_factory=HttpClientSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    knowledge: KnowledgeSettings = Field(default_factory=KnowledgeSettings)


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный кэшированный экземпляр настроек."""
    return Settings()
