"""Agent identity, strategy, career, memory, and decision logs."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_service_key
from app.core.database import get_db
from app.models import (
    Agent,
    AgentCareer,
    AgentDecisionLog,
    AgentMemory,
    StrategyProfile,
    Tournament,
    TournamentStatus,
    User,
)
from app.schemas import (
    AgentCreate,
    AgentOut,
    AgentCareerOut,
    AgentMemoryOut,
    DecisionLogCreate,
    DecisionLogOut,
    StrategyProfileIn,
    StrategyProfileOut,
)
from fastapi import Header
from typing import Optional

router = APIRouter(prefix="/agents", tags=["agents"])


def _strategy_out(s: StrategyProfile | None) -> StrategyProfileOut | None:
    if not s:
        return None
    return StrategyProfileOut(
        confidence_threshold=s.confidence_threshold,
        thinking_time_ms=s.thinking_time_ms,
        risk_level=s.risk_level,
        max_mcp_calls=s.max_mcp_calls,
        premium_insight_budget=s.premium_insight_budget,
        resource_conservation=s.resource_conservation,
        locked_at=s.locked_at,
        locked_tournament_id=s.locked_tournament_id,
        updated_at=s.updated_at,
    )


def _agent_out(agent: Agent, user: User | None = None) -> AgentOut:
    career = agent.career
    memory = agent.memory
    return AgentOut(
        id=agent.id,
        user_id=agent.user_id,
        name=agent.name,
        arena_rating=agent.arena_rating,
        created_at=agent.created_at,
        strategy=_strategy_out(agent.strategy),
        career=AgentCareerOut(
            tournaments_played=career.tournaments_played if career else 0,
            matches_played=career.matches_played if career else 0,
            wins=career.wins if career else 0,
            losses=career.losses if career else 0,
            championships=career.championships if career else 0,
            average_accuracy=career.average_accuracy if career else 0.0,
            average_response_ms=career.average_response_ms if career else 0.0,
            resource_efficiency=career.resource_efficiency if career else 0.0,
            category_stats=career.category_stats if career else {},
        )
        if career
        else AgentCareerOut(),
        memory=AgentMemoryOut(summary=memory.summary if memory else {}, updated_at=memory.updated_at if memory else None)
        if memory
        else AgentMemoryOut(),
        is_system_agent=bool(user.is_system_agent) if user else bool(getattr(agent.user, "is_system_agent", False)),
    )


async def _load_agent(db: AsyncSession, user_id: str) -> Agent | None:
    result = await db.execute(
        select(Agent)
        .options(
            selectinload(Agent.strategy),
            selectinload(Agent.career),
            selectinload(Agent.memory),
            selectinload(Agent.user),
        )
        .where(Agent.user_id == user_id, Agent.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


def _default_strategy(body: StrategyProfileIn | None) -> StrategyProfileIn:
    return body or StrategyProfileIn()


async def create_agent_for_user(
    db: AsyncSession,
    user: User,
    name: str,
    strategy: StrategyProfileIn | None = None,
) -> Agent:
    existing = await _load_agent(db, user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Wallet already owns an agent")

    strat = _default_strategy(strategy)
    agent = Agent(user_id=user.id, name=name.strip())
    db.add(agent)
    await db.flush()
    db.add(
        StrategyProfile(
            agent_id=agent.id,
            confidence_threshold=strat.confidence_threshold,
            thinking_time_ms=strat.thinking_time_ms,
            risk_level=strat.risk_level,
            max_mcp_calls=strat.max_mcp_calls,
            premium_insight_budget=strat.premium_insight_budget,
            resource_conservation=strat.resource_conservation,
        )
    )
    db.add(AgentCareer(agent_id=agent.id))
    db.add(AgentMemory(agent_id=agent.id))
    await db.flush()
    loaded = await _load_agent(db, user.id)
    assert loaded
    return loaded


@router.get("/me", response_model=AgentOut)
async def get_my_agent(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    agent = await _load_agent(db, user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="No agent — create one first")
    return _agent_out(agent, user)


@router.post("/me", response_model=AgentOut)
async def create_my_agent(
    body: AgentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await create_agent_for_user(db, user, body.name, body.strategy)
    return _agent_out(agent, user)


@router.patch("/me/strategy", response_model=StrategyProfileOut)
async def update_my_strategy(
    body: StrategyProfileIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await _load_agent(db, user.id)
    if not agent or not agent.strategy:
        raise HTTPException(status_code=404, detail="No agent")
    s = agent.strategy
    if s.locked_at:
        raise HTTPException(status_code=400, detail="Strategy locked during tournament")
    s.confidence_threshold = body.confidence_threshold
    s.thinking_time_ms = body.thinking_time_ms
    s.risk_level = body.risk_level
    s.max_mcp_calls = body.max_mcp_calls
    s.premium_insight_budget = body.premium_insight_budget
    s.resource_conservation = body.resource_conservation
    s.updated_at = datetime.utcnow()
    await db.flush()
    return _strategy_out(s)


@router.delete("/me")
async def delete_my_agent(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    agent = await _load_agent(db, user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="No agent")
    if agent.strategy and agent.strategy.locked_at:
        raise HTTPException(status_code=400, detail="Cannot delete agent while strategy is locked")
    agent.deleted_at = datetime.utcnow()
    await db.flush()
    return {"ok": True}


@router.get("/by-user/{user_id}", response_model=AgentOut)
async def get_agent_by_user(user_id: str, db: AsyncSession = Depends(get_db)):
    agent = await _load_agent(db, user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_out(agent)


@router.get("/matches/{match_id}/decisions", response_model=list[DecisionLogOut])
async def list_match_decisions(match_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentDecisionLog)
        .where(AgentDecisionLog.match_id == match_id)
        .order_by(AgentDecisionLog.created_at.asc())
    )
    rows = list(result.scalars().all())
    return [
        DecisionLogOut(
            id=r.id,
            agent_id=r.agent_id,
            match_id=r.match_id,
            question_id=r.question_id,
            option_id=r.option_id,
            confidence=r.confidence,
            used_mcp=r.used_mcp,
            used_premium=r.used_premium,
            used_coach_credit=r.used_coach_credit,
            reasoning=r.reasoning,
            latency_ms=r.latency_ms,
            accelerated=r.accelerated,
            is_correct=r.is_correct,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Agent)
        .options(
            selectinload(Agent.strategy),
            selectinload(Agent.career),
            selectinload(Agent.memory),
            selectinload(Agent.user),
        )
        .where(Agent.id == agent_id, Agent.deleted_at.is_(None))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_out(agent)


@router.post("/decisions", response_model=DecisionLogOut)
async def create_decision_log(
    body: DecisionLogCreate,
    db: AsyncSession = Depends(get_db),
    x_service_key: Optional[str] = Header(default=None),
):
    """Runtime / MCP writes decision logs (service key required)."""
    require_service_key(x_service_key)
    row = AgentDecisionLog(
        agent_id=body.agent_id,
        match_id=body.match_id,
        round_id=body.round_id,
        question_id=body.question_id,
        option_id=body.option_id,
        confidence=body.confidence,
        used_mcp=body.used_mcp,
        used_premium=body.used_premium,
        used_coach_credit=body.used_coach_credit,
        reasoning=body.reasoning[:2000],
        latency_ms=body.latency_ms,
        accelerated=body.accelerated,
        is_correct=body.is_correct,
    )
    db.add(row)
    await db.flush()
    return DecisionLogOut(
        id=row.id,
        agent_id=row.agent_id,
        match_id=row.match_id,
        question_id=row.question_id,
        option_id=row.option_id,
        confidence=row.confidence,
        used_mcp=row.used_mcp,
        used_premium=row.used_premium,
        used_coach_credit=row.used_coach_credit,
        reasoning=row.reasoning,
        latency_ms=row.latency_ms,
        accelerated=row.accelerated,
        is_correct=row.is_correct,
        created_at=row.created_at,
    )


async def lock_strategies_for_tournament(db: AsyncSession, tournament: Tournament) -> None:
    """Lock all entrant strategies when competition begins."""
    from app.models import TournamentEntry

    entries = await db.execute(
        select(TournamentEntry).where(TournamentEntry.tournament_id == tournament.id)
    )
    user_ids = [e.user_id for e in entries.scalars().all()]
    if not user_ids:
        return
    agents = await db.execute(
        select(Agent)
        .options(selectinload(Agent.strategy))
        .where(Agent.user_id.in_(user_ids), Agent.deleted_at.is_(None))
    )
    now = datetime.utcnow()
    for agent in agents.scalars().all():
        if agent.strategy and not agent.strategy.locked_at:
            agent.strategy.locked_at = now
            agent.strategy.locked_tournament_id = tournament.id


async def unlock_strategies_for_tournament(db: AsyncSession, tournament_id: str) -> None:
    result = await db.execute(
        select(StrategyProfile).where(StrategyProfile.locked_tournament_id == tournament_id)
    )
    for s in result.scalars().all():
        s.locked_at = None
        s.locked_tournament_id = None
        s.updated_at = datetime.utcnow()
