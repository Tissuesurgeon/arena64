from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.fair_play import fair_play_agent
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import User
from app.routers.auth import _user_out
from app.schemas import FairPlayEvent, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.post("/me/fair-play")
async def fair_play_event(
    body: FairPlayEvent,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fp = await fair_play_agent.record_event(db, user, body.event, body.meta)
    return {"score": fp.score, "flags": fp.flags}