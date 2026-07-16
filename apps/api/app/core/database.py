from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # Always commit: after flush(), session.new/dirty are empty but the
            # transaction still holds uncommitted writes (e.g. deposit credits).
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _ensure_schema_patches(conn) -> None:
    """Idempotent patches for existing MVP DBs (create_all won't alter enums/columns)."""
    await conn.execute(
        text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS media_url VARCHAR(1024)")
    )
    await conn.execute(
        text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_system_agent BOOLEAN DEFAULT FALSE")
    )
    await conn.execute(
        text("ALTER TABLE agent_decision_logs ADD COLUMN IF NOT EXISTS is_correct BOOLEAN")
    )
    await conn.execute(
        text("ALTER TABLE balances ADD COLUMN IF NOT EXISTS locked_usdc_micro BIGINT DEFAULT 0")
    )
    await conn.execute(
        text(
            "ALTER TABLE tournament_entries ADD COLUMN IF NOT EXISTS entry_fee_locked_usdc_micro BIGINT DEFAULT 0"
        )
    )
    await conn.execute(
        text(
            "ALTER TABLE tournament_entries ADD COLUMN IF NOT EXISTS fee_status VARCHAR(16) DEFAULT 'NONE'"
        )
    )
    for value in (
        "STADIUM",
        "PLAYER_ID",
        "FLAG",
        "FORMATION",
    ):
        await conn.execute(
            text(
                f"""
                DO $$ BEGIN
                    ALTER TYPE challengetype ADD VALUE IF NOT EXISTS '{value}';
                EXCEPTION
                    WHEN duplicate_object THEN null;
                    WHEN undefined_object THEN null;
                END $$;
                """
            )
        )
    for value in (
        "CCTP_DEPOSIT",
        "ONCHAIN_DEPOSIT",
        "DEMO_FAUCET",
        "ENTRY_FEE",
        "ENTRY_LOCK",
        "ENTRY_UNLOCK",
        "ENTRY_CONSUME",
        "COACH_PACK",
        "REWARD",
        "X402_PREMIUM",
        "REFUND",
        "WITHDRAW",
    ):
        await conn.execute(
            text(
                f"""
                DO $$ BEGIN
                    ALTER TYPE txtype ADD VALUE IF NOT EXISTS '{value}';
                EXCEPTION
                    WHEN duplicate_object THEN null;
                    WHEN undefined_object THEN null;
                END $$;
                """
            )
        )


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await _ensure_schema_patches(conn)
        except Exception:
            # SQLite / non-Postgres: ignore enum patches
            pass
