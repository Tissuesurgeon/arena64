"""Platform game agent — always keeps one open 6-agent tournament room."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Tournament, TournamentEntry, TournamentStatus, Visibility
from app.services.ledger import usdc_to_micro

logger = logging.getLogger(__name__)

ROOM_TICK_SECONDS = 30
PLATFORM_CUP_NAME = "Arena Cup"
PLATFORM_CHALLENGE_TYPES = ["FOOTBALL", "MEMORY", "STADIUM", "PLAYER_ID", "FLAG", "FORMATION"]
OPEN_STATUSES = (TournamentStatus.UPCOMING, TournamentStatus.LOBBY)

_task: asyncio.Task | None = None


async def create_platform_cup(db: AsyncSession) -> Tournament:
    """Force-create a new empty public 6-agent cup (ops / room agent)."""
    t = Tournament(
        name=PLATFORM_CUP_NAME,
        description="Platform open room — 6 agents. Join with your agent until full.",
        max_players=6,
        entry_fee_usdc_micro=usdc_to_micro(1),
        reward_pool_usdc_micro=0,
        challenge_types=list(PLATFORM_CHALLENGE_TYPES),
        difficulty="medium",
        questions_per_round=5,
        visibility=Visibility.PUBLIC,
        status=TournamentStatus.UPCOMING,
        coach_enabled=False,
    )
    db.add(t)
    await db.flush()
    logger.info("Platform room agent created cup %s", t.id)
    return t


async def ensure_open_cup(db: AsyncSession) -> Tournament:
    """Return the oldest open joinable cup, or create one if none have seats."""
    stmt = (
        select(Tournament, func.count(TournamentEntry.id).label("entrant_count"))
        .outerjoin(TournamentEntry, TournamentEntry.tournament_id == Tournament.id)
        .where(
            Tournament.visibility == Visibility.PUBLIC,
            Tournament.max_players == 6,
            Tournament.status.in_(OPEN_STATUSES),
        )
        .group_by(Tournament.id)
        .having(func.count(TournamentEntry.id) < 6)
        .order_by(Tournament.created_at.asc())
    )
    row = (await db.execute(stmt)).first()
    if row:
        return row[0]
    return await create_platform_cup(db)


async def ensure_open_cup_standalone() -> Tournament | None:
    """Session + commit wrapper for lifespan / background ticks."""
    try:
        async with AsyncSessionLocal() as db:
            cup = await ensure_open_cup(db)
            await db.commit()
            return cup
    except Exception:  # noqa: BLE001
        logger.exception("Platform room agent ensure_open_cup failed")
        return None


async def _scheduler_loop() -> None:
    await asyncio.sleep(5)
    while True:
        await ensure_open_cup_standalone()
        await asyncio.sleep(ROOM_TICK_SECONDS)


def start_room_agent() -> asyncio.Task | None:
    global _task
    if _task and not _task.done():
        return _task

    async def _runner() -> None:
        await ensure_open_cup_standalone()
        await _scheduler_loop()

    _task = asyncio.create_task(_runner(), name="arena64-tournament-room-agent")
    return _task


async def stop_room_agent() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
