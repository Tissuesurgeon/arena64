"""Background Web Scout worker — interval runs with query rotation and fact dedup."""

from __future__ import annotations

import asyncio
import logging

from app.agents.web_scout import DEFAULT_SEARCH_QUERIES, web_scout_agent
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.bootstrap_knowledge import bootstrap_all_world_cup_knowledge

logger = logging.getLogger(__name__)

_query_index = 0
_task: asyncio.Task | None = None


def _next_queries(batch: int = 2) -> list[str]:
    global _query_index
    pool = DEFAULT_SEARCH_QUERIES
    if not pool:
        return ["FIFA World Cup"]
    out: list[str] = []
    for _ in range(batch):
        out.append(pool[_query_index % len(pool)])
        _query_index += 1
    return out


async def run_scout_once(*, auto_approve: bool | None = None) -> None:
    """Run one scout pass. Network/LLM work happens inside the agent; keep DB sessions short."""
    settings = get_settings()
    approve = settings.scout_auto_approve if auto_approve is None else auto_approve
    queries = _next_queries(2)
    try:
        async with AsyncSessionLocal() as db:
            job = await web_scout_agent.run(
                db,
                topic="world-cup",
                queries=queries,
                auto_approve=approve,
            )
            await db.commit()
            logger.info(
                "Scout job %s status=%s facts=%s questions=%s queries=%s",
                job.id,
                job.status,
                job.facts_stored,
                job.questions_created,
                queries,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Scout run failed")


async def bootstrap_then_scout() -> None:
    settings = get_settings()
    if not settings.scout_bootstrap_on_start:
        return
    try:
        async with AsyncSessionLocal() as db:
            result = await bootstrap_all_world_cup_knowledge(db)
            await db.commit()
            logger.info("Knowledge bootstrap: %s", result)
    except Exception:  # noqa: BLE001
        logger.exception("Knowledge bootstrap failed")


async def _scheduler_loop() -> None:
    settings = get_settings()
    await asyncio.sleep(15)
    while True:
        settings = get_settings()
        if settings.scout_scheduler_enabled:
            # Never block the API event loop on scout — run in a worker thread/task with timeout
            try:
                await asyncio.wait_for(run_scout_once(), timeout=120)
            except asyncio.TimeoutError:
                logger.warning("Scout run timed out after 120s")
        interval = max(60, int(settings.scout_interval_minutes) * 60)
        await asyncio.sleep(interval)


def start_scout_scheduler() -> asyncio.Task | None:
    settings = get_settings()
    if not settings.scout_scheduler_enabled and not settings.scout_bootstrap_on_start:
        return None
    global _task
    if _task and not _task.done():
        return _task

    async def _runner() -> None:
        await bootstrap_then_scout()
        if settings.scout_scheduler_enabled:
            await _scheduler_loop()

    _task = asyncio.create_task(_runner(), name="arena64-scout-worker")
    return _task


async def stop_scout_scheduler() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
