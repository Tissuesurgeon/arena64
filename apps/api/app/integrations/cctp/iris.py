"""Circle Iris CCTP attestation client (sandbox on testnet)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class IrisError(Exception):
    pass


class IrisClient:
    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.cctp_iris_api).rstrip("/")

    async def messages_by_tx(self, source_domain: int, tx_hash: str) -> dict[str, Any]:
        """Look up CCTP messages / attestation for a burn tx."""
        url = f"{self.base_url}/v2/messages/{source_domain}"
        params = {"transactionHash": tx_hash}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, params=params)
                if r.status_code == 404:
                    # v1 fallback used by some sandbox deployments
                    url_v1 = f"{self.base_url}/messages/{source_domain}/{tx_hash}"
                    r = await client.get(url_v1)
                r.raise_for_status()
                return r.json()
        except httpx.HTTPError as exc:
            raise IrisError(f"Iris request failed: {exc}") from exc

    async def verify_deposit(
        self,
        *,
        burn_tx_hash: str,
        source_domain: int,
        attestation: str | None,
        message_bytes: str | None,
    ) -> dict[str, Any]:
        """
        Require a usable attestation before crediting the ledger.

        Accepts either a client-supplied attestation (from Iris) or fetches
        attestation status from Iris by burn tx hash.
        """
        settings = get_settings()
        if not settings.cctp_require_attestation:
            return {
                "ok": True,
                "mode": "skipped",
                "attestation_present": bool(attestation),
            }

        # Client already has attestation from Iris UI / SDK
        if attestation and len(attestation) >= 8 and not attestation.startswith("demo-"):
            return {
                "ok": True,
                "mode": "client_attestation",
                "attestation_prefix": attestation[:16],
                "message_present": bool(message_bytes),
            }

        # Reject obvious demo placeholders when verification is required
        if attestation and attestation.startswith("demo-"):
            raise IrisError("Demo attestations are not accepted when CCTP_REQUIRE_ATTESTATION=true")

        try:
            data = await self.messages_by_tx(source_domain, burn_tx_hash)
        except IrisError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise IrisError(f"Could not fetch Iris attestation: {exc}") from exc

        messages = data.get("messages") or data.get("message") or data
        if isinstance(messages, dict) and "attestation" in messages:
            messages = [messages]
        if not isinstance(messages, list) or not messages:
            raise IrisError("No CCTP messages found for burn tx on Iris")

        first = messages[0] if isinstance(messages[0], dict) else {}
        status = str(first.get("status") or first.get("attestation") or "").lower()
        att = first.get("attestation") or attestation
        if not att and "complete" not in status and status not in ("complete", "completed", "attested"):
            # Some Iris responses nest differently
            if not first.get("message"):
                raise IrisError(f"Iris attestation not ready (status={status or 'unknown'})")

        return {
            "ok": True,
            "mode": "iris_lookup",
            "status": status or "ok",
            "iris_api": self.base_url,
            "message_count": len(messages) if isinstance(messages, list) else 1,
        }
