from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.reward_manager import reward_manager
from app.agents.tournament_director import ALLOWED_SIZES, tournament_director
from app.core.auth import get_current_user, get_optional_user, require_admin
from app.core.database import get_db
from app.models import (
    LeaderboardEntry,
    Reward,
    Tournament,
    TournamentEntry,
    TournamentGroup,
    TournamentStatus,
    User,
    Visibility,
)
from app.realtime.ws import emit_tournament
from app.schemas import JoinRequest, TournamentCreate, TournamentOut
from app.services.ledger import micro_to_usdc, usdc_to_micro
from app.services.tournament_finance import TournamentFinanceError, tournament_finance
from app.services.tournament_room_agent import ensure_open_cup

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


def _to_out(t: Tournament, entrant_count: int = 0) -> TournamentOut:
    return TournamentOut(
        id=t.id,
        name=t.name,
        description=t.description,
        max_players=t.max_players,
        entry_fee_usdc=micro_to_usdc(t.entry_fee_usdc_micro),
        reward_pool_usdc=micro_to_usdc(t.reward_pool_usdc_micro),
        start_time=t.start_time,
        challenge_types=t.challenge_types or [],
        difficulty=t.difficulty,
        questions_per_round=t.questions_per_round,
        coach_enabled=t.coach_enabled,
        platform_fee_bps=t.platform_fee_bps,
        visibility=t.visibility.value if hasattr(t.visibility, "value") else str(t.visibility),
        status=t.status.value if hasattr(t.status, "value") else str(t.status),
        entrant_count=entrant_count,
        created_at=t.created_at,
    )


@router.get("", response_model=list[TournamentOut])
async def list_tournaments(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Tournament, func.count(TournamentEntry.id).label("entrant_count"))
        .outerjoin(TournamentEntry, TournamentEntry.tournament_id == Tournament.id)
        .where(Tournament.visibility == Visibility.PUBLIC, Tournament.max_players == 6)
        .group_by(Tournament.id)
        .order_by(Tournament.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [_to_out(t, entrant_count or 0) for t, entrant_count in rows]


@router.post("", response_model=TournamentOut)
async def create_tournament(
    body: TournamentCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only. Platform cups are created by the tournament room agent."""
    if body.max_players not in ALLOWED_SIZES:
        raise HTTPException(
            status_code=400,
            detail=f"max_players must be one of {list(ALLOWED_SIZES)}",
        )
    t = Tournament(
        name=body.name,
        description=body.description or f"Created by {user.display_name or user.wallet_address[:10]}",
        max_players=body.max_players,
        entry_fee_usdc_micro=usdc_to_micro(body.entry_fee_usdc),
        reward_pool_usdc_micro=usdc_to_micro(body.reward_pool_usdc),
        start_time=body.start_time,
        challenge_types=body.challenge_types,
        difficulty=body.difficulty,
        questions_per_round=body.questions_per_round,
        coach_enabled=body.coach_enabled,
        platform_fee_bps=body.platform_fee_bps,
        visibility=Visibility(body.visibility),
        invite_code=body.invite_code,
        status=TournamentStatus.UPCOMING,
    )
    db.add(t)
    await db.flush()
    return _to_out(t, 0)


@router.get("/me/rewards")
async def my_rewards(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Reward).where(Reward.user_id == user.id).order_by(Reward.created_at.desc())
    )
    rows = list(result.scalars().all())
    return [
        {
            "id": r.id,
            "tournament_id": r.tournament_id,
            "placement": r.placement,
            "usdc": micro_to_usdc(r.amount_usdc_micro),
            "xp": r.xp_awarded,
            "claimed": r.claimed,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/{tournament_id}", response_model=TournamentOut)
async def get_tournament(tournament_id: str, db: AsyncSession = Depends(get_db)):
    t = await db.get(Tournament, tournament_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    count = await db.scalar(
        select(func.count()).select_from(TournamentEntry).where(TournamentEntry.tournament_id == t.id)
    )
    return _to_out(t, count or 0)


@router.post("/{tournament_id}/join")
async def join_tournament(
    tournament_id: str,
    body: JoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Agent
    from app.routers.agents import lock_strategies_for_tournament

    t = await db.get(Tournament, tournament_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    if t.status not in (TournamentStatus.UPCOMING, TournamentStatus.LOBBY):
        raise HTTPException(status_code=400, detail="Tournament not open for entry")
    if t.visibility == Visibility.PRIVATE and body.invite_code != t.invite_code:
        raise HTTPException(status_code=403, detail="Invalid invite code")

    agent = await db.execute(
        select(Agent).where(Agent.user_id == user.id, Agent.deleted_at.is_(None))
    )
    if not agent.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Create an AI agent before joining")

    existing = await db.execute(
        select(TournamentEntry).where(
            TournamentEntry.tournament_id == tournament_id, TournamentEntry.user_id == user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already joined")

    count = await db.scalar(
        select(func.count()).select_from(TournamentEntry).where(TournamentEntry.tournament_id == tournament_id)
    )
    if (count or 0) >= t.max_players:
        raise HTTPException(status_code=400, detail="Tournament full")

    try:
        await tournament_finance.register_entry(db, user, t)
    except TournamentFinanceError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    if t.status == TournamentStatus.UPCOMING:
        await tournament_director.open_lobby(db, t)

    new_count = (count or 0) + 1
    bracket_ready = False
    if new_count >= t.max_players:
        try:
            groups = await tournament_director.create_balanced_groups(db, t)
            await lock_strategies_for_tournament(db, t)
            started = await tournament_director.start_all_pending_matches(db, t)
            bracket_ready = True
            await emit_tournament(
                tournament_id,
                "groups_created",
                {
                    "groups": [g.name for g in groups],
                    "status": t.status.value,
                    "matches_started": started,
                },
            )
        except ValueError:
            pass
        await ensure_open_cup(db)

    await db.flush()
    await emit_tournament(tournament_id, "player_joined", {"user_id": user.id, "count": new_count})
    return {
        "status": "joined",
        "tournament_id": tournament_id,
        "bracket_ready": bracket_ready,
        "tournament_status": t.status.value,
    }


@router.post("/{tournament_id}/start-groups")
async def start_groups(
    tournament_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = await db.get(Tournament, tournament_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    if not user.is_admin:
        entry = await db.execute(
            select(TournamentEntry).where(
                TournamentEntry.tournament_id == tournament_id, TournamentEntry.user_id == user.id
            )
        )
        if not entry.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Only entrants or admin can form the bracket")
    try:
        groups = await tournament_director.create_balanced_groups(db, t)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from app.routers.agents import lock_strategies_for_tournament

    await lock_strategies_for_tournament(db, t)
    started = await tournament_director.start_all_pending_matches(db, t)
    await emit_tournament(
        tournament_id,
        "groups_created",
        {"groups": [g.name for g in groups], "matches_started": started},
    )
    return {
        "status": t.status.value,
        "groups": [{"name": g.name, "members": g.member_user_ids} for g in groups],
        "matches_started": started,
    }

@router.get("/{tournament_id}/bracket")
async def bracket(tournament_id: str, db: AsyncSession = Depends(get_db)):
    return await tournament_director.get_bracket(db, tournament_id)


@router.get("/{tournament_id}/leaderboard")
async def leaderboard(tournament_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(LeaderboardEntry)
        .where(LeaderboardEntry.tournament_id == tournament_id)
        .order_by(LeaderboardEntry.wins.desc(), LeaderboardEntry.points.desc())
    )
    rows = list(result.scalars().all())
    return [
        {
            "user_id": r.user_id,
            "points": r.points,
            "wins": r.wins,
            "placement": r.placement,
        }
        for r in rows
    ]


@router.get("/{tournament_id}/lobby")
async def lobby(tournament_id: str, db: AsyncSession = Depends(get_db)):
    from app.models import Agent

    t = await db.get(Tournament, tournament_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    entries = await db.execute(select(TournamentEntry).where(TournamentEntry.tournament_id == tournament_id))
    players = list(entries.scalars().all())
    user_ids = [p.user_id for p in players]
    agents_by_user: dict[str, Agent] = {}
    users_by_id: dict[str, User] = {}
    if user_ids:
        ares = await db.execute(select(Agent).where(Agent.user_id.in_(user_ids), Agent.deleted_at.is_(None)))
        for a in ares.scalars().all():
            agents_by_user[a.user_id] = a
        ures = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in ures.scalars().all():
            users_by_id[u.id] = u
    groups_result = await db.execute(
        select(TournamentGroup).where(TournamentGroup.tournament_id == tournament_id)
    )
    groups = list(groups_result.scalars().all())
    return {
        "tournament": _to_out(t, len(players)),
        "players": [
            {
                "user_id": p.user_id,
                "seed": p.seed,
                "agent_id": agents_by_user[p.user_id].id if p.user_id in agents_by_user else None,
                "agent_name": agents_by_user[p.user_id].name if p.user_id in agents_by_user else None,
                "is_system_agent": bool(users_by_id[p.user_id].is_system_agent)
                if p.user_id in users_by_id
                else False,
            }
            for p in players
        ],
        "groups": [{"name": g.name, "members": g.member_user_ids} for g in groups],
    }


@router.post("/{tournament_id}/finalize-rewards")
async def finalize_rewards(
    tournament_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    t = await db.get(Tournament, tournament_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    # Ensure completed
    t = await tournament_director.advance_if_ready(db, t)
    if t.status != TournamentStatus.COMPLETED:
        # Force complete for demo if final done
        from app.models import Match, MatchStatus

        finals = await db.execute(
            select(Match).where(Match.tournament_id == tournament_id, Match.stage == "FINAL")
        )
        finals_list = list(finals.scalars().all())
        if finals_list and all(m.status == MatchStatus.COMPLETED for m in finals_list):
            t.status = TournamentStatus.COMPLETED
            await db.flush()
        else:
            raise HTTPException(status_code=400, detail="Tournament not ready to finalize")

    await tournament_finance.settle_tournament(db, t)
    rewards = await reward_manager.finalize(db, t)
    await emit_tournament(tournament_id, "rewards_ready", {"count": len(rewards)})
    return [{"id": r.id, "user_id": r.user_id, "placement": r.placement, "usdc": micro_to_usdc(r.amount_usdc_micro)} for r in rewards]


@router.post("/rewards/{reward_id}/claim")
async def claim_reward(
    reward_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reward = await db.get(Reward, reward_id)
    if not reward:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        reward = await reward_manager.claim(db, user, reward)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"claimed": reward.claimed, "usdc": micro_to_usdc(reward.amount_usdc_micro), "xp": reward.xp_awarded}