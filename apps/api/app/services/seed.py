"""Seed questions + trial arena. No pre-filled Global Cup / system fillers."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal
from app.data.seed_questions import SEED_QUESTIONS
from app.models import (
    ChallengeType,
    Question,
    QuestionOption,
    Tournament,
    TournamentEntry,
    TournamentStatus,
    User,
    Visibility,
)

TRIAL_ARENA_NAME = "Trial Kickabout"
GLOBAL_CUP_NAME = "Arena64 Global Cup"
PRACTICE_CUP_NAME = "Practice Cup"
PREFILLED_NAMES = (
    GLOBAL_CUP_NAME,
    PRACTICE_CUP_NAME,
    "Arena64 Global Cup Demo",
)


async def ensure_trial_arena(db) -> Tournament:
    """Idempotent free trial container (private — not on the public board)."""
    result = await db.execute(select(Tournament).where(Tournament.name == TRIAL_ARENA_NAME).limit(1))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    t = Tournament(
        name=TRIAL_ARENA_NAME,
        description="Solo practice — watch your AI agent compete. No USDC, no rewards.",
        max_players=9999,
        entry_fee_usdc_micro=0,
        reward_pool_usdc_micro=0,
        challenge_types=["FOOTBALL", "MEMORY", "STADIUM", "PLAYER_ID", "FLAG", "FORMATION"],
        difficulty="medium",
        questions_per_round=5,
        visibility=Visibility.PRIVATE,
        status=TournamentStatus.GROUP_STAGE,
        coach_enabled=False,
    )
    db.add(t)
    await db.flush()
    return t


async def _retire_cup(cup: Tournament, prefix: str) -> None:
    cup.visibility = Visibility.PRIVATE
    cup.status = TournamentStatus.COMPLETED
    if not cup.name.startswith(f"[{prefix}]"):
        cup.name = f"[{prefix}] {cup.name}"


async def _cleanup_prefilled_tournaments(db) -> None:
    """Strip system-agent entries; retire prefilled cups; hide legacy non-6 public cups."""
    system_ids = (
        await db.execute(select(User.id).where(User.is_system_agent.is_(True)))
    ).scalars().all()
    if system_ids:
        await db.execute(
            delete(TournamentEntry).where(TournamentEntry.user_id.in_(list(system_ids)))
        )

    for name in PREFILLED_NAMES:
        result = await db.execute(select(Tournament).where(Tournament.name == name).limit(1))
        cup = result.scalar_one_or_none()
        if cup:
            await _retire_cup(cup, "retired")

    legacy = await db.execute(
        select(Tournament).where(
            Tournament.visibility == Visibility.PUBLIC,
            Tournament.max_players != 6,
        )
    )
    for cup in legacy.scalars().all():
        await _retire_cup(cup, "legacy")


async def _insert_question(db, item: dict) -> None:
    q = Question(
        challenge_type=ChallengeType(item["challenge_type"]),
        prompt=item["prompt"],
        memory_payload=item.get("memory_payload"),
        media_url=item.get("media_url"),
        difficulty=item.get("difficulty", "medium"),
        source="seed",
        approved=True,
        tags=item.get("tags", []),
    )
    db.add(q)
    await db.flush()
    for i, opt in enumerate(item["options"]):
        db.add(
            QuestionOption(
                question_id=q.id,
                label=opt["label"],
                is_correct=opt["is_correct"],
                sort_order=i,
            )
        )


async def seed_if_empty() -> None:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(Question))
        if not count:
            for item in SEED_QUESTIONS:
                await _insert_question(db, item)
        else:
            for ctype in (
                ChallengeType.STADIUM,
                ChallengeType.PLAYER_ID,
                ChallengeType.FLAG,
                ChallengeType.FORMATION,
            ):
                n = await db.scalar(
                    select(func.count()).select_from(Question).where(Question.challenge_type == ctype)
                )
                if not n:
                    for item in SEED_QUESTIONS:
                        if item["challenge_type"] == ctype.value:
                            await _insert_question(db, item)

        await _cleanup_prefilled_tournaments(db)
        await ensure_trial_arena(db)
        await db.commit()
