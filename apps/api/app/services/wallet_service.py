"""Arena64 Account ledger — available / locked USDC (custodial, not an on-chain wallet)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Balance, Transaction, TxType, User


class InsufficientBalance(Exception):
    pass


class InsufficientLocked(Exception):
    pass


def usdc_to_micro(amount: float) -> int:
    return int(round(amount * 1_000_000))


def micro_to_usdc(amount_micro: int) -> float:
    return amount_micro / 1_000_000


class WalletService:
    def get_balance(self, user: User) -> dict[str, float | int]:
        bal = user.balance
        available = int(bal.available_usdc_micro or 0) if bal else 0
        locked = int(bal.locked_usdc_micro or 0) if bal else 0
        return {
            "available_usdc_micro": available,
            "locked_usdc_micro": locked,
            "total_usdc_micro": available + locked,
            "available_usdc": micro_to_usdc(available),
            "locked_usdc": micro_to_usdc(locked),
            "usdc": micro_to_usdc(available + locked),
            "usdc_micro": available + locked,
        }

    async def _ensure_balance(self, db: AsyncSession, user: User) -> Balance:
        if user.balance is None:
            bal = Balance(user_id=user.id, available_usdc_micro=0, locked_usdc_micro=0)
            db.add(bal)
            await db.flush()
            user.balance = bal
        return user.balance

    async def _record(
        self,
        db: AsyncSession,
        user: User,
        tx_type: TxType,
        amount_micro: int,
        meta: dict | None = None,
        external_ref: str | None = None,
    ) -> Transaction:
        row = Transaction(
            user_id=user.id,
            tx_type=tx_type,
            amount_usdc_micro=amount_micro,
            meta=meta or {},
            external_ref=external_ref,
        )
        db.add(row)
        await db.flush()
        return row

    async def credit_available(
        self,
        db: AsyncSession,
        user: User,
        amount_micro: int,
        tx_type: TxType,
        meta: dict | None = None,
        external_ref: str | None = None,
    ) -> Balance:
        if amount_micro < 0:
            raise ValueError("amount must be non-negative")
        bal = await self._ensure_balance(db, user)
        bal.available_usdc_micro = int(bal.available_usdc_micro or 0) + amount_micro
        await self._record(db, user, tx_type, amount_micro, meta, external_ref)
        return bal

    async def debit_available(
        self,
        db: AsyncSession,
        user: User,
        amount_micro: int,
        tx_type: TxType,
        meta: dict | None = None,
        external_ref: str | None = None,
    ) -> Balance:
        if amount_micro < 0:
            raise ValueError("amount must be non-negative")
        bal = await self._ensure_balance(db, user)
        available = int(bal.available_usdc_micro or 0)
        if available < amount_micro:
            need = amount_micro / 1_000_000
            have = available / 1_000_000
            raise InsufficientBalance(f"Need {need:g} USDC available, have {have:g} USDC. Deposit testnet USDC first.")
        bal.available_usdc_micro = available - amount_micro
        await self._record(db, user, tx_type, -amount_micro, meta, external_ref)
        return bal

    async def lock(
        self,
        db: AsyncSession,
        user: User,
        amount_micro: int,
        *,
        meta: dict | None = None,
        external_ref: str | None = None,
    ) -> Balance:
        if amount_micro < 0:
            raise ValueError("amount must be non-negative")
        if amount_micro == 0:
            return await self._ensure_balance(db, user)
        bal = await self._ensure_balance(db, user)
        available = int(bal.available_usdc_micro or 0)
        if available < amount_micro:
            raise InsufficientBalance(
                f"Need {amount_micro / 1_000_000:g} USDC available to lock, have {available / 1_000_000:g}."
            )
        bal.available_usdc_micro = available - amount_micro
        bal.locked_usdc_micro = int(bal.locked_usdc_micro or 0) + amount_micro
        await self._record(
            db,
            user,
            TxType.ENTRY_LOCK,
            -amount_micro,
            {**(meta or {}), "locked_delta": amount_micro},
            external_ref,
        )
        return bal

    async def unlock(
        self,
        db: AsyncSession,
        user: User,
        amount_micro: int,
        *,
        meta: dict | None = None,
        external_ref: str | None = None,
    ) -> Balance:
        if amount_micro < 0:
            raise ValueError("amount must be non-negative")
        bal = await self._ensure_balance(db, user)
        locked = int(bal.locked_usdc_micro or 0)
        if locked < amount_micro:
            raise InsufficientLocked(f"Cannot unlock {amount_micro}; locked={locked}")
        bal.locked_usdc_micro = locked - amount_micro
        bal.available_usdc_micro = int(bal.available_usdc_micro or 0) + amount_micro
        await self._record(
            db,
            user,
            TxType.ENTRY_UNLOCK,
            amount_micro,
            {**(meta or {}), "unlocked_delta": amount_micro},
            external_ref,
        )
        return bal

    async def consume_locked(
        self,
        db: AsyncSession,
        user: User,
        amount_micro: int,
        *,
        meta: dict | None = None,
        external_ref: str | None = None,
    ) -> Balance:
        if amount_micro < 0:
            raise ValueError("amount must be non-negative")
        if amount_micro == 0:
            return await self._ensure_balance(db, user)
        bal = await self._ensure_balance(db, user)
        locked = int(bal.locked_usdc_micro or 0)
        if locked < amount_micro:
            raise InsufficientLocked(f"Cannot consume {amount_micro}; locked={locked}")
        bal.locked_usdc_micro = locked - amount_micro
        await self._record(
            db,
            user,
            TxType.ENTRY_CONSUME,
            -amount_micro,
            {**(meta or {}), "consumed_locked": amount_micro},
            external_ref,
        )
        return bal


wallet_service = WalletService()


# Back-compat wrappers used by existing routers during migration
async def credit_usdc(
    db: AsyncSession,
    user: User,
    amount_micro: int,
    tx_type: TxType,
    meta: dict | None = None,
    external_ref: str | None = None,
) -> Balance:
    return await wallet_service.credit_available(db, user, amount_micro, tx_type, meta, external_ref)


async def debit_usdc(
    db: AsyncSession,
    user: User,
    amount_micro: int,
    tx_type: TxType,
    meta: dict | None = None,
    external_ref: str | None = None,
) -> Balance:
    return await wallet_service.debit_available(db, user, amount_micro, tx_type, meta, external_ref)
