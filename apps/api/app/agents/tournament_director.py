from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChallengeType,
    LeaderboardEntry,
    Match,
    MatchStatus,
    Question,
    Round,
    Tournament,
    TournamentEntry,
    TournamentGroup,
    TournamentStatus,
    User,
)
from app.services.scoring import compare_tiebreak

logger = logging.getLogger(__name__)

GROUP_NAMES = list("ABCDEFGH")
ALLOWED_SIZES = (6,)


class TournamentDirector:
    """Create groups, brackets, advance stages, auto-start matches."""

    async def open_lobby(self, db: AsyncSession, tournament: Tournament) -> Tournament:
        tournament.status = TournamentStatus.LOBBY
        await db.flush()
        return tournament

    async def create_balanced_groups(self, db: AsyncSession, tournament: Tournament) -> list[TournamentGroup]:
        result = await db.execute(select(TournamentEntry).where(TournamentEntry.tournament_id == tournament.id))
        entries = list(result.scalars().all())
        if len(entries) != tournament.max_players:
            raise ValueError(f"Need {tournament.max_players} players, have {len(entries)}")

        existing_matches = await db.execute(select(Match).where(Match.tournament_id == tournament.id).limit(1))
        if existing_matches.scalar_one_or_none():
            raise ValueError("Bracket already formed")

        n = tournament.max_players
        if n not in ALLOWED_SIZES:
            raise ValueError(f"Unsupported field size {n}; use {ALLOWED_SIZES}")

        random.shuffle(entries)
        for idx, entry in enumerate(entries):
            entry.seed = idx + 1

        groups: list[TournamentGroup] = []

        if n == 4:
            groups = [self._make_group(db, tournament, "A", entries)]
        elif n == 6:
            groups = [
                self._make_group(db, tournament, "A", entries[0:3]),
                self._make_group(db, tournament, "B", entries[3:6]),
            ]
        elif n == 10:
            groups = [
                self._make_group(db, tournament, "A", entries[0:5]),
                self._make_group(db, tournament, "B", entries[5:10]),
            ]
        else:
            # 16 or 32 → groups of 4
            group_count = n // 4
            for i in range(group_count):
                chunk = entries[i * 4 : (i + 1) * 4]
                groups.append(self._make_group(db, tournament, GROUP_NAMES[i], chunk))

        tournament.status = TournamentStatus.GROUP_STAGE
        await db.flush()
        return groups

    def _make_group(
        self,
        db: AsyncSession,
        tournament: Tournament,
        name: str,
        entries: list[TournamentEntry],
    ) -> TournamentGroup:
        members = [m.user_id for m in entries]
        group = TournamentGroup(
            tournament_id=tournament.id,
            name=name,
            member_user_ids=members,
        )
        db.add(group)
        self._add_group_matches(db, tournament, name, members)
        return group

    def _add_group_matches(
        self, db: AsyncSession, tournament: Tournament, group_name: str, members: list[str]
    ) -> None:
        size = len(members)
        if size == 3:
            pairs = [(0, 1), (0, 2), (1, 2)]
        elif size == 4:
            pairs = [(0, 1), (2, 3), (0, 2), (1, 3)]
        elif size == 5:
            # Compact: each player appears twice
            pairs = [(0, 1), (2, 3), (0, 4), (1, 2), (3, 4)]
        else:
            raise ValueError(f"Unsupported group size {size}")

        for slot, (i, j) in enumerate(pairs):
            db.add(
                Match(
                    tournament_id=tournament.id,
                    stage="GROUP",
                    group_name=group_name,
                    player_a_id=members[i],
                    player_b_id=members[j],
                    bracket_slot=slot,
                    status=MatchStatus.PENDING,
                )
            )

    async def start_match(
        self,
        db: AsyncSession,
        match: Match,
        questions_per_round: int,
        challenge_types: list[str],
        *,
        mixed: bool = False,
    ) -> Round:
        if match.status == MatchStatus.LIVE:
            existing = await db.execute(
                select(Round).where(Round.match_id == match.id).order_by(Round.round_number.desc())
            )
            rnd = existing.scalars().first()
            if rnd:
                return rnd

        types = challenge_types or ["FOOTBALL"]
        selected: list[Question] = []

        if mixed or match.stage == "TRIAL":
            per_type = max(2, (questions_per_round // max(1, len(types))) + 2)
            pools: list[Question] = []
            for tname in types:
                try:
                    ctype = ChallengeType(tname)
                except ValueError:
                    continue
                q_result = await db.execute(
                    select(Question)
                    .where(Question.challenge_type == ctype, Question.approved.is_(True))
                    .order_by(Question.id)
                    .limit(40)
                )
                type_pool = list(q_result.scalars().all())
                if type_pool:
                    pools.extend(random.sample(type_pool, min(per_type, len(type_pool))))
            if len(pools) < questions_per_round:
                raise ValueError("Not enough approved questions for trial")
            selected = random.sample(pools, questions_per_round)
            qtype = selected[0].challenge_type
        else:
            qtype = ChallengeType(random.choice(types))
            q_result = await db.execute(
                select(Question)
                .where(Question.challenge_type == qtype, Question.approved.is_(True))
                .order_by(Question.id)
                .limit(80)
            )
            pool = list(q_result.scalars().all())
            if len(pool) < questions_per_round:
                raise ValueError("Not enough approved questions")
            selected = random.sample(pool, questions_per_round)

        now = datetime.utcnow()
        duration = 20 if qtype == ChallengeType.FOOTBALL else 30
        rnd = Round(
            match_id=match.id,
            round_number=1,
            challenge_type=qtype,
            started_at=now,
            ends_at=now + timedelta(seconds=duration * questions_per_round + 15),
            question_ids=[q.id for q in selected],
            active_question_index=0,
        )
        db.add(rnd)
        match.status = MatchStatus.LIVE
        await db.flush()
        return rnd

    async def start_all_pending_matches(self, db: AsyncSession, tournament: Tournament) -> int:
        """Flip every PENDING match in the tournament to LIVE with a round."""
        result = await db.execute(
            select(Match).where(
                Match.tournament_id == tournament.id,
                Match.status == MatchStatus.PENDING,
            )
        )
        pending = list(result.scalars().all())
        started = 0
        types = tournament.challenge_types or ["FOOTBALL"]
        qpr = tournament.questions_per_round or 5
        for match in pending:
            if not match.player_a_id or not match.player_b_id:
                continue
            try:
                await self.start_match(db, match, qpr, types)
                started += 1
            except ValueError as exc:
                logger.warning("auto-start match %s failed: %s", match.id, exc)
        await db.flush()
        return started

    async def resolve_match(self, db: AsyncSession, match: Match) -> Match:
        if match.player_a_id and not match.player_b_id:
            match.winner_id = match.player_a_id
            match.status = MatchStatus.COMPLETED
            if match.stage != "TRIAL":
                await self._bump_leaderboard(db, match)
            from app.services.agent_career import update_careers_after_match

            await update_careers_after_match(db, match)
            await db.flush()
            return match

        if match.score_a == match.score_b:
            winner = await self._tiebreak(db, match)
            match.winner_id = winner
        else:
            match.winner_id = match.player_a_id if match.score_a > match.score_b else match.player_b_id
        match.status = MatchStatus.COMPLETED
        await self._bump_leaderboard(db, match)
        from app.services.agent_career import update_careers_after_match

        await update_careers_after_match(db, match)
        await db.flush()
        return match

    async def _tiebreak(self, db: AsyncSession, match: Match) -> str:
        assert match.player_a_id and match.player_b_id
        a = await db.get(User, match.player_a_id)
        b = await db.get(User, match.player_b_id)
        fp_a = a.fair_play.score if a and a.fair_play else 100.0
        fp_b = b.fair_play.score if b and b.fair_play else 100.0
        cmp = compare_tiebreak(fp_a, match.score_a, 10.0, fp_b, match.score_b, 10.0)
        if cmp >= 0:
            return match.player_a_id
        return match.player_b_id

    async def _bump_leaderboard(self, db: AsyncSession, match: Match) -> None:
        for uid, pts in ((match.player_a_id, match.score_a), (match.player_b_id, match.score_b)):
            if not uid:
                continue
            result = await db.execute(
                select(LeaderboardEntry).where(
                    LeaderboardEntry.tournament_id == match.tournament_id,
                    LeaderboardEntry.user_id == uid,
                )
            )
            entry = result.scalar_one_or_none()
            if not entry:
                entry = LeaderboardEntry(tournament_id=match.tournament_id, user_id=uid, points=0, wins=0)
                db.add(entry)
            entry.points += pts
            if match.winner_id == uid:
                entry.wins += 1

    @staticmethod
    def _qualifiers_per_group(max_players: int) -> int:
        if max_players == 6:
            return 1  # group winners only
        return 2

    @staticmethod
    def _next_stage_after_groups(qualifier_count: int) -> tuple[str, TournamentStatus]:
        if qualifier_count <= 2:
            return "FINAL", TournamentStatus.FINAL
        if qualifier_count <= 4:
            return "SF", TournamentStatus.SF
        if qualifier_count <= 8:
            return "QF", TournamentStatus.QF
        return "R16", TournamentStatus.R16

    async def advance_if_ready(self, db: AsyncSession, tournament: Tournament) -> Tournament:
        result = await db.execute(select(Match).where(Match.tournament_id == tournament.id))
        matches = list(result.scalars().all())
        prev_status = tournament.status

        if tournament.status == TournamentStatus.GROUP_STAGE:
            group_matches = [m for m in matches if m.stage == "GROUP"]
            if group_matches and all(m.status == MatchStatus.COMPLETED for m in group_matches):
                _stage, next_status = await self._build_knockout(db, tournament)
                tournament.status = next_status
        elif tournament.status in (TournamentStatus.R16, TournamentStatus.QF, TournamentStatus.SF):
            stage_map = {
                TournamentStatus.R16: ("R16", "QF", TournamentStatus.QF),
                TournamentStatus.QF: ("QF", "SF", TournamentStatus.SF),
                TournamentStatus.SF: ("SF", "FINAL", TournamentStatus.FINAL),
            }
            current, nxt, next_status = stage_map[tournament.status]
            stage_matches = [m for m in matches if m.stage == current]
            if stage_matches and all(m.status == MatchStatus.COMPLETED for m in stage_matches):
                winners = [m.winner_id for m in sorted(stage_matches, key=lambda x: x.bracket_slot or 0) if m.winner_id]
                for i in range(0, len(winners), 2):
                    if i + 1 >= len(winners):
                        break
                    db.add(
                        Match(
                            tournament_id=tournament.id,
                            stage=nxt,
                            player_a_id=winners[i],
                            player_b_id=winners[i + 1],
                            bracket_slot=i // 2,
                            status=MatchStatus.PENDING,
                        )
                    )
                tournament.status = next_status
        elif tournament.status == TournamentStatus.FINAL:
            finals = [m for m in matches if m.stage == "FINAL"]
            if finals and all(m.status == MatchStatus.COMPLETED for m in finals):
                tournament.status = TournamentStatus.COMPLETED
                from app.services.agent_career import finalize_agent_tournament
                from app.services.tournament_finance import tournament_finance

                await tournament_finance.settle_tournament(db, tournament)
                await finalize_agent_tournament(db, tournament)

        await db.flush()

        if tournament.status != prev_status and tournament.status != TournamentStatus.COMPLETED:
            await self.start_all_pending_matches(db, tournament)

        return tournament

    async def _build_knockout(self, db: AsyncSession, tournament: Tournament) -> tuple[str, TournamentStatus]:
        groups_result = await db.execute(
            select(TournamentGroup).where(TournamentGroup.tournament_id == tournament.id)
        )
        groups = list(groups_result.scalars().all())
        lb_result = await db.execute(
            select(LeaderboardEntry).where(LeaderboardEntry.tournament_id == tournament.id)
        )
        lb = {e.user_id: e for e in lb_result.scalars().all()}
        per_group = self._qualifiers_per_group(tournament.max_players)
        qualifiers: list[str] = []
        for g in sorted(groups, key=lambda x: x.name):
            ranked = sorted(
                g.member_user_ids,
                key=lambda uid: (lb.get(uid).points if uid in lb else 0, lb.get(uid).wins if uid in lb else 0),
                reverse=True,
            )
            qualifiers.extend(ranked[:per_group])

        stage_name, next_status = self._next_stage_after_groups(len(qualifiers))
        pairs: list[tuple[str, str]] = []

        if len(qualifiers) == 2:
            pairs.append((qualifiers[0], qualifiers[1]))
        elif len(qualifiers) == 4:
            # Cross groups when possible: 1A vs 2B, 1B vs 2A
            if len(groups) >= 2 and per_group == 2:
                pairs.append((qualifiers[0], qualifiers[3]))
                pairs.append((qualifiers[2], qualifiers[1]))
            else:
                pairs.append((qualifiers[0], qualifiers[1]))
                pairs.append((qualifiers[2], qualifiers[3]))
        else:
            for i in range(0, len(qualifiers), 4):
                chunk = qualifiers[i : i + 4]
                if len(chunk) >= 4:
                    pairs.append((chunk[0], chunk[3]))
                    pairs.append((chunk[2], chunk[1]))
                elif len(chunk) == 2:
                    pairs.append((chunk[0], chunk[1]))

        for slot, (a, b) in enumerate(pairs):
            db.add(
                Match(
                    tournament_id=tournament.id,
                    stage=stage_name,
                    player_a_id=a,
                    player_b_id=b,
                    bracket_slot=slot,
                    status=MatchStatus.PENDING,
                )
            )
        return stage_name, next_status

    async def get_bracket(self, db: AsyncSession, tournament_id: str) -> dict:
        result = await db.execute(
            select(Match).where(Match.tournament_id == tournament_id).order_by(Match.stage, Match.bracket_slot)
        )
        matches = list(result.scalars().all())
        by_stage: dict[str, list] = {}
        for m in matches:
            rnd = await db.execute(
                select(Round).where(Round.match_id == m.id).order_by(Round.round_number.desc())
            )
            round_row = rnd.scalars().first()
            stage_key = "GROUP" if m.stage in ("GROUP", "GROUP_STAGE") else m.stage
            by_stage.setdefault(stage_key, []).append(
                {
                    "id": m.id,
                    "player_a_id": m.player_a_id,
                    "player_b_id": m.player_b_id,
                    "score_a": m.score_a,
                    "score_b": m.score_b,
                    "winner_id": m.winner_id,
                    "status": m.status.value,
                    "group_name": m.group_name,
                    "bracket_slot": m.bracket_slot,
                    "stage": m.stage,
                    "round_id": round_row.id if round_row else None,
                }
            )
        return by_stage


tournament_director = TournamentDirector()
