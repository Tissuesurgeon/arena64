import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.fair_play import fair_play_agent
from app.agents.puzzle_generator import puzzle_generator
from app.agents.tournament_director import tournament_director
from app.core.auth import get_current_user, require_admin
from app.core.database import get_db
from app.models import Answer, Match, MatchStatus, QuestionOption, Round, Tournament, User
from app.realtime.ws import emit_tournament
from app.schemas import AnswerSubmit
from app.services.scoring import score_answer

router = APIRouter(tags=["challenges"])


def _can_operate_match(user: User, match: Match) -> bool:
    if user.is_admin:
        return True
    return user.id in {match.player_a_id, match.player_b_id}


@router.post("/matches/{match_id}/start")
async def start_match(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if not _can_operate_match(user, match):
        raise HTTPException(status_code=403, detail="Only match players or admin can start")
    if match.status == MatchStatus.LIVE:
        # Return existing live round
        result = await db.execute(
            select(Round).where(Round.match_id == match.id).order_by(Round.round_number.desc())
        )
        rnd = result.scalars().first()
        if rnd:
            return {
                "round_id": rnd.id,
                "question_ids": rnd.question_ids,
                "challenge_type": rnd.challenge_type.value,
            }
    if match.status == MatchStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Match already completed")

    t = await db.get(Tournament, match.tournament_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    try:
        rnd = await tournament_director.start_match(
            db, match, t.questions_per_round, t.challenge_types or ["FOOTBALL"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await emit_tournament(match.tournament_id, "match_started", {"match_id": match.id, "round_id": rnd.id})
    return {"round_id": rnd.id, "question_ids": rnd.question_ids, "challenge_type": rnd.challenge_type.value}


@router.get("/rounds/{round_id}/current")
async def current_question(round_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rnd = await db.get(Round, round_id)
    if not rnd:
        raise HTTPException(status_code=404, detail="Round not found")
    if rnd.active_question_index >= len(rnd.question_ids):
        return {"done": True}

    match = await db.get(Match, rnd.match_id)
    user_answered = False

    # If the player already answered the active question (e.g. page refresh), advance when ready.
    if match:
        qid = rnd.question_ids[rnd.active_question_index]
        prior = await db.execute(
            select(Answer).where(
                Answer.round_id == rnd.id,
                Answer.question_id == qid,
                Answer.user_id == user.id,
            )
        )
        if prior.scalar_one_or_none():
            advance = await _maybe_advance_round(db, rnd, match)
            if advance and advance.get("done"):
                return {"done": True, "winner_id": advance.get("winner_id")}
            if advance and advance.get("advanced"):
                await db.flush()
            elif rnd.active_question_index < len(rnd.question_ids):
                # Still on this question — waiting for opponent
                user_answered = True
            if rnd.active_question_index >= len(rnd.question_ids):
                return {"done": True, "winner_id": match.winner_id if match else None}

    qid = rnd.question_ids[rnd.active_question_index]
    payload = await puzzle_generator.public_question_payload(db, qid)
    nonce = secrets.token_hex(8)
    seconds = 20
    if payload.get("challenge_type") == "MEMORY":
        seconds = 20
        payload["memory_seconds"] = (payload.get("memory_payload") or {}).get("display_seconds", 10)
    deadline = datetime.utcnow() + timedelta(seconds=seconds)
    return {
        "done": False,
        "round_id": rnd.id,
        "index": rnd.active_question_index,
        "total": len(rnd.question_ids),
        "nonce": nonce,
        "deadline": deadline.isoformat() + "Z",
        "seconds": seconds,
        "user_answered": user_answered,
        "question": payload,
    }


async def _maybe_advance_round(db: AsyncSession, rnd: Round, match: Match) -> dict | None:
    """Auto-advance when both players have answered the active question (or solo)."""
    qid = rnd.question_ids[rnd.active_question_index]
    players = [p for p in (match.player_a_id, match.player_b_id) if p]
    if not players:
        return None
    answered = await db.scalar(
        select(func.count())
        .select_from(Answer)
        .where(Answer.round_id == rnd.id, Answer.question_id == qid, Answer.user_id.in_(players))
    )
    if (answered or 0) < len(players):
        return None

    rnd.active_question_index += 1
    await db.flush()
    if rnd.active_question_index >= len(rnd.question_ids):
        await tournament_director.resolve_match(db, match)
        # Trial matches do not advance a bracket
        if match.stage != "TRIAL":
            t = await db.get(Tournament, match.tournament_id)
            if t:
                await tournament_director.advance_if_ready(db, t)
        await emit_tournament(
            match.tournament_id, "match_completed", {"match_id": match.id, "winner_id": match.winner_id}
        )
        return {"done": True, "winner_id": match.winner_id, "advanced": True}
    await emit_tournament(match.tournament_id, "next_question", {"index": rnd.active_question_index})
    return {"done": False, "index": rnd.active_question_index, "advanced": True}


@router.post("/answers")
async def submit_answer(
    body: AnswerSubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.exc import IntegrityError

    rnd = await db.get(Round, body.round_id)
    if not rnd:
        raise HTTPException(status_code=404, detail="Round not found")

    match = await db.get(Match, rnd.match_id)

    existing = await db.execute(
        select(Answer).where(
            Answer.round_id == body.round_id,
            Answer.question_id == body.question_id,
            Answer.user_id == user.id,
        )
    )
    prior = existing.scalar_one_or_none()
    if prior:
        advance = None
        if match and rnd.active_question_index < len(rnd.question_ids):
            if body.question_id == rnd.question_ids[rnd.active_question_index]:
                advance = await _maybe_advance_round(db, rnd, match)
        return {
            "correct": prior.is_correct,
            "points": prior.points,
            "match_score_a": match.score_a if match else None,
            "match_score_b": match.score_b if match else None,
            "advance": advance,
            "already_answered": True,
        }

    is_correct = False
    if body.option_id:
        opt = await db.get(QuestionOption, body.option_id)
        if opt and opt.question_id == body.question_id:
            is_correct = opt.is_correct

    points = score_answer(is_correct, body.remaining_seconds)
    answer = Answer(
        round_id=body.round_id,
        question_id=body.question_id,
        user_id=user.id,
        option_id=body.option_id,
        is_correct=is_correct,
        points=points,
        remaining_seconds=body.remaining_seconds,
        nonce=body.nonce,
    )
    db.add(answer)

    try:
        await db.flush()
    except IntegrityError:
        # Concurrent double-submit — treat as already answered
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already answered") from None

    if match:
        if user.id == match.player_a_id:
            match.score_a += points
        elif user.id == match.player_b_id:
            match.score_b += points
        await emit_tournament(
            match.tournament_id,
            "score_update",
            {
                "match_id": match.id,
                "score_a": match.score_a,
                "score_b": match.score_b,
                "user_id": user.id,
                "points": points,
            },
        )

    if is_correct:
        await fair_play_agent.note_clean_round(db, user)

    await db.flush()

    advance = None
    if match and rnd.active_question_index < len(rnd.question_ids):
        if body.question_id == rnd.question_ids[rnd.active_question_index]:
            advance = await _maybe_advance_round(db, rnd, match)

    return {
        "correct": is_correct,
        "points": points,
        "match_score_a": match.score_a if match else None,
        "match_score_b": match.score_b if match else None,
        "advance": advance,
    }


@router.post("/rounds/{round_id}/next")
async def next_question(round_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rnd = await db.get(Round, round_id)
    if not rnd:
        raise HTTPException(status_code=404, detail="Round not found")
    match = await db.get(Match, rnd.match_id)
    if not match or not _can_operate_match(user, match):
        raise HTTPException(status_code=403, detail="Only match players or admin can advance")
    rnd.active_question_index += 1
    await db.flush()
    if rnd.active_question_index >= len(rnd.question_ids) and match:
        await tournament_director.resolve_match(db, match)
        if match.stage != "TRIAL":
            t = await db.get(Tournament, match.tournament_id)
            if t:
                await tournament_director.advance_if_ready(db, t)
        await emit_tournament(
            match.tournament_id, "match_completed", {"match_id": match.id, "winner_id": match.winner_id}
        )
        return {"done": True, "winner_id": match.winner_id}
    await emit_tournament(match.tournament_id if match else "", "next_question", {"index": rnd.active_question_index})
    return {"done": False, "index": rnd.active_question_index}


@router.get("/matches/{match_id}")
async def get_match(match_id: str, db: AsyncSession = Depends(get_db)):
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Not found")
    result = await db.execute(
        select(Round).where(Round.match_id == match.id).order_by(Round.round_number.desc())
    )
    rnd = result.scalars().first()
    return {
        "id": match.id,
        "tournament_id": match.tournament_id,
        "stage": match.stage,
        "group_name": match.group_name,
        "player_a_id": match.player_a_id,
        "player_b_id": match.player_b_id,
        "score_a": match.score_a,
        "score_b": match.score_b,
        "winner_id": match.winner_id,
        "status": match.status.value,
        "round_id": rnd.id if rnd else None,
    }


@router.get("/tournaments/{tournament_id}/my-matches")
async def my_matches(
    tournament_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Match).where(
            Match.tournament_id == tournament_id,
            (Match.player_a_id == user.id) | (Match.player_b_id == user.id),
        )
    )
    rows = list(result.scalars().all())
    out = []
    for m in rows:
        rnd_res = await db.execute(
            select(Round).where(Round.match_id == m.id).order_by(Round.round_number.desc())
        )
        rnd = rnd_res.scalars().first()
        out.append(
            {
                "id": m.id,
                "stage": m.stage,
                "status": m.status.value,
                "player_a_id": m.player_a_id,
                "player_b_id": m.player_b_id,
                "score_a": m.score_a,
                "score_b": m.score_b,
                "winner_id": m.winner_id,
                "round_id": rnd.id if rnd else None,
            }
        )
    return out
