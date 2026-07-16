"""Tournament entry fee lock / unlock / settle into reward pool."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EntryFeeStatus,
    Tournament,
    TournamentEntry,
    User,
)
from app.services.wallet_service import InsufficientBalance, wallet_service


class TournamentFinanceError(Exception):
    pass


class TournamentFinanceService:
    async def register_entry(
        self,
        db: AsyncSession,
        user: User,
        tournament: Tournament,
    ) -> TournamentEntry:
        fee = int(tournament.entry_fee_usdc_micro or 0)
        entry = TournamentEntry(
            tournament_id=tournament.id,
            user_id=user.id,
            entry_fee_locked_usdc_micro=0,
            fee_status=EntryFeeStatus.NONE.value,
        )

        if fee > 0 and not user.is_system_agent:
            try:
                await wallet_service.lock(
                    db,
                    user,
                    fee,
                    meta={"tournament_id": tournament.id},
                    external_ref=f"entry:{tournament.id}:{user.id}",
                )
            except InsufficientBalance as exc:
                raise TournamentFinanceError(str(exc)) from exc
            entry.entry_fee_locked_usdc_micro = fee
            entry.fee_status = EntryFeeStatus.LOCKED.value
            tournament.reward_pool_usdc_micro = int(tournament.reward_pool_usdc_micro or 0) + fee
        elif fee > 0 and user.is_system_agent:
            # Fillers: house floats the fee into the pool; no user lock.
            tournament.reward_pool_usdc_micro = int(tournament.reward_pool_usdc_micro or 0) + fee
            entry.fee_status = EntryFeeStatus.CONSUMED.value

        db.add(entry)
        await db.flush()
        return entry

    async def cancel_entry(
        self,
        db: AsyncSession,
        user: User,
        tournament: Tournament,
        entry: TournamentEntry,
    ) -> None:
        if entry.fee_status != EntryFeeStatus.LOCKED.value:
            return
        amount = int(entry.entry_fee_locked_usdc_micro or 0)
        if amount > 0:
            await wallet_service.unlock(
                db,
                user,
                amount,
                meta={"tournament_id": tournament.id, "reason": "cancel"},
                external_ref=f"unlock:{tournament.id}:{user.id}",
            )
            tournament.reward_pool_usdc_micro = max(
                0, int(tournament.reward_pool_usdc_micro or 0) - amount
            )
        entry.fee_status = EntryFeeStatus.REFUNDED.value
        entry.entry_fee_locked_usdc_micro = 0
        await db.flush()

    async def settle_tournament(self, db: AsyncSession, tournament: Tournament) -> int:
        """Consume all LOCKED entry fees. Returns number of entries consumed."""
        result = await db.execute(
            select(TournamentEntry).where(TournamentEntry.tournament_id == tournament.id)
        )
        entries = list(result.scalars().all())
        consumed = 0
        for entry in entries:
            if entry.fee_status != EntryFeeStatus.LOCKED.value:
                continue
            amount = int(entry.entry_fee_locked_usdc_micro or 0)
            user = await db.get(User, entry.user_id)
            if user and amount > 0:
                await wallet_service.consume_locked(
                    db,
                    user,
                    amount,
                    meta={"tournament_id": tournament.id},
                    external_ref=f"consume:{tournament.id}:{entry.user_id}",
                )
            entry.fee_status = EntryFeeStatus.CONSUMED.value
            entry.entry_fee_locked_usdc_micro = 0
            consumed += 1
        await db.flush()
        return consumed


tournament_finance = TournamentFinanceService()
