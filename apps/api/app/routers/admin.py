from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.web_scout import (
    DEFAULT_FOOTBALL_HOSTS,
    DEFAULT_SCOUT_URLS,
    DEFAULT_SEARCH_QUERIES,
    web_scout_agent,
)
from app.agents.world_cup_monitor import read_monitor_status
from app.core.auth import require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models import FairPlayScore, KnowledgeEntry, Question, ScrapeJob, Tournament, User
from app.services.world_cup_monitor_worker import run_world_cup_monitor_once

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


class ScoutRunRequest(BaseModel):
    topic: str = "world-cup"
    urls: list[str] | None = None
    queries: list[str] | None = None
    auto_approve: bool | None = None


@router.get("/stats")
async def stats(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    users = await db.scalar(select(func.count()).select_from(User))
    tournaments = await db.scalar(select(func.count()).select_from(Tournament))
    questions = await db.scalar(select(func.count()).select_from(Question))
    knowledge = await db.scalar(select(func.count()).select_from(KnowledgeEntry))
    jobs = await db.scalar(select(func.count()).select_from(ScrapeJob))
    return {
        "users": users or 0,
        "tournaments": tournaments or 0,
        "questions": questions or 0,
        "knowledge_entries": knowledge or 0,
        "scrape_jobs": jobs or 0,
    }


@router.get("/questions")
async def list_questions(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Question).order_by(Question.id).limit(200))
    qs = list(result.scalars().all())
    return [
        {
            "id": q.id,
            "type": q.challenge_type.value,
            "prompt": q.prompt,
            "difficulty": q.difficulty,
            "approved": q.approved,
            "source": q.source,
            "source_url": q.source_url,
        }
        for q in qs
    ]


@router.post("/questions/{question_id}/approve")
async def approve_question(question_id: str, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Not found")
    q.approved = True
    await db.flush()
    return {"id": q.id, "approved": True}


@router.get("/fair-play")
async def fair_play_monitor(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FairPlayScore).order_by(FairPlayScore.score.asc()).limit(50))
    rows = list(result.scalars().all())
    return [
        {
            "user_id": r.user_id,
            "score": r.score,
            "needs_review": bool((r.flags or {}).get("needs_review")),
            "counts": (r.flags or {}).get("counts", {}),
            "flags": r.flags,
        }
        for r in rows
    ]


@router.get("/tournaments/{tournament_id}/matches")
async def list_matches(tournament_id: str, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from app.models import Match

    result = await db.execute(select(Match).where(Match.tournament_id == tournament_id).order_by(Match.stage.asc()))
    rows = list(result.scalars().all())
    return [
        {
            "id": m.id,
            "stage": m.stage,
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            "player_a_id": m.player_a_id,
            "player_b_id": m.player_b_id,
            "winner_id": m.winner_id,
        }
        for m in rows
    ]


@router.post("/create-empty-tournament")
async def create_empty_tournament(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Admin helper: force-create an empty public cup via the platform room agent helper."""
    from app.services.tournament_room_agent import create_platform_cup

    t = await create_platform_cup(db)
    return {"id": t.id, "name": t.name}


@router.post("/seed-demo-tournament")
async def seed_demo_tournament(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Back-compat: creates an empty cup (no system fillers)."""
    return await create_empty_tournament(user, db)


@router.get("/scout/sources")
async def scout_sources(user: User = Depends(require_admin)):
    return {
        "search": {
            "engine": "duckduckgo_html",
            "paid_apis": False,
            "default_queries": DEFAULT_SEARCH_QUERIES,
        },
        "llm": {
            "pattern": "voya",
            "ai_provider": settings.cloud_ai_provider,
            "fallback_chain": "ollama → qwen → heuristics",
            "ollama_enabled": settings.ollama_enabled,
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
            "qwen_configured": settings.qwen_configured,
            "qwen_base_url": settings.qwen_base_url,
            "qwen_chat_model": settings.qwen_chat_model,
        },
        "allowed_hosts": sorted(web_scout_agent.allowed_hosts) or DEFAULT_FOOTBALL_HOSTS,
        "fallback_seed_urls": DEFAULT_SCOUT_URLS,
        "blocked": ["wikipedia.org", "wikimedia.org"],
        "auto_approve_default": settings.scout_auto_approve,
    }


@router.post("/scout/run")
async def scout_run(
    body: ScoutRunRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Search Google/news for football pages, scrape them, store knowledge + questions."""
    auto_approve = settings.scout_auto_approve if body.auto_approve is None else body.auto_approve
    job = await web_scout_agent.run(
        db,
        topic=body.topic,
        urls=body.urls,
        queries=body.queries,
        auto_approve=auto_approve,
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "pages_scraped": job.pages_scraped,
        "facts_stored": job.facts_stored,
        "questions_created": job.questions_created,
        "error": job.error,
        "urls": job.urls,
        "search_engine": (job.meta or {}).get("search_engine"),
        "queries": (job.meta or {}).get("queries"),
        "llm_provider": (job.meta or {}).get("llm_provider"),
    }


@router.get("/world-cup-monitor/status")
async def world_cup_monitor_admin_status(user: User = Depends(require_admin)):
    s = get_settings()
    return {
        "enabled": s.world_cup_monitor_enabled,
        "interval_minutes": s.world_cup_monitor_interval_minutes,
        **read_monitor_status(),
    }


@router.post("/world-cup-monitor/run")
async def world_cup_monitor_run(user: User = Depends(require_admin)):
    """Force one World Cup Monitor pass (search → scrape → live snapshot + knowledge)."""
    try:
        return await run_world_cup_monitor_once()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc


@router.get("/scout/jobs")
async def scout_jobs(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(20))
    jobs = list(result.scalars().all())
    return [
        {
            "id": j.id,
            "status": j.status,
            "topic": j.topic,
            "pages_scraped": j.pages_scraped,
            "facts_stored": j.facts_stored,
            "questions_created": j.questions_created,
            "error": j.error,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        }
        for j in jobs
    ]


@router.get("/scout/knowledge")
async def scout_knowledge(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeEntry).order_by(KnowledgeEntry.created_at.desc()).limit(50))
    rows = list(result.scalars().all())
    return [
        {
            "id": k.id,
            "fact": k.fact,
            "category": k.category,
            "source_url": k.source_url,
            "title": k.title,
            "confidence": k.confidence,
        }
        for k in rows
    ]
