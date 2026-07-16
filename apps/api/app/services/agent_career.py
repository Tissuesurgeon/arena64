"""Post-tournament memory + career updates for AI agents (Memory Manager)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Agent,
    AgentCareer,
    AgentDecisionLog,
    AgentMemory,
    Answer,
    Match,
    MatchStatus,
    Question,
    Round,
    Tournament,
    TournamentEntry,
    TournamentStatus,
)
from app.routers.agents import unlock_strategies_for_tournament


async def update_careers_after_match(db: AsyncSession, match: Match) -> None:
    if match.status != MatchStatus.COMPLETED:
        return
    for uid in (match.player_a_id, match.player_b_id):
        if not uid:
            continue
        won = match.winner_id == uid
        agent = await db.scalar(select(Agent).where(Agent.user_id == uid, Agent.deleted_at.is_(None)))
        if not agent:
            continue
        career = await db.scalar(select(AgentCareer).where(AgentCareer.agent_id == agent.id))
        if not career:
            career = AgentCareer(agent_id=agent.id)
            db.add(career)
            await db.flush()
        career.matches_played += 1
        if won:
            career.wins += 1
        else:
            career.losses += 1
        career.updated_at = datetime.utcnow()


async def _category_stats_for_user(
    db: AsyncSession, user_id: str, agent_id: str, match_ids: list[str]
) -> dict[str, dict]:
    """accuracy / attempts / avg_confidence by challenge_type."""
    stats: dict[str, dict] = {}
    if not match_ids:
        return stats

    rnds = await db.execute(select(Round).where(Round.match_id.in_(match_ids)))
    for rnd in rnds.scalars().all():
        arows = await db.execute(
            select(Answer).where(Answer.round_id == rnd.id, Answer.user_id == user_id)
        )
        for a in arows.scalars().all():
            q = await db.get(Question, a.question_id)
            if not q:
                continue
            cat = q.challenge_type.value if hasattr(q.challenge_type, "value") else str(q.challenge_type)
            bucket = stats.setdefault(cat, {"attempts": 0, "correct": 0, "confidence_sum": 0.0, "confidence_n": 0})
            bucket["attempts"] += 1
            if a.is_correct:
                bucket["correct"] += 1

    logs = await db.execute(
        select(AgentDecisionLog).where(
            AgentDecisionLog.agent_id == agent_id,
            AgentDecisionLog.match_id.in_(match_ids),
        )
    )
    for log in logs.scalars().all():
        q = await db.get(Question, log.question_id)
        if not q:
            continue
        cat = q.challenge_type.value if hasattr(q.challenge_type, "value") else str(q.challenge_type)
        if cat not in stats:
            continue
        stats[cat]["confidence_sum"] += float(log.confidence or 0)
        stats[cat]["confidence_n"] += 1

    out: dict[str, dict] = {}
    for cat, b in stats.items():
        attempts = max(1, b["attempts"])
        conf_n = b["confidence_n"]
        out[cat] = {
            "attempts": b["attempts"],
            "correct": b["correct"],
            "accuracy": round(b["correct"] / attempts, 3) if b["attempts"] else 0.0,
            "avg_confidence": round(b["confidence_sum"] / conf_n, 3) if conf_n else None,
        }
    return out


async def finalize_agent_tournament(db: AsyncSession, tournament: Tournament) -> None:
    """Roll up memory/career when a tournament completes; unlock strategies."""
    if tournament.status != TournamentStatus.COMPLETED:
        return

    entries = await db.execute(
        select(TournamentEntry).where(TournamentEntry.tournament_id == tournament.id)
    )
    user_ids = [e.user_id for e in entries.scalars().all()]

    final = await db.execute(
        select(Match).where(Match.tournament_id == tournament.id, Match.stage == "FINAL").limit(1)
    )
    champ_id = None
    fm = final.scalar_one_or_none()
    if fm:
        champ_id = fm.winner_id

    match_ids = list(
        (await db.execute(select(Match.id).where(Match.tournament_id == tournament.id))).scalars().all()
    )

    for uid in user_ids:
        agent = await db.scalar(select(Agent).where(Agent.user_id == uid, Agent.deleted_at.is_(None)))
        if not agent:
            continue
        career = await db.scalar(select(AgentCareer).where(AgentCareer.agent_id == agent.id))
        if not career:
            career = AgentCareer(agent_id=agent.id)
            db.add(career)
            await db.flush()
        career.tournaments_played += 1
        placed = "champion" if champ_id == uid else "participant"
        if champ_id == uid:
            career.championships += 1
            agent.arena_rating += 40
        else:
            agent.arena_rating = max(800.0, agent.arena_rating + 5)

        log_rows: list[AgentDecisionLog] = []
        if match_ids:
            logs = await db.execute(
                select(AgentDecisionLog).where(
                    AgentDecisionLog.agent_id == agent.id,
                    AgentDecisionLog.match_id.in_(match_ids),
                )
            )
            log_rows = list(logs.scalars().all())

        correct = 0
        total_a = 0
        if match_ids:
            rnds = await db.execute(select(Round).where(Round.match_id.in_(match_ids)))
            for rnd in rnds.scalars().all():
                arows = await db.execute(
                    select(Answer).where(Answer.round_id == rnd.id, Answer.user_id == uid)
                )
                for a in arows.scalars().all():
                    total_a += 1
                    if a.is_correct:
                        correct += 1

        category_stats = await _category_stats_for_user(db, uid, agent.id, match_ids)
        # Merge into career.category_stats
        merged = dict(career.category_stats or {})
        for cat, st in category_stats.items():
            prev = merged.get(cat) or {"attempts": 0, "correct": 0}
            merged[cat] = {
                "attempts": int(prev.get("attempts", 0)) + int(st["attempts"]),
                "correct": int(prev.get("correct", 0)) + int(st["correct"]),
                "accuracy": st["accuracy"],
                "avg_confidence": st.get("avg_confidence"),
            }
        career.category_stats = merged

        n = max(1, career.tournaments_played)
        if total_a:
            acc = correct / total_a
            career.average_accuracy = (career.average_accuracy * (n - 1) + acc) / n

        mcp_n = sum(1 for r in log_rows if r.used_mcp) if log_rows else 0
        prem_n = sum(1 for r in log_rows if r.used_premium) if log_rows else 0
        coach_n = sum(1 for r in log_rows if r.used_coach_credit) if log_rows else 0
        avg_conf = (sum(r.confidence for r in log_rows) / len(log_rows)) if log_rows else 0.0
        if log_rows:
            avg_lat = sum(r.latency_ms for r in log_rows) / len(log_rows)
            career.average_response_ms = (career.average_response_ms * (n - 1) + avg_lat) / n
            career.resource_efficiency = max(0.0, 1.0 - (mcp_n + prem_n) / max(1, len(log_rows)))

        weak = [c for c, s in category_stats.items() if float(s.get("accuracy") or 0) < 0.5]
        strong = [c for c, s in category_stats.items() if float(s.get("accuracy") or 0) >= 0.7]

        memory = await db.scalar(select(AgentMemory).where(AgentMemory.agent_id == agent.id))
        if not memory:
            memory = AgentMemory(agent_id=agent.id)
            db.add(memory)
        strengths = list((memory.summary or {}).get("strengths") or [])
        weaknesses = list((memory.summary or {}).get("weaknesses") or [])
        for s in strong:
            if s.lower() not in [x.lower() for x in strengths]:
                strengths.append(s)
        for w in weak:
            if w.lower() not in [x.lower() for x in weaknesses]:
                weaknesses.append(w)
        if career.average_accuracy >= 0.6 and "solid accuracy" not in strengths:
            strengths.append("solid accuracy")
        elif career.average_accuracy < 0.5 and "accuracy dips under pressure" not in weaknesses:
            weaknesses.append("accuracy dips under pressure")

        memory.summary = {
            "strengths": strengths[-8:],
            "weaknesses": weaknesses[-8:],
            "avg_confidence": round(avg_conf, 3),
            "mcp_usage": mcp_n,
            "premium_usage": prem_n,
            "coach_usage": coach_n,
            "coach_credit_efficiency": career.resource_efficiency,
            "category_stats": category_stats,
            "tournament": {
                "id": tournament.id,
                "name": tournament.name,
                "result": placed,
                "questions": total_a,
                "correct": correct,
                "resources_used": {"mcp": mcp_n, "premium": prem_n, "coach": coach_n},
            },
            "recommendation": (
                "Raise confidence threshold and conserve premium budget."
                if career.resource_efficiency < 0.4
                else (
                    f"Drill weak categories next cup: {', '.join(weak[:3])}."
                    if weak
                    else "Lean into MCP on stadium/player categories next cup."
                )
            ),
        }
        memory.updated_at = datetime.utcnow()

        career.updated_at = datetime.utcnow()

    await unlock_strategies_for_tournament(db, tournament.id)
    await db.flush()
