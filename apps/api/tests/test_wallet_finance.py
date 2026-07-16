"""Unit tests for Arena64 Account lock / settle / premium ledger."""

import pytest

from app.models import Balance, EntryFeeStatus, Tournament, TournamentEntry, TxType, User
from app.services.tournament_finance import TournamentFinanceError, tournament_finance
from app.services.wallet_service import InsufficientBalance, wallet_service
from app.services.x402_payment import X402PaymentError, x402_payment


class _FakeResult:
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return self._one


class FakeDB:
    def __init__(self):
        self.added = []
        self._premium = []

    def add(self, obj):
        self.added.append(obj)
        from app.models import PremiumTransaction

        if isinstance(obj, PremiumTransaction):
            self._premium.append(obj)

    async def flush(self):
        return None

    async def execute(self, stmt):  # noqa: ARG002
        return _FakeResult(rows=self._premium)

    async def get(self, model, pk):  # noqa: ARG002
        return None


def _user(available: int = 10_000_000, locked: int = 0) -> User:
    u = User(id="u1", wallet_address="0xabc")
    u.balance = Balance(
        user_id="u1",
        available_usdc_micro=available,
        locked_usdc_micro=locked,
    )
    u.is_system_agent = False
    return u


@pytest.mark.asyncio
async def test_lock_unlock_consume_invariants():
    db = FakeDB()
    user = _user(10_000_000)
    await wallet_service.lock(db, user, 5_000_000, meta={"t": "1"})
    assert user.balance.available_usdc_micro == 5_000_000
    assert user.balance.locked_usdc_micro == 5_000_000
    await wallet_service.unlock(db, user, 2_000_000)
    assert user.balance.available_usdc_micro == 7_000_000
    assert user.balance.locked_usdc_micro == 3_000_000
    await wallet_service.consume_locked(db, user, 3_000_000)
    assert user.balance.available_usdc_micro == 7_000_000
    assert user.balance.locked_usdc_micro == 0


@pytest.mark.asyncio
async def test_lock_rejects_insufficient_available():
    db = FakeDB()
    user = _user(1_000_000)
    with pytest.raises(InsufficientBalance):
        await wallet_service.lock(db, user, 5_000_000)


@pytest.mark.asyncio
async def test_register_entry_locks_and_bumps_pool():
    db = FakeDB()
    user = _user(10_000_000)
    t = Tournament(id="t1", name="Cup", entry_fee_usdc_micro=5_000_000, reward_pool_usdc_micro=0)
    entry = await tournament_finance.register_entry(db, user, t)
    assert entry.fee_status == EntryFeeStatus.LOCKED.value
    assert entry.entry_fee_locked_usdc_micro == 5_000_000
    assert t.reward_pool_usdc_micro == 5_000_000
    assert user.balance.available_usdc_micro == 5_000_000
    assert user.balance.locked_usdc_micro == 5_000_000


@pytest.mark.asyncio
async def test_register_entry_insufficient():
    db = FakeDB()
    user = _user(100_000)
    t = Tournament(id="t1", name="Cup", entry_fee_usdc_micro=5_000_000, reward_pool_usdc_micro=0)
    with pytest.raises(TournamentFinanceError):
        await tournament_finance.register_entry(db, user, t)


@pytest.mark.asyncio
async def test_settle_consumes_locked(monkeypatch):
    db = FakeDB()
    user = _user(0, locked=5_000_000)
    t = Tournament(id="t1", name="Cup", entry_fee_usdc_micro=5_000_000, reward_pool_usdc_micro=5_000_000)
    entry = TournamentEntry(
        tournament_id="t1",
        user_id="u1",
        entry_fee_locked_usdc_micro=5_000_000,
        fee_status=EntryFeeStatus.LOCKED.value,
    )

    async def fake_execute(stmt):  # noqa: ARG001
        return _FakeResult(rows=[entry])

    async def fake_get(model, pk):  # noqa: ARG001
        return user

    db.execute = fake_execute  # type: ignore[method-assign]
    db.get = fake_get  # type: ignore[method-assign]
    n = await tournament_finance.settle_tournament(db, t)
    assert n == 1
    assert entry.fee_status == EntryFeeStatus.CONSUMED.value
    assert user.balance.locked_usdc_micro == 0


@pytest.mark.asyncio
async def test_premium_debits_available(monkeypatch):
    db = FakeDB()
    user = _user(1_000_000)
    monkeypatch.setattr(
        "app.services.x402_payment.settings.x402_require_verify",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.x402_payment.settings.premium_insight_cost_usdc",
        0.05,
        raising=False,
    )
    pay = await x402_payment.authorize_premium(db, user, service_name="premium_insight")
    assert pay["ok"] is True
    assert user.balance.available_usdc_micro == 950_000


@pytest.mark.asyncio
async def test_balance_snapshot_available_locked():
    user = _user(7_000_000, locked=3_000_000)
    snap = wallet_service.get_balance(user)
    assert snap["available_usdc"] == 7.0
    assert snap["locked_usdc"] == 3.0
    assert snap["usdc"] == 10.0


@pytest.mark.asyncio
async def test_withdraw_debit_path():
    db = FakeDB()
    user = _user(2_000_000)
    await wallet_service.debit_available(db, user, 1_000_000, TxType.WITHDRAW, meta={"to": "0x"})
    assert user.balance.available_usdc_micro == 1_000_000
    with pytest.raises(InsufficientBalance):
        await wallet_service.debit_available(db, user, 5_000_000, TxType.WITHDRAW)
