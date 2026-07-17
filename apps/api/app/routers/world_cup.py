"""Public World Cup stats — current 2026 snapshot + fun facts for coaches & agents."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.world_cup_monitor import load_effective_snapshot, read_monitor_status
from app.core.config import get_settings
from app.core.database import get_db
from app.models import KnowledgeEntry

router = APIRouter(prefix="/world-cup", tags=["world-cup"])

_DATA = Path(__file__).resolve().parent.parent / "data"
_HISTORY = _DATA / "world_cup_history.json"


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("")
async def world_cup_overview(
    db: AsyncSession = Depends(get_db),
    facts_limit: int = Query(default=24, ge=1, le=60),
):
    """Current WC 2026 snapshot (live overlay preferred), fun facts, and knowledge bank."""
    settings = get_settings()
    snapshot = load_effective_snapshot()
    history_raw = _load_json(_HISTORY)
    tournaments = list(history_raw.get("tournaments") or [])
    monitor = read_monitor_status()

    priority = case(
        (KnowledgeEntry.category == "world-cup-2026", 0),
        (KnowledgeEntry.category.in_(["world-cup", "football-news"]), 1),
        else_=2,
    )
    facts_q = await db.execute(
        select(KnowledgeEntry)
        .where(
            KnowledgeEntry.category.in_(
                [
                    "world-cup-2026",
                    "world-cup",
                    "world-cup-history",
                    "football-news",
                    "FOOTBALL",
                ]
            )
        )
        .order_by(priority, KnowledgeEntry.created_at.desc())
        .limit(facts_limit)
    )
    facts = [
        {
            "id": f.id,
            "title": f.title,
            "category": f.category,
            "fact": f.fact,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in facts_q.scalars().all()
    ]

    return {
        "current": snapshot,
        "fun_facts": list(snapshot.get("fun_facts") or []),
        "history": tournaments,
        "knowledge_facts": facts,
        "monitor": {
            "enabled": settings.world_cup_monitor_enabled,
            "interval_minutes": settings.world_cup_monitor_interval_minutes,
            **monitor,
            "live_overlay": bool(snapshot.get("_monitor")),
        },
        "views": [
            {"id": "current", "label": "Current tournament"},
            {"id": "fun-facts", "label": "Fun facts"},
            {"id": "so-far", "label": "Tournament so far"},
            {"id": "history", "label": "Past World Cups"},
        ],
    }


@router.get("/monitor")
async def world_cup_monitor_status():
    settings = get_settings()
    status = read_monitor_status()
    snapshot = load_effective_snapshot()
    return {
        "enabled": settings.world_cup_monitor_enabled,
        "interval_minutes": settings.world_cup_monitor_interval_minutes,
        **status,
        "live_overlay": bool(snapshot.get("_monitor")),
        "snapshot_updated_at": (snapshot.get("_monitor") or {}).get("updated_at")
        or snapshot.get("updated_at"),
    }


@router.get("/current")
async def world_cup_current():
    snapshot = load_effective_snapshot()
    return snapshot or {"error": "snapshot_unavailable"}


@router.get("/fun-facts")
async def world_cup_fun_facts():
    snapshot = load_effective_snapshot()
    return {
        "edition": snapshot.get("edition"),
        "updated_at": snapshot.get("updated_at"),
        "fun_facts": list(snapshot.get("fun_facts") or []),
        "format_facts": snapshot.get("format_facts") or {},
        "hosts_detail": snapshot.get("hosts_detail") or [],
        "disclaimer": snapshot.get("disclaimer"),
        "monitor": snapshot.get("_monitor"),
    }


@router.get("/so-far")
async def world_cup_so_far():
    snapshot = load_effective_snapshot()
    return {
        "edition": snapshot.get("edition"),
        "updated_at": snapshot.get("updated_at"),
        "stage": snapshot.get("stage"),
        "tournament_so_far": snapshot.get("tournament_so_far") or {},
        "golden_boot": snapshot.get("golden_boot") or [],
        "recent_results": snapshot.get("recent_results") or [],
        "upcoming": snapshot.get("upcoming") or [],
        "fun_facts": list(snapshot.get("fun_facts") or []),
        "disclaimer": snapshot.get("disclaimer"),
        "monitor": snapshot.get("_monitor"),
    }
