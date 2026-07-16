from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CoachCredits, QuestionOption, User


class InsufficientCredits(Exception):
    pass


COACH_ABILITIES = {
    "remove_two": {"cost": 1, "label": "Remove Two Wrong Answers"},
    "add_five_seconds": {"cost": 2, "label": "Add Five Seconds"},
    "replay_memory": {"cost": 2, "label": "Replay Memory Challenge"},
    "round_review": {"cost": 1, "label": "Round Performance Review"},
}

COACH_PACKS = {
    "starter": {"credits": 2, "price_usdc_micro": 1_000_000, "label": "Starter"},
    "pro": {"credits": 5, "price_usdc_micro": 2_000_000, "label": "Pro"},
    "champion": {"credits": 10, "price_usdc_micro": 3_500_000, "label": "Champion"},
}


class AICoach:
    """Consume coach credits for in-match abilities (no chain txs)."""

    async def spend(self, db: AsyncSession, user: User, ability: str) -> dict:
        if ability not in COACH_ABILITIES:
            raise ValueError("Unknown ability")
        cost = COACH_ABILITIES[ability]["cost"]
        credits = user.coach_credits
        if credits.credits < cost:
            raise InsufficientCredits(f"Need {cost} credits")
        credits.credits -= cost
        await db.flush()
        return {"ability": ability, "cost": cost, "remaining": credits.credits}

    async def remove_two_wrong(self, db: AsyncSession, question_id: str) -> list[str]:
        result = await db.execute(select(QuestionOption).where(QuestionOption.question_id == question_id))
        options = list(result.scalars().all())
        wrong = [o.id for o in options if not o.is_correct]
        return random.sample(wrong, min(2, len(wrong)))

    async def add_credits(self, db: AsyncSession, user: User, amount: int) -> CoachCredits:
        user.coach_credits.credits += amount
        await db.flush()
        return user.coach_credits


ai_coach = AICoach()