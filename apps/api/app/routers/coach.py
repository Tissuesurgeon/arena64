from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.ai_coach import COACH_ABILITIES, COACH_PACKS, InsufficientCredits, ai_coach
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.x402.facilitator import X402Error, require_x402_payment
from app.models import Transaction, TxType, User
from app.schemas import CoachAbilityRequest, CoachPackPurchase
from app.services.ledger import InsufficientBalance, debit_usdc, micro_to_usdc

router = APIRouter(prefix="/coach", tags=["coach"])
settings = get_settings()


@router.get("/packs")
async def list_packs():
    return {
        "packs": [
            {
                "id": k,
                "label": v["label"],
                "credits": v["credits"],
                "price_usdc": micro_to_usdc(v["price_usdc_micro"]),
                "x402": True,
            }
            for k, v in COACH_PACKS.items()
        ],
        "abilities": COACH_ABILITIES,
        "x402_network": settings.x402_network,
        "facilitator": settings.x402_facilitator_url,
        "x402_require_verify": settings.x402_require_verify,
    }


@router.post("/packs/purchase")
async def purchase_pack(
    body: CoachPackPurchase,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
):
    """
    Purchase coach credits. Prefers verified x402 payment (X-PAYMENT / payment_proof).
    Falls back to internal USDC balance debit for testnet continuity.
    """
    pack = COACH_PACKS.get(body.pack)
    if not pack:
        raise HTTPException(status_code=400, detail="Unknown pack")

    proof = body.payment_proof or x_payment
    paid_via = "internal_balance"
    x402_meta: dict = {}

    if proof:
        try:
            x402_meta = await require_x402_payment(
                proof,
                amount_micro=str(pack["price_usdc_micro"]),
            )
        except X402Error as exc:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": str(exc),
                    "x402": {
                        "accepts": [
                            {
                                "network": settings.x402_network,
                                "asset": settings.injective_usdc_address,
                                "amount": str(pack["price_usdc_micro"]),
                            }
                        ],
                        "facilitator": settings.x402_facilitator_url,
                    },
                },
            ) from exc
        paid_via = f"x402:{x402_meta.get('mode', 'verified')}"
        db.add(
            Transaction(
                user_id=user.id,
                tx_type=TxType.COACH_PACK,
                amount_usdc_micro=0,
                meta={"pack": body.pack, "credits": pack["credits"], "x402": x402_meta, "proof": proof[:200]},
                external_ref=f"x402:{proof[:64]}",
            )
        )
    else:
        try:
            await debit_usdc(
                db,
                user,
                pack["price_usdc_micro"],
                TxType.COACH_PACK,
                meta={"pack": body.pack, "credits": pack["credits"]},
            )
        except InsufficientBalance as exc:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": str(exc),
                    "x402": {
                        "accepts": [
                            {
                                "network": settings.x402_network,
                                "asset": settings.injective_usdc_address,
                                "amount": str(pack["price_usdc_micro"]),
                            }
                        ],
                        "facilitator": settings.x402_facilitator_url,
                    },
                },
            ) from exc

    credits = await ai_coach.add_credits(db, user, pack["credits"])
    return {
        "pack": body.pack,
        "credits_added": pack["credits"],
        "credits_total": credits.credits,
        "paid_via": paid_via,
        "x402": x402_meta or None,
    }


@router.post("/ability")
async def use_ability(
    body: CoachAbilityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await ai_coach.spend(db, user, body.ability)
    except InsufficientCredits as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    extra = {}
    if body.ability == "remove_two" and body.question_id:
        extra["remove_option_ids"] = await ai_coach.remove_two_wrong(db, body.question_id)
    if body.ability == "add_five_seconds":
        extra["extra_seconds"] = 5
    if body.ability == "replay_memory":
        extra["replay"] = True
    if body.ability == "round_review":
        extra["review"] = {"tip": "Trust first instincts on historical WC facts; pace beats overthinking."}

    return {**result, **extra}


@router.post("/report")
async def coach_report(
    user: User = Depends(get_current_user),
    x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
):
    """Premium x402-gated performance report."""
    try:
        meta = await require_x402_payment(x_payment, amount_micro="10000")
    except X402Error as exc:
        if settings.app_env == "development" and not x_payment and not settings.x402_require_verify:
            meta = {"ok": True, "mode": "dev_bypass"}
        else:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": str(exc),
                    "accepts": [
                        {
                            "network": settings.x402_network,
                            "asset": settings.injective_usdc_address,
                            "amount": "10000",
                        }
                    ],
                    "facilitator": settings.x402_facilitator_url,
                },
            ) from exc
    return {
        "player_id": user.id,
        "fair_play": user.fair_play.score if user.fair_play else 100,
        "xp": user.xp,
        "summary": "Strong pace on football MCQs; review memory retention under 10s windows.",
        "x402": meta,
    }
