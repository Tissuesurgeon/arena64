from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_optional_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models import Agent, LeaderboardEntry, Tournament, TournamentHistory, User
from app.services.x402_payment import X402PaymentError, x402_payment

router = APIRouter(tags=["insights"])
settings = get_settings()


@router.get("/player/analysis")
async def player_analysis(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
    tournament_id: str | None = None,
):
    agent_res = await db.execute(
        select(Agent).where(Agent.user_id == user.id, Agent.deleted_at.is_(None))
    )
    agent = agent_res.scalar_one_or_none()
    try:
        pay = await x402_payment.authorize_premium(
            db,
            user,
            service_name="premium_insight",
            tournament_id=tournament_id,
            x_payment=x_payment,
            agent=agent,
        )
    except X402PaymentError as exc:
        raise HTTPException(
            status_code=402,
            detail={
                "message": str(exc),
                "accepts": [
                    {
                        "network": settings.x402_network,
                        "asset": settings.injective_usdc_address,
                        "amount": str(x402_payment.premium_cost_micro()),
                    }
                ],
                "facilitator": settings.x402_facilitator_url,
            },
        ) from exc

    hist = await db.execute(
        select(TournamentHistory)
        .where(TournamentHistory.user_id == user.id)
        .order_by(TournamentHistory.created_at.desc())
        .limit(10)
    )
    rows = list(hist.scalars().all())
    return {
        "user_id": user.id,
        "xp": user.xp,
        "fair_play": user.fair_play.score if user.fair_play else 100,
        "recent": [{"tournament_id": h.tournament_id, "placement": h.placement, "points": h.points} for h in rows],
        "insight": "Prioritize memory challenges — your football accuracy outpaces recall speed.",
        "payment": pay,
    }


@router.get("/tournament/{tournament_id}/insights")
async def tournament_insights(
    tournament_id: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
):
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    try:
        pay = await x402_payment.authorize_premium(
            db,
            user,
            service_name="tournament_insights",
            tournament_id=tournament_id,
            x_payment=x_payment,
        )
    except X402PaymentError as exc:
        raise HTTPException(
            status_code=402,
            detail={
                "message": str(exc),
                "accepts": [
                    {
                        "network": settings.x402_network,
                        "asset": settings.injective_usdc_address,
                        "amount": str(x402_payment.premium_cost_micro()),
                    }
                ],
            },
        ) from exc

    t = await db.get(Tournament, tournament_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    lb = await db.execute(
        select(LeaderboardEntry)
        .where(LeaderboardEntry.tournament_id == tournament_id)
        .order_by(LeaderboardEntry.points.desc())
        .limit(5)
    )
    top = list(lb.scalars().all())
    return {
        "tournament_id": tournament_id,
        "status": t.status.value,
        "top": [{"user_id": e.user_id, "points": e.points, "wins": e.wins} for e in top],
        "insight": "Group stage variance is high — early pace setters often fade in knockout memory rounds.",
        "payment": pay,
    }
