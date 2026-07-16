from __future__ import annotations

import random
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChallengeType, Question, QuestionOption


class PuzzleGenerator:
    """Select and balance football / memory challenges from the question bank."""

    async def pick_questions(
        self,
        db: AsyncSession,
        challenge_type: ChallengeType,
        count: int,
        difficulty: Optional[str] = None,
    ) -> list[Question]:
        stmt = select(Question).where(Question.challenge_type == challenge_type, Question.approved.is_(True))
        if difficulty:
            stmt = stmt.where(Question.difficulty == difficulty)
        result = await db.execute(stmt)
        pool = list(result.scalars().all())
        if not pool:
            raise ValueError(f"No questions for {challenge_type}")
        if len(pool) <= count:
            return pool
        # Mild difficulty balancing: prefer mix
        random.shuffle(pool)
        return pool[:count]

    async def public_question_payload(self, db: AsyncSession, question_id: str) -> dict:
        result = await db.execute(select(Question).where(Question.id == question_id))
        q = result.scalar_one()
        opts = await db.execute(
            select(QuestionOption).where(QuestionOption.question_id == q.id).order_by(QuestionOption.sort_order)
        )
        options = [{"id": o.id, "label": o.label, "sort_order": o.sort_order} for o in opts.scalars().all()]
        return {
            "id": q.id,
            "challenge_type": q.challenge_type.value,
            "prompt": q.prompt,
            "memory_payload": q.memory_payload,
            "media_url": q.media_url,
            "difficulty": q.difficulty,
            "options": options,
        }


puzzle_generator = PuzzleGenerator()