from app.core.config import normalize_async_database_url, normalize_sync_database_url


def test_normalize_async_from_postgres_scheme():
    assert normalize_async_database_url("postgres://u:p@host:5432/db") == (
        "postgresql+asyncpg://u:p@host:5432/db"
    )


def test_normalize_async_from_postgresql():
    assert normalize_async_database_url("postgresql://u:p@host/db") == (
        "postgresql+asyncpg://u:p@host/db"
    )


def test_normalize_async_idempotent():
    url = "postgresql+asyncpg://u:p@host/db"
    assert normalize_async_database_url(url) == url


def test_normalize_sync_strips_asyncpg():
    assert normalize_sync_database_url("postgresql+asyncpg://u:p@host/db") == (
        "postgresql://u:p@host/db"
    )


def test_normalize_sync_from_postgres_scheme():
    assert normalize_sync_database_url("postgres://u:p@host/db") == "postgresql://u:p@host/db"
