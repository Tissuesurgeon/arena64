import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.injective.networks import get_profile
from app.models import Transaction, TxType, User
from app.schemas import CCTPDepositRequest, DemoFaucetRequest
from app.services.treasury_service import TreasuryError, treasury_service
from app.services.wallet_service import micro_to_usdc, usdc_to_micro, wallet_service

router = APIRouter(prefix="/wallet", tags=["wallet"])
logger = logging.getLogger(__name__)


def _settings():
    return get_settings()


class OnchainDepositRequest(BaseModel):
    tx_hash: str = Field(..., min_length=66, max_length=66)


class WithdrawRequest(BaseModel):
    amount_usdc: float = Field(..., gt=0)
    to_address: str | None = None


@router.get("/balance")
async def balance(user: User = Depends(get_current_user)):
    snap = wallet_service.get_balance(user)
    return {
        **snap,
        "available_usdc": snap["available_usdc"],
        "locked_usdc": snap["locked_usdc"],
        "usdc": snap["available_usdc"],  # spendable / primary chip
        "usdc_total": snap["usdc"],
        "coach_credits": user.coach_credits.credits if user.coach_credits else 0,
        "xp": user.xp,
    }


@router.get("/transactions")
async def transactions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.desc()).limit(50)
    )
    rows = result.scalars().all()
    return [
        {
            "id": t.id,
            "type": t.tx_type.value,
            "amount_usdc": micro_to_usdc(t.amount_usdc_micro),
            "meta": t.meta,
            "external_ref": t.external_ref,
            "created_at": t.created_at.isoformat(),
        }
        for t in rows
    ]


@router.post("/deposit")
async def onchain_deposit(
    body: OnchainDepositRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Credit Arena64 Account after verifying USDC transfer to treasury."""
    logger.info("deposit credit requested wallet=%s tx=%s", user.wallet_address, body.tx_hash)
    try:
        result = await treasury_service.verify_and_credit_deposit(db, user, body.tx_hash)
        logger.info(
            "deposit credited wallet=%s tx=%s amount=%s",
            user.wallet_address,
            body.tx_hash,
            result.get("credited_usdc"),
        )
        return result
    except TreasuryError as exc:
        logger.warning("deposit credit failed wallet=%s tx=%s err=%s", user.wallet_address, body.tx_hash, exc)
        code = 409 if "already" in str(exc).lower() else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/deposit/sync")
async def sync_deposits(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Scan recent on-chain transfers to treasury and credit any missing ones."""
    logger.info("deposit sync requested wallet=%s", user.wallet_address)
    try:
        result = await treasury_service.sync_uncredited_deposits(db, user)
        logger.info(
            "deposit sync wallet=%s credited=%s amount=%s",
            user.wallet_address,
            result.get("credited_count"),
            result.get("credited_usdc"),
        )
        return result
    except TreasuryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cctp/deposit")
async def cctp_deposit(
    body: CCTPDepositRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await treasury_service.verify_and_credit_cctp(
            db,
            user,
            burn_tx_hash=body.burn_tx_hash,
            source_domain=body.source_domain,
            amount_usdc=body.amount_usdc,
            attestation=body.attestation,
            message_bytes=body.message_bytes,
        )
    except TreasuryError as exc:
        code = 409 if "already" in str(exc).lower() else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/withdraw")
async def withdraw(
    body: WithdrawRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await treasury_service.withdraw(db, user, body.amount_usdc, body.to_address)
    except TreasuryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/faucet")
async def demo_faucet(
    body: DemoFaucetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = _settings()
    if not settings.demo_faucet_enabled or settings.is_mainnet:
        raise HTTPException(
            status_code=403,
            detail="Faucet disabled. Deposit Injective testnet USDC to the Arena64 treasury.",
        )
    amount = body.amount_usdc or settings.demo_faucet_amount_usdc
    await wallet_service.credit_available(db, user, usdc_to_micro(amount), TxType.DEMO_FAUCET, meta={"demo": True})
    snap = wallet_service.get_balance(user)
    return {"usdc": snap["available_usdc"], **snap}


@router.get("/onchain-usdc")
async def onchain_usdc(user: User = Depends(get_current_user)):
    """Connected-wallet USDC on Injective (server RPC) — used when the browser RPC fails."""
    from app.integrations.injective.usdc_deposit import DepositError, UsdcDepositVerifier

    settings = _settings()
    try:
        raw = await UsdcDepositVerifier().balance_of(user.wallet_address)
    except DepositError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("onchain-usdc failed wallet=%s err=%s", user.wallet_address, exc)
        raise HTTPException(status_code=502, detail="Could not read on-chain USDC balance") from exc
    return {
        "wallet_address": user.wallet_address,
        "usdc_address": settings.injective_usdc_address,
        "balance_usdc": raw / 1_000_000,
        "balance_micro": str(raw),
        "chain_id": settings.injective_evm_chain_id,
    }


@router.get("/cctp/config")
async def cctp_config():
    settings = _settings()
    profile = get_profile(settings.injective_network)
    return {
        "network": settings.injective_network,
        "chain_id": settings.injective_evm_chain_id,
        "usdc_address": settings.injective_usdc_address,
        "treasury_address": settings.arena64_treasury_address or None,
        "iris_api": settings.cctp_iris_api,
        "cctp_domain": settings.cctp_domain,
        "rpc_url": settings.injective_rpc_url,
        "explorer_url": profile.explorer_url,
        "require_attestation": settings.cctp_require_attestation,
        "faucet_enabled": bool(settings.demo_faucet_enabled) and not settings.is_mainnet,
        "withdraw_enabled": bool(settings.arena64_treasury_private_key),
        "x402_network": settings.x402_network,
        "x402_require_verify": settings.x402_require_verify,
        "premium_insight_cost_usdc": settings.premium_insight_cost_usdc,
        "deposit_flow": [
            "get_testnet_usdc",
            "transfer_to_treasury",
            "POST /api/wallet/deposit → Arena64 Account Available",
        ],
        "external_faucets": {
            "circle": "https://faucet.circle.com/",
            "injective": "https://testnet.faucet.injective.network/",
        },
        "mainnet_gate": "Pass testnet checklist before INJECTIVE_NETWORK=mainnet",
    }
