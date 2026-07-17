"""Background World Cup Monitor — frequent internet polling to refresh live WC data."""

from __future__ import annotations

import asyncio
import logging

from app.agents.world_cup_monitor import world_cup_monitor_agent
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


async def run_world_cup_monitor_once(*, auto_approve: bool | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        result = await world_cup_monitor_agent.run_once(db, auto_approve=auto_approve)
        await db.commit()
        logger.info(
            "World Cup monitor: pages=%s facts=%s snapshot=%s",
            result.get("pages_scraped"),
            result.get("facts_stored"),
            result.get("snapshot_updated"),
        )
        return result


async def _scheduler_loop() -> None:
    settings = get_settings()
    # First pass soon after boot so Current stats are not stuck on a stale snapshot
    await asyncio.sleep(20)
    while True:
        settings = get_settings()
        if settings.world_cup_monitor_enabled:
            try:
                await asyncio.wait_for(run_world_cup_monitor_once(), timeout=180)
            except asyncio.TimeoutError:
                logger.warning("World Cup monitor timed out after 180s")
            except Exception:  # noqa: BLE001
                logger.exception("World Cup monitor scheduler iteration failed")
        interval = max(60, int(settings.world_cup_monitor_interval_minutes) * 60)
        await asyncio.sleep(interval)


def start_world_cup_monitor() -> asyncio.Task | None:
    settings = get_settings()
    if not settings.world_cup_monitor_enabled:
        return None
    global _task
    if _task and not _task.done():
        return _task
    _task = asyncio.create_task(_scheduler_loop(), name="arena64-world-cup-monitor")
    logger.info(
        "World Cup monitor started (every %s min)",
        settings.world_cup_monitor_interval_minutes,
    )
    return _task


async def stop_world_cup_monitor() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
