"""Явные пределы ресурсов: пул PostgreSQL и пул исходящих HTTP-соединений.

Пределы, оставленные умолчаниям библиотек, определяют поведение системы
под нагрузкой, но нигде не записаны. Тест фиксирует, что каждое значение
задано проектом и попадает в реально созданный ресурс.
"""

import httpx
import pytest

from src.core.settings import DBSettings, Settings, get_settings
from src.db.session import engine
from src.knowledge.runtime import create_http_client

EXPECTED_POOL_FIELDS = (
    "pool_size",
    "pool_max_overflow",
    "pool_timeout",
    "pool_pre_ping",
    "pool_recycle",
)


def test_db_settings_declare_every_pool_parameter() -> None:
    """Все пять параметров пула объявлены в настройках, а не подразумеваются."""
    fields = set(DBSettings.model_fields)

    missing = [name for name in EXPECTED_POOL_FIELDS if name not in fields]
    assert not missing, f"Параметры пула не заданы явно: {missing}"


def test_db_pool_baseline_matches_single_worker_budget() -> None:
    """Baseline рассчитан на один worker: (5 + 10) × 1 = 15 соединений."""
    db = get_settings().db

    assert db.pool_size == 5
    assert db.pool_max_overflow == 10
    assert db.pool_timeout == 5.0
    assert db.pool_pre_ping is True
    assert db.pool_recycle == 1800
    assert (db.pool_size + db.pool_max_overflow) == 15


def test_engine_receives_the_configured_pool_limits() -> None:
    """Значения из настроек действительно дошли до созданного движка."""
    db = get_settings().db
    pool = engine.pool

    assert pool.size() == db.pool_size
    assert pool._max_overflow == db.pool_max_overflow
    assert pool._timeout == db.pool_timeout
    assert pool._pre_ping is db.pool_pre_ping
    assert pool._recycle == db.pool_recycle


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("pool_size", 0),
        ("pool_timeout", 0),
        ("pool_recycle", 0),
    ],
)
def test_pool_settings_reject_meaningless_values(field: str, invalid: int) -> None:
    """Бессмысленный предел не проходит валидацию настроек."""
    with pytest.raises(ValueError):
        DBSettings(
            postgres_host="localhost",
            postgres_port=5432,
            postgres_user="user",
            postgres_password="secret",
            postgres_name="db",
            **{field: invalid},
        )


def test_http_client_settings_are_explicit() -> None:
    """Пределы исходящего HTTP-пула зафиксированы как осознанный baseline."""
    limits = get_settings().http_client

    assert limits.http_max_connections == 100
    assert limits.http_max_keepalive_connections == 20
    assert limits.http_keepalive_expiry == 5.0


@pytest.mark.asyncio
async def test_created_http_client_uses_configured_limits() -> None:
    """Созданный клиент получает пределы из настроек, а не умолчания httpx."""
    settings: Settings = get_settings()

    client = create_http_client(settings)
    try:
        transport = client._transport
        assert isinstance(transport, httpx.AsyncHTTPTransport)
        limits = transport._pool._max_connections
        assert limits == settings.http_client.http_max_connections
        assert (
            transport._pool._max_keepalive_connections
            == settings.http_client.http_max_keepalive_connections
        )
        assert transport._pool._keepalive_expiry == settings.http_client.http_keepalive_expiry
        assert client.timeout.read == float(settings.llm.llm_timeout)
    finally:
        await client.aclose()
