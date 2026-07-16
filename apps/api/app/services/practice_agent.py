"""In-API practice answerer — runs trial matches without a separate ai-runtime process."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.puzzle_generator import puzzle_generator
from app.core.database import AsyncSessionLocal
from app.models import (
    Agent,
    AgentDecisionLog,
    Answer,
    Match,
    MatchStatus,
    QuestionOption,
    Round,
    User,
)
from app.services.scoring import score_answer

logger = logging.getLogger("arena64.practice_agent")

_running: set[str] = set()


def _pick_option(options: list[dict], risk: str) -> tuple[str | None, float, str]:
    if not options:
        return None, 0.2, "No options available"
    if risk == "high":
        opt = random.choice(options)
        conf = 0.42
    elif risk == "low":
        opt = options[0]
        conf = 0.72
    else:
        opt = options[0] if random.random() < 0.65 else random.choice(options)
        conf = 0.55
    return opt["id"], conf, f"Practice {risk} pick"


async def _answer_once(match_id: str, user_id: str, round_id: str) -> tuple[bool, float]:
    """
    Answer one question.
    Returns (continue?, think_seconds_already_applied).
    """
    async with AsyncSessionLocal() as db:
        match = await db.get(Match, match_id)
        rnd = await db.get(Round, round_id)
        if not match or not rnd or match.status != MatchStatus.LIVE:
            return False, 0.0
        if rnd.active_question_index >= len(rnd.question_ids or []):
            return False, 0.0

        qid = rnd.question_ids[rnd.active_question_index]
        prior = await db.execute(
            select(Answer).where(
                Answer.round_id == rnd.id,
                Answer.question_id == qid,
                Answer.user_id == user_id,
            )
        )
        if prior.scalar_one_or_none():
            from app.routers.challenges import _maybe_advance_round

            await _maybe_advance_round(db, rnd, match)
            await db.commit()
            still = rnd.active_question_index < len(rnd.question_ids or [])
            return still, 0.0

        agent_res = await db.execute(
            select(Agent)
            .options(selectinload(Agent.strategy))
            .where(Agent.user_id == user_id, Agent.deleted_at.is_(None))
        )
        agent = agent_res.scalar_one_or_none()
        if not agent:
            return False, 0.0

        payload = await puzzle_generator.public_question_payload(db, qid)
        options = list(payload.get("options") or [])
        risk = (agent.strategy.risk_level if agent.strategy else "medium") or "medium"
        thinking_ms = int(agent.strategy.thinking_time_ms if agent.strategy else 800)
        think_s = max(0.4, min(thinking_ms / 1000.0, 2.5))

        # Release DB during "thinking"
        await db.commit()

    await asyncio.sleep(think_s)

    async with AsyncSessionLocal() as db:
        match = await db.get(Match, match_id)
        rnd = await db.get(Round, round_id)
        if not match or not rnd or match.status != MatchStatus.LIVE:
            return False, think_s
        if rnd.active_question_index >= len(rnd.question_ids or []):
            return False, think_s
        if rnd.question_ids[rnd.active_question_index] != qid:
            return True, think_s

        prior = await db.execute(
            select(Answer).where(
                Answer.round_id == rnd.id,
                Answer.question_id == qid,
                Answer.user_id == user_id,
            )
        )
        if prior.scalar_one_or_none():
            return True, think_s

        agent_res = await db.execute(
            select(Agent).where(Agent.user_id == user_id, Agent.deleted_at.is_(None))
        )
        agent = agent_res.scalar_one_or_none()
        if not agent:
            return False, think_s

        option_id, confidence, reasoning = _pick_option(options, risk)
        is_correct = False
        if option_id:
            opt = await db.get(QuestionOption, option_id)
            is_correct = bool(opt and opt.is_correct)

        remaining = random.randint(8, 18)
        points = score_answer(is_correct, remaining)
        db.add(
            Answer(
                round_id=rnd.id,
                question_id=qid,
                user_id=user_id,
                option_id=option_id,
                is_correct=is_correct,
                points=points,
                remaining_seconds=remaining,
                nonce=f"practice-{qid[:8]}",
            )
        )
        if user_id == match.player_a_id:
            match.score_a += points
        elif user_id == match.player_b_id:
            match.score_b += points

        db.add(
            AgentDecisionLog(
                agent_id=agent.id,
                match_id=match.id,
                round_id=rnd.id,
                question_id=qid,
                option_id=option_id,
                confidence=confidence,
                reasoning=reasoning,
                used_mcp=False,
                used_premium=False,
                used_coach_credit=False,
                latency_ms=int(think_s * 1000),
                accelerated=True,
                is_correct=is_correct,
                created_at=datetime.utcnow(),
            )
        )

        from app.routers.challenges import _maybe_advance_round

        await db.flush()
        await _maybe_advance_round(db, rnd, match)
        await db.commit()
        await db.refresh(rnd)
        await db.refresh(match)
        still = (
            match.status == MatchStatus.LIVE
            and rnd.active_question_index < len(rnd.question_ids or [])
        )
        return still, think_s


async def run_practice_match(match_id: str, user_id: str, round_id: str) -> None:
    if match_id in _running:
        return
    _running.add(match_id)
    try:
        logger.info("Practice agent started match=%s", match_id)
        await asyncio.sleep(1.2)
        for _ in range(12):
            try:
                cont, _ = await _answer_once(match_id, user_id, round_id)
            except Exception:
                logger.exception("Practice answer failed match=%s", match_id)
                await asyncio.sleep(1.5)
                continue
            if not cont:
                break
            await asyncio.sleep(0.5)
        logger.info("Practice agent finished match=%s", match_id)
    finally:
        _running.discard(match_id)


def schedule_practice_match(match_id: str, user_id: str, round_id: str) -> None:
    """Fire-and-forget from the trial start request."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(run_practice_match(match_id, user_id, round_id))
