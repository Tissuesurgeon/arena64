"""Free trial — solo practice: agent answers autonomously; coach spectates."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tournament_director import tournament_director
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import Agent, Match, MatchStatus, Tournament, User
from app.services.practice_agent import schedule_practice_match
from app.services.seed import TRIAL_ARENA_NAME, ensure_trial_arena

router = APIRouter(prefix="/trial", tags=["trial"])

TRIAL_QUESTIONS = 5
TRIAL_TYPES = ["FOOTBALL", "MEMORY", "STADIUM", "PLAYER_ID", "FLAG", "FORMATION"]


@router.post("/start")
async def start_trial(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a free solo trial match for the coach's agent (runtime answers)."""
    agent_res = await db.execute(
        select(Agent).where(Agent.user_id == user.id, Agent.deleted_at.is_(None))
    )
    if not agent_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Create an agent before practice")

    arena = await ensure_trial_arena(db)
    if not arena:
        raise HTTPException(status_code=500, detail="Trial arena unavailable")

    live = await db.execute(
        select(Match).where(
            Match.tournament_id == arena.id,
            Match.player_a_id == user.id,
            Match.stage == "TRIAL",
            Match.status == MatchStatus.LIVE,
        )
    )
    for old in live.scalars().all():
        old.status = MatchStatus.COMPLETED
        old.winner_id = user.id

    match = Match(
        tournament_id=arena.id,
        stage="TRIAL",
        player_a_id=user.id,
        player_b_id=None,
        bracket_slot=None,
        status=MatchStatus.PENDING,
    )
    db.add(match)
    await db.flush()

    try:
        rnd = await tournament_director.start_match(db, match, TRIAL_QUESTIONS, TRIAL_TYPES)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # In-API practice answerer so Trial works without a separate ai-runtime process.
    # External ai-runtime can still answer tournament matches; this covers solo practice.
    schedule_practice_match(match.id, user.id, rnd.id)

    return {
        "trial": True,
        "match_id": match.id,
        "round_id": rnd.id,
        "tournament_id": arena.id,
        "questions": len(rnd.question_ids),
        "challenge_type": rnd.challenge_type.value,
        "message": "Practice watch — your agent answers autonomously. No USDC, no rewards.",
    }


@router.get("/info")
async def trial_info(db: AsyncSession = Depends(get_db)):
    arena = await db.execute(select(Tournament).where(Tournament.name == TRIAL_ARENA_NAME).limit(1))
    t = arena.scalar_one_or_none()
    return {
        "available": True,
        "name": TRIAL_ARENA_NAME,
        "questions": TRIAL_QUESTIONS,
        "entry_fee_usdc": 0,
        "rewards": False,
        "requires_wallet": True,
        "description": (
            "Solo practice: deploy your agent and spectate autonomous decisions. "
            "Same knowledge bank as tournaments — no USDC, no rewards."
        ),
        "tournament_id": t.id if t else None,
    }
