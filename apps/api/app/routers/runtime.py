"""Endpoints for the AI runtime worker (service-key auth)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import create_access_token, require_service_key
from app.core.database import get_db
from app.models import Agent, Match, MatchStatus, PremiumTransaction, Round, User
from app.core.config import get_settings
from app.services.wallet_service import wallet_service

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/live-work")
async def live_work(
    db: AsyncSession = Depends(get_db),
    x_service_key: Optional[str] = Header(default=None),
):
    """List LIVE matches with player agent payloads for the AI runtime."""
    require_service_key(x_service_key)
    result = await db.execute(select(Match).where(Match.status == MatchStatus.LIVE))
    matches = list(result.scalars().all())
    out = []
    for m in matches:
        rnd = await db.execute(
            select(Round).where(Round.match_id == m.id).order_by(Round.round_number.desc())
        )
        round_row = rnd.scalars().first()
        players = []
        for uid in (m.player_a_id, m.player_b_id):
            if not uid:
                continue
            user_res = await db.execute(
                select(User).options(selectinload(User.balance)).where(User.id == uid)
            )
            user = user_res.scalar_one_or_none()
            agent_res = await db.execute(
                select(Agent)
                .options(
                    selectinload(Agent.strategy),
                    selectinload(Agent.memory),
                    selectinload(Agent.career),
                )
                .where(Agent.user_id == uid, Agent.deleted_at.is_(None))
            )
            agent = agent_res.scalar_one_or_none()
            if not agent or not user:
                continue
            token = create_access_token(user.id, user.wallet_address)
            strat = agent.strategy
            mem = agent.memory
            try:
                bal = wallet_service.get_balance(user)
            except Exception:
                bal = {"available_usdc": 0.0}
            premium_budget = float(strat.premium_insight_budget) if strat else 0.0
            spent = 0.0
            if m.tournament_id:
                spent_rows = list(
                    (
                        await db.execute(
                            select(PremiumTransaction).where(
                                PremiumTransaction.agent_id == agent.id,
                                PremiumTransaction.tournament_id == m.tournament_id,
                            )
                        )
                    ).scalars().all()
                )
                spent = sum(int(r.cost_usdc_micro or 0) for r in spent_rows) / 1_000_000
            remaining_budget = max(0.0, premium_budget - spent) if premium_budget else premium_budget
            cost = float(get_settings().premium_insight_cost_usdc or 0.05)
            max_premium = int(remaining_budget / cost) if cost > 0 and remaining_budget > 0 else 0
            if premium_budget <= 0:
                max_premium = 0
            players.append(
                {
                    "user_id": uid,
                    "token": token,
                    "is_system_agent": bool(user.is_system_agent),
                    "agent": {
                        "id": agent.id,
                        "name": agent.name,
                        "arena_rating": agent.arena_rating,
                        "is_system_agent": bool(user.is_system_agent),
                        "budget": {
                            "wallet_balance": float(bal["available_usdc"]),
                            "premium_budget": remaining_budget,
                            "max_premium_requests": max_premium,
                        },
                        "strategy": {
                            "confidence_threshold": strat.confidence_threshold if strat else 0.55,
                            "thinking_time_ms": strat.thinking_time_ms if strat else 800,
                            "risk_level": strat.risk_level if strat else "medium",
                            "max_mcp_calls": strat.max_mcp_calls if strat else 0,
                            "premium_insight_budget": strat.premium_insight_budget if strat else 0,
                            "resource_conservation": strat.resource_conservation if strat else 0.5,
                        }
                        if strat
                        else {},
                        "memory": {"summary": mem.summary if mem else {}},
                        "career": {
                            "tournaments_played": agent.career.tournaments_played if agent.career else 0,
                            "wins": agent.career.wins if agent.career else 0,
                            "losses": agent.career.losses if agent.career else 0,
                            "championships": agent.career.championships if agent.career else 0,
                            "average_accuracy": agent.career.average_accuracy if agent.career else 0.0,
                            "category_stats": agent.career.category_stats if agent.career else {},
                        }
                        if agent.career
                        else {},
                    },
                }
            )
        out.append(
            {
                "id": m.id,
                "tournament_id": m.tournament_id,
                "stage": m.stage,
                "round_id": round_row.id if round_row else None,
                "score_a": m.score_a,
                "score_b": m.score_b,
                "players": players,
            }
        )
    return {"matches": out}


@router.post("/ensure-started/{match_id}")
async def ensure_started(
    match_id: str,
    db: AsyncSession = Depends(get_db),
    x_service_key: Optional[str] = Header(default=None),
):
    require_service_key(x_service_key)
    from app.agents.tournament_director import tournament_director
    from app.models import Tournament

    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.status == MatchStatus.LIVE:
        rnd = await db.execute(
            select(Round).where(Round.match_id == match.id).order_by(Round.round_number.desc())
        )
        row = rnd.scalars().first()
        return {"round_id": row.id if row else None, "status": "LIVE"}
    if match.status != MatchStatus.PENDING:
        raise HTTPException(status_code=400, detail="Match not startable")
    t = await db.get(Tournament, match.tournament_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournament missing")
    rnd = await tournament_director.start_match(
        db, match, t.questions_per_round, t.challenge_types or ["FOOTBALL"], mixed=True
    )
    return {"round_id": rnd.id, "status": "LIVE"}


@router.get("/research")
async def research_knowledge(
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 8,
    db: AsyncSession = Depends(get_db),
    x_service_key: Optional[str] = Header(default=None),
):
    """Shared knowledge bank search for competitor MCP / runtime help."""
    require_service_key(x_service_key)
    from app.models import ChallengeType, KnowledgeEntry, Question

    limit = max(1, min(limit, 20))
    facts: list[dict] = []
    cat = (category or "").strip().upper() or None

    if q:
        like = f"%{q}%"
        kq = select(KnowledgeEntry).where(KnowledgeEntry.fact.ilike(like))
        if cat:
            kq = select(KnowledgeEntry).where(
                or_(
                    KnowledgeEntry.fact.ilike(like),
                    KnowledgeEntry.category.ilike(f"%{cat.lower()}%"),
                    KnowledgeEntry.title.ilike(like),
                )
            )
        kres = await db.execute(kq.limit(limit))
        for row in kres.scalars().all():
            facts.append(
                {
                    "type": "knowledge",
                    "content": row.fact[:500],
                    "topic": row.category,
                    "title": row.title,
                }
            )
        qq = select(Question).where(Question.prompt.ilike(like), Question.approved.is_(True))
        if cat:
            try:
                ctype = ChallengeType(cat)
                qq = qq.where(Question.challenge_type == ctype)
            except ValueError:
                pass
        qres = await db.execute(qq.limit(limit))
        for row in qres.scalars().all():
            facts.append(
                {
                    "type": "question_bank",
                    "prompt": row.prompt[:300],
                    "challenge_type": row.challenge_type.value
                    if hasattr(row.challenge_type, "value")
                    else str(row.challenge_type),
                }
            )
    else:
        kq = select(KnowledgeEntry)
        if cat:
            kq = kq.where(KnowledgeEntry.category.ilike(f"%{cat.lower()}%"))
        kres = await db.execute(kq.limit(limit))
        for row in kres.scalars().all():
            facts.append({"type": "knowledge", "content": row.fact[:500], "title": row.title})
    return {"query": q, "category": cat, "results": facts[:limit]}
