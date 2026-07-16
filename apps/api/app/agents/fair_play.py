from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FairPlayScore, User


class FairPlayAgent:
    """Flag suspicious patterns for organizer review — never auto-ban."""

    # Soft score adjustments for ranking/tie-break; events are always retained for review.
    PENALTIES = {
        "focus_loss": 0.5,
        "paste_attempt": 1.0,
        "suspicious_timing": 0.75,
        "score_anomaly": 1.0,
    }

    async def record_event(self, db: AsyncSession, user: User, event: str, meta: dict | None = None) -> FairPlayScore:
        fp = user.fair_play
        flags = dict(fp.flags or {})
        events = list(flags.get("events", []))
        events.append({"event": event, "meta": meta or {}, "at": datetime.utcnow().isoformat()})
        flags["events"] = events[-50:]
        flags["needs_review"] = True
        counts = dict(flags.get("counts", {}))
        counts[event] = int(counts.get(event, 0)) + 1
        flags["counts"] = counts

        penalty = self.PENALTIES.get(event, 0.25)
        fp.score = max(0.0, fp.score - penalty)
        fp.flags = flags
        await db.flush()
        return fp

    async def note_clean_round(self, db: AsyncSession, user: User) -> FairPlayScore:
        fp = user.fair_play
        fp.score = min(100.0, fp.score + 0.2)
        await db.flush()
        return fp


fair_play_agent = FairPlayAgent()
