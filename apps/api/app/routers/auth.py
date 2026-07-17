import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, get_or_create_user, verify_wallet_signature
from app.core.database import get_db
from app.core.redis_client import cache_get, cache_set
from app.schemas import AuthLoginRequest, NonceResponse, TokenResponse, UserOut
from app.services.wallet_service import wallet_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Fallback when Redis is unavailable (single-process / local)
_nonces: dict[str, str] = {}
_NONCE_TTL_SECONDS = 600
_NONCE_KEY = "arena64:auth:nonce:{wallet}"


def _user_out(user) -> UserOut:
    snap = (
        wallet_service.get_balance(user)
        if user.balance
        else {"available_usdc": 0.0, "locked_usdc": 0.0, "usdc": 0.0}
    )
    return UserOut(
        id=user.id,
        wallet_address=user.wallet_address,
        display_name=user.display_name,
        xp=user.xp,
        is_admin=user.is_admin,
        usdc_balance=float(snap["available_usdc"]),
        available_usdc=float(snap["available_usdc"]),
        locked_usdc=float(snap["locked_usdc"]),
        coach_credits=user.coach_credits.credits if user.coach_credits else 0,
        fair_play_score=user.fair_play.score if user.fair_play else 100.0,
    )


async def _store_nonce(wallet: str, message: str) -> None:
    _nonces[wallet] = message
    await cache_set(_NONCE_KEY.format(wallet=wallet), message, ttl=_NONCE_TTL_SECONDS)


async def _load_nonce(wallet: str) -> str | None:
    cached = await cache_get(_NONCE_KEY.format(wallet=wallet))
    if cached:
        return cached
    return _nonces.get(wallet)


async def _clear_nonce(wallet: str) -> None:
    _nonces.pop(wallet, None)
    try:
        from app.core.redis_client import get_redis

        r = await get_redis()
        await r.delete(_NONCE_KEY.format(wallet=wallet))
    except Exception:
        pass


@router.get("/nonce", response_model=NonceResponse)
async def get_nonce(wallet_address: str) -> NonceResponse:
    nonce = secrets.token_hex(16)
    wallet = wallet_address.lower()
    message = (
        f"Arena64 login\nWallet: {wallet}\nNonce: {nonce}\nIssued: {datetime.utcnow().isoformat()}Z"
    )
    await _store_nonce(wallet, message)
    return NonceResponse(message=message, nonce=nonce)


@router.post("/login", response_model=TokenResponse)
async def login(body: AuthLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    wallet = body.wallet_address.lower()
    expected = await _load_nonce(wallet)
    if not expected or body.message != expected:
        raise HTTPException(status_code=400, detail="Invalid or expired nonce — try Sign in again")

    # Dev bypass: signature "demo" only when APP_ENV=development
    if body.signature == "demo":
        from app.core.config import get_settings

        if get_settings().app_env != "development":
            raise HTTPException(status_code=401, detail="Demo login disabled")
    elif not verify_wallet_signature(wallet, body.message, body.signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    user = await get_or_create_user(db, wallet, body.display_name)
    token = create_access_token(user.id, user.wallet_address)
    await _clear_nonce(wallet)
    return TokenResponse(access_token=token, user=_user_out(user))
