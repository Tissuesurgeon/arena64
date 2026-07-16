"""x402 Payment Service — debit Arena64 Account for premium intelligence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.x402.facilitator import X402Error, require_x402_payment
from app.models import Agent, PremiumTransaction, TxType, User
from app.services.wallet_service import InsufficientBalance, usdc_to_micro, wallet_service

settings = get_settings()


class X402PaymentError(Exception):
    def __init__(self, message: str, *, accepts: dict | None = None):
        super().__init__(message)
        self.accepts = accepts


class X402PaymentService:
    def premium_cost_micro(self) -> int:
        return usdc_to_micro(float(settings.premium_insight_cost_usdc or 0.05))

    async def authorize_premium(
        self,
        db: AsyncSession,
        user: User,
        *,
        service_name: str = "premium_insight",
        tournament_id: str | None = None,
        x_payment: str | None = None,
        agent: Agent | None = None,
    ) -> dict[str, Any]:
        cost = self.premium_cost_micro()
        # Optional on-chain x402 proof when required; ledger debit is always source of truth for agents.
        x402_meta: dict[str, Any] = {"mode": "ledger"}
        if settings.x402_require_verify and x_payment:
            try:
                x402_meta = await require_x402_payment(x_payment, amount_micro=str(cost))
            except X402Error as exc:
                raise X402PaymentError(str(exc)) from exc
        elif settings.x402_require_verify and not x_payment and settings.app_env != "development":
            # Human UI may still send X-PAYMENT; agents use ledger-only in product when flag allows.
            if not getattr(settings, "x402_allow_testnet_fallback", True):
                raise X402PaymentError(
                    "X-PAYMENT required",
                    accepts={
                        "network": settings.x402_network,
                        "asset": settings.injective_usdc_address,
                        "amount": str(cost),
                    },
                )

        # Strategy budget gate
        if agent and agent.strategy:
            budget = float(agent.strategy.premium_insight_budget or 0)
            q = select(PremiumTransaction).where(PremiumTransaction.agent_id == agent.id)
            if tournament_id:
                q = q.where(PremiumTransaction.tournament_id == tournament_id)
            rows = list((await db.execute(q)).scalars().all())
            spent = sum(int(r.cost_usdc_micro or 0) for r in rows) / 1_000_000
            if budget > 0 and spent + (cost / 1_000_000) > budget + 1e-9:
                raise X402PaymentError(
                    f"Premium budget exhausted ({spent:.2f}/{budget:.2f} USDC)."
                )

        try:
            await wallet_service.debit_available(
                db,
                user,
                cost,
                TxType.X402_PREMIUM,
                meta={"service": service_name, "tournament_id": tournament_id},
            )
        except InsufficientBalance as exc:
            raise X402PaymentError(str(exc)) from exc

        agent_id = agent.id if agent else None
        if agent_id is None:
            ag = await db.execute(
                select(Agent).where(Agent.user_id == user.id, Agent.deleted_at.is_(None))
            )
            found = ag.scalar_one_or_none()
            agent_id = found.id if found else None

        db.add(
            PremiumTransaction(
                user_id=user.id,
                agent_id=agent_id,
                service_name=service_name,
                cost_usdc_micro=cost,
                tournament_id=tournament_id,
            )
        )
        await db.flush()
        snap = wallet_service.get_balance(user)
        return {
            "ok": True,
            "cost_usdc": cost / 1_000_000,
            "x402": x402_meta,
            **snap,
        }


x402_payment = X402PaymentService()
