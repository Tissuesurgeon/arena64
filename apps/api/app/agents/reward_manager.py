from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    LeaderboardEntry,
    Reward,
    Tournament,
    TournamentHistory,
    TournamentStatus,
    TxType,
    User,
)
from app.services.ledger import credit_usdc
from app.services.scoring import distribute_pool


class RewardManager:
    """Calculate and distribute tournament rewards to internal balances."""

    async def finalize(self, db: AsyncSession, tournament: Tournament) -> list[Reward]:
        if tournament.status != TournamentStatus.COMPLETED:
            raise ValueError("Tournament not completed")

        existing = await db.execute(select(Reward).where(Reward.tournament_id == tournament.id))
        already = list(existing.scalars().all())
        if already:
            return already

        lb = await db.execute(
            select(LeaderboardEntry)
            .where(LeaderboardEntry.tournament_id == tournament.id)
            .order_by(LeaderboardEntry.wins.desc(), LeaderboardEntry.points.desc())
        )
        ranked = list(lb.scalars().all())
        for i, entry in enumerate(ranked, start=1):
            entry.placement = i

        splits = distribute_pool(tournament.reward_pool_usdc_micro, tournament.platform_fee_bps)
        rewards: list[Reward] = []
        xp_table = {1: 500, 2: 300, 3: 200, 4: 100}

        for place, amount in splits.items():
            if place > len(ranked):
                break
            entry = ranked[place - 1]
            reward = Reward(
                tournament_id=tournament.id,
                user_id=entry.user_id,
                placement=place,
                amount_usdc_micro=amount,
                xp_awarded=xp_table.get(place, 50),
                claimed=False,
            )
            db.add(reward)
            rewards.append(reward)
            db.add(
                TournamentHistory(
                    tournament_id=tournament.id,
                    user_id=entry.user_id,
                    placement=place,
                    points=entry.points,
                    summary={"wins": entry.wins},
                )
            )

        await db.flush()
        return rewards

    async def claim(self, db: AsyncSession, user: User, reward: Reward) -> Reward:
        if reward.user_id != user.id:
            raise PermissionError("Not your reward")
        if reward.claimed:
            return reward
        if reward.amount_usdc_micro > 0:
            await credit_usdc(
                db,
                user,
                reward.amount_usdc_micro,
                TxType.REWARD,
                meta={"reward_id": reward.id, "placement": reward.placement},
            )
        user.xp += reward.xp_awarded
        reward.claimed = True
        await db.flush()
        return reward


reward_manager = RewardManager()