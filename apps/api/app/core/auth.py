from datetime import datetime, timedelta
from typing import Optional

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Balance, CoachCredits, FairPlayScore, User

security = HTTPBearer(auto_error=False)
settings = get_settings()


def create_access_token(user_id: str, wallet: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "wallet": wallet.lower(), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def verify_wallet_signature(wallet: str, message: str, signature: str) -> bool:
    """Verify EIP-191 personal_sign (MetaMask / wagmi signMessage)."""
    try:
        sig = signature.strip()
        if not sig.startswith("0x"):
            sig = "0x" + sig
        recovered = Account.recover_message(encode_defunct(text=message), signature=sig)
        return recovered.lower() == wallet.lower()
    except Exception:
        return False


async def ensure_user_profile(db: AsyncSession, user: User) -> User:
    # Avoid lazy-loading relationships in async context (MissingGreenlet).
    bal = await db.scalar(select(Balance).where(Balance.user_id == user.id))
    if bal is None:
        db.add(Balance(user_id=user.id, available_usdc_micro=0, locked_usdc_micro=0))
    credits = await db.scalar(select(CoachCredits).where(CoachCredits.user_id == user.id))
    if credits is None:
        db.add(CoachCredits(user_id=user.id, credits=0))
    fp = await db.scalar(select(FairPlayScore).where(FairPlayScore.user_id == user.id))
    if fp is None:
        db.add(FairPlayScore(user_id=user.id, score=100.0, flags={}))
    await db.flush()
    return user


async def get_or_create_user(db: AsyncSession, wallet: str, display_name: Optional[str] = None) -> User:
    wallet = wallet.lower()
    result = await db.execute(
        select(User)
        .options(selectinload(User.balance), selectinload(User.coach_credits), selectinload(User.fair_play))
        .where(User.wallet_address == wallet)
    )
    user = result.scalar_one_or_none()
    if user:
        await ensure_user_profile(db, user)
        return user

    is_admin = wallet in settings.admin_wallet_set
    if settings.app_env == "development" and not settings.admin_wallet_set:
        # First-ish demo wallets can administer locally
        is_admin = wallet.startswith("0xdemo") or is_admin
    user = User(
        wallet_address=wallet,
        display_name=display_name or f"Player-{wallet[-4:].upper()}",
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    db.add(Balance(user_id=user.id, available_usdc_micro=0, locked_usdc_micro=0))
    db.add(CoachCredits(user_id=user.id, credits=0))
    db.add(FairPlayScore(user_id=user.id, score=100.0, flags={}))
    await db.flush()
    result = await db.execute(
        select(User)
        .options(selectinload(User.balance), selectinload(User.coach_credits), selectinload(User.fair_play))
        .where(User.id == user.id)
    )
    return result.scalar_one()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    result = await db.execute(
        select(User)
        .options(selectinload(User.balance), selectinload(User.coach_credits), selectinload(User.fair_play))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def require_service_key(x_service_key: Optional[str] = None) -> None:
    if x_service_key != settings.service_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service key")