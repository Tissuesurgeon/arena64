"""x402 facilitator verify/settle client (Injective EVM)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class X402Error(Exception):
    pass


class FacilitatorClient:
    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.x402_facilitator_url).rstrip("/")

    async def verify(self, payment_payload: str | dict, payment_requirements: dict | None = None) -> dict[str, Any]:
        """POST /verify — returns facilitator verification result."""
        body: dict[str, Any] = {
            "x402Version": 1,
            "paymentPayload": payment_payload if isinstance(payment_payload, dict) else {"payload": payment_payload},
        }
        if payment_requirements:
            body["paymentRequirements"] = payment_requirements

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(f"{self.base_url}/verify", json=body)
                if r.status_code >= 400:
                    # Some facilitators expect a flatter body
                    r2 = await client.post(
                        f"{self.base_url}/verify",
                        json={
                            "paymentHeader": payment_payload if isinstance(payment_payload, str) else None,
                            "paymentPayload": payment_payload,
                            "paymentRequirements": payment_requirements or {},
                        },
                    )
                    if r2.status_code >= 400:
                        raise X402Error(f"Facilitator verify failed: {r.status_code} {r.text[:300]}")
                    data = r2.json()
                else:
                    data = r.json()
        except httpx.HTTPError as exc:
            raise X402Error(f"Facilitator unreachable: {exc}") from exc

        valid = data.get("isValid") if "isValid" in data else data.get("valid")
        if valid is False:
            raise X402Error(data.get("invalidReason") or data.get("error") or "Payment not valid")
        # If facilitator returns opaque success without isValid, treat 2xx as ok
        return {"ok": True, "raw": data, "facilitator": self.base_url}

    async def settle(self, payment_payload: str | dict, payment_requirements: dict | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "x402Version": 1,
            "paymentPayload": payment_payload if isinstance(payment_payload, dict) else {"payload": payment_payload},
        }
        if payment_requirements:
            body["paymentRequirements"] = payment_requirements
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(f"{self.base_url}/settle", json=body)
                if r.status_code >= 400:
                    raise X402Error(f"Facilitator settle failed: {r.status_code} {r.text[:300]}")
                return r.json()
        except httpx.HTTPError as exc:
            raise X402Error(f"Facilitator settle unreachable: {exc}") from exc


async def require_x402_payment(
    proof: str | None,
    *,
    amount_micro: str,
    asset: str | None = None,
) -> dict[str, Any]:
    """
    Enforce x402 verification when configured.

    Returns metadata about how payment was accepted.
    """
    settings = get_settings()
    requirements = {
        "network": settings.x402_network,
        "asset": asset or settings.injective_usdc_address,
        "amount": str(amount_micro),
    }

    if not proof:
        if settings.app_env == "development" and not settings.x402_require_verify:
            return {"ok": True, "mode": "dev_bypass"}
        raise X402Error("X-PAYMENT required")

    if not settings.x402_require_verify:
        # Explicit offline / unit-test mode — still reject obvious empty
        if len(proof.strip()) < 4:
            raise X402Error("Invalid payment proof")
        return {"ok": True, "mode": "verify_disabled", "proof_prefix": proof[:16]}

    client = FacilitatorClient()
    try:
        result = await client.verify(proof, requirements)
        return {"ok": True, "mode": "facilitator_verify", **result}
    except X402Error as exc:
        # Documented fallback when facilitator lacks testnet support
        if settings.injective_network == "testnet" and settings.x402_allow_testnet_fallback:
            logger.warning("x402 facilitator verify failed on testnet, fallback allowed: %s", exc)
            return {
                "ok": True,
                "mode": "testnet_fallback",
                "warning": str(exc),
                "proof_prefix": proof[:16],
            }
        raise
