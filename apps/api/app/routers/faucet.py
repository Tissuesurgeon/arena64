"""INJ testnet faucet — one claim per connected wallet."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.models import User
from app.services.inj_faucet_service import InjFaucetError, inj_faucet_service

router = APIRouter(prefix="/faucet", tags=["faucet"])


@router.get("/inj/status")
async def inj_faucet_status(user: User = Depends(get_current_user)):
    try:
        return await inj_faucet_service.status(user.wallet_address)
    except InjFaucetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/inj/claim")
async def inj_faucet_claim(user: User = Depends(get_current_user)):
    try:
        return await inj_faucet_service.claim_for(user.wallet_address)
    except InjFaucetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
