"""Treasury — on-chain USDC in/out; credits Arena64 Account available balance."""

from __future__ import annotations

import logging
from typing import Any

from eth_account import Account
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.cctp.iris import IrisClient, IrisError
from app.integrations.injective.usdc_deposit import DepositError, UsdcDepositVerifier
from app.models import Transaction, TxType, User
from app.services.wallet_service import InsufficientBalance, micro_to_usdc, usdc_to_micro, wallet_service

logger = logging.getLogger(__name__)

# Minimal ERC-20 transfer ABI encoding
_TRANSFER_SELECTOR = bytes.fromhex("a9059cbb")


class TreasuryError(Exception):
    pass


def _encode_transfer(to_address: str, amount_micro: int) -> bytes:
    to = to_address.lower().replace("0x", "").zfill(64)
    amt = format(amount_micro, "064x")
    return _TRANSFER_SELECTOR + bytes.fromhex(to + amt)


def _settings():
    return get_settings()


class TreasuryService:
    async def verify_and_credit_deposit(
        self,
        db: AsyncSession,
        user: User,
        tx_hash: str,
    ) -> dict[str, Any]:
        submitted = tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}"
        submitted = submitted.lower()
        existing = await db.execute(select(Transaction).where(Transaction.external_ref == submitted))
        if existing.scalar_one_or_none():
            raise TreasuryError("Deposit already recorded")

        verifier = UsdcDepositVerifier()
        verified: dict[str, Any] | None = None
        try:
            verified = await verifier.verify_transfer(
                tx_hash=submitted,
                expected_from=user.wallet_address,
            )
        except DepositError as exc:
            msg = str(exc).lower()
            recoverable = any(
                s in msg for s in ("not found", "not yet mined", "could not fetch", "no usdc transfer")
            )
            if not recoverable:
                raise TreasuryError(str(exc)) from exc
            logger.warning(
                "deposit hash miss wallet=%s submitted=%s (%s); scanning recent transfers",
                user.wallet_address,
                submitted,
                exc,
            )
            candidates = await verifier.list_recent_transfers(user.wallet_address)
            for cand in candidates:
                exists = await db.scalar(
                    select(Transaction.id).where(Transaction.external_ref == cand["tx_hash"])
                )
                if exists:
                    continue
                verified = {**cand, "submitted_tx_hash": submitted}
                break
            if verified is None:
                if candidates:
                    raise TreasuryError("Deposit already recorded") from exc
                raise TreasuryError(
                    "No USDC transfer to the Arena64 treasury was found for this wallet. "
                    "MetaMask on Injective often returns a hash that never mined — your USDC "
                    "is probably still in your wallet. Try Deposit again, or paste a successful "
                    "Blockscout transfer hash and use Verify & credit."
                ) from exc

        real_hash = str(verified["tx_hash"]).lower()
        if real_hash != submitted:
            exists_real = await db.scalar(select(Transaction.id).where(Transaction.external_ref == real_hash))
            if exists_real:
                raise TreasuryError("Deposit already recorded")
            logger.info("deposit recovered submitted=%s real=%s", submitted, real_hash)

        await wallet_service.credit_available(
            db,
            user,
            verified["amount_usdc_micro"],
            TxType.ONCHAIN_DEPOSIT,
            meta=verified,
            external_ref=real_hash,
        )
        snap = wallet_service.get_balance(user)
        return {
            "status": "credited",
            "credited_usdc": micro_to_usdc(verified["amount_usdc_micro"]),
            "tx_hash": real_hash,
            "submitted_tx_hash": submitted,
            **snap,
        }

    async def sync_uncredited_deposits(self, db: AsyncSession, user: User) -> dict[str, Any]:
        """Credit any recent on-chain wallet→treasury USDC transfers not yet in the ledger."""
        verifier = UsdcDepositVerifier()
        if not verifier.treasury:
            raise TreasuryError("ARENA64_TREASURY_ADDRESS not configured")
        candidates = await verifier.list_recent_transfers(user.wallet_address)
        credited: list[dict[str, Any]] = []
        total_micro = 0
        for cand in candidates:
            tx_hash = str(cand["tx_hash"]).lower()
            exists = await db.scalar(select(Transaction.id).where(Transaction.external_ref == tx_hash))
            if exists:
                continue
            amount = int(cand["amount_usdc_micro"])
            await wallet_service.credit_available(
                db,
                user,
                amount,
                TxType.ONCHAIN_DEPOSIT,
                meta={**cand, "synced": True},
                external_ref=tx_hash,
            )
            total_micro += amount
            credited.append(
                {
                    "tx_hash": tx_hash,
                    "credited_usdc": micro_to_usdc(amount),
                }
            )
        snap = wallet_service.get_balance(user)
        return {
            "status": "synced",
            "credited_count": len(credited),
            "credited_usdc": micro_to_usdc(total_micro),
            "deposits": credited,
            **snap,
        }

    async def verify_and_credit_cctp(
        self,
        db: AsyncSession,
        user: User,
        *,
        burn_tx_hash: str,
        source_domain: int,
        amount_usdc: float,
        attestation: str | None = None,
        message_bytes: str | None = None,
    ) -> dict[str, Any]:
        if amount_usdc <= 0:
            raise TreasuryError("Invalid amount")
        existing = await db.execute(select(Transaction).where(Transaction.external_ref == burn_tx_hash))
        if existing.scalar_one_or_none():
            raise TreasuryError("Deposit already recorded")
        try:
            verification = await IrisClient().verify_deposit(
                burn_tx_hash=burn_tx_hash,
                source_domain=source_domain,
                attestation=attestation,
                message_bytes=message_bytes,
            )
        except IrisError as exc:
            raise TreasuryError(str(exc)) from exc
        amount_micro = usdc_to_micro(amount_usdc)
        await wallet_service.credit_available(
            db,
            user,
            amount_micro,
            TxType.CCTP_DEPOSIT,
            meta={
                "source_domain": source_domain,
                "attestation_present": bool(attestation),
                "network": _settings().injective_network,
                "iris": verification,
            },
            external_ref=burn_tx_hash,
        )
        snap = wallet_service.get_balance(user)
        return {
            "status": "credited",
            "cctp": {
                "burn_tx_hash": burn_tx_hash,
                "iris_api": _settings().cctp_iris_api,
                "verification": verification,
            },
            **snap,
        }

    async def withdraw(
        self,
        db: AsyncSession,
        user: User,
        amount_usdc: float,
        to_address: str | None = None,
    ) -> dict[str, Any]:
        settings = _settings()
        if amount_usdc <= 0:
            raise TreasuryError("Invalid amount")
        to = (to_address or user.wallet_address or "").strip()
        if not to.startswith("0x") or len(to) != 42:
            raise TreasuryError("Invalid destination address")
        amount_micro = usdc_to_micro(amount_usdc)
        pk = (settings.arena64_treasury_private_key or "").strip()
        if not pk:
            raise TreasuryError(
                "Withdrawals require ARENA64_TREASURY_PRIVATE_KEY for the treasury hot wallet."
            )
        usdc = settings.injective_usdc_address
        if not usdc:
            raise TreasuryError("USDC contract not configured")

        try:
            await wallet_service.debit_available(
                db,
                user,
                amount_micro,
                TxType.WITHDRAW,
                meta={"to": to.lower(), "pending": True},
            )
        except InsufficientBalance as exc:
            raise TreasuryError(str(exc)) from exc

        try:
            tx_hash = await self._send_usdc(to, amount_micro)
        except Exception as exc:
            logger.exception("Treasury withdraw send failed; refunding available")
            await wallet_service.credit_available(
                db,
                user,
                amount_micro,
                TxType.REFUND,
                meta={"reason": "withdraw_send_failed", "error": str(exc), "to": to.lower()},
            )
            raise TreasuryError(f"On-chain send failed; balance restored. {exc}") from exc

        await wallet_service._record(  # noqa: SLF001
            db,
            user,
            TxType.WITHDRAW,
            0,
            meta={"to": to.lower(), "confirmed": True, "amount_usdc_micro": amount_micro},
            external_ref=tx_hash,
        )
        snap = wallet_service.get_balance(user)
        return {"status": "sent", "tx_hash": tx_hash, "to": to.lower(), "amount_usdc": amount_usdc, **snap}

    async def _send_usdc(self, to_address: str, amount_micro: int) -> str:
        import httpx

        settings = _settings()
        pk = settings.arena64_treasury_private_key.strip()
        if not pk.startswith("0x"):
            pk = "0x" + pk
        account = Account.from_key(pk)
        treasury = (settings.arena64_treasury_address or account.address).lower()
        if account.address.lower() != treasury and settings.arena64_treasury_address:
            raise TreasuryError(
                "Treasury private key does not match ARENA64_TREASURY_ADDRESS — "
                "set the key for the same hot wallet that receives deposits."
            )

        rpc = settings.injective_rpc_url
        usdc = settings.injective_usdc_address
        data = "0x" + _encode_transfer(to_address, amount_micro).hex()

        async with httpx.AsyncClient(timeout=45.0) as client:
            nonce_res = await client.post(
                rpc,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getTransactionCount",
                    "params": [account.address, "pending"],
                },
            )
            nonce_hex = nonce_res.json().get("result")
            if not nonce_hex:
                raise TreasuryError(f"RPC nonce error: {nonce_res.text}")

            gas_price_res = await client.post(
                rpc,
                json={"jsonrpc": "2.0", "id": 2, "method": "eth_gasPrice", "params": []},
            )
            gas_price = int(gas_price_res.json().get("result") or "0x3b9aca00", 16)

            chain_id = int(settings.injective_evm_chain_id or 1439)
            signed = account.sign_transaction(
                {
                    "nonce": int(nonce_hex, 16),
                    "gasPrice": gas_price,
                    "gas": 120_000,
                    "to": usdc,
                    "value": 0,
                    "data": data,
                    "chainId": chain_id,
                }
            )
            raw_bytes = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
            raw = raw_bytes.hex() if hasattr(raw_bytes, "hex") else str(raw_bytes)
            if not raw.startswith("0x"):
                raw = "0x" + raw
            send = await client.post(
                rpc,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "eth_sendRawTransaction",
                    "params": [raw],
                },
            )
            body = send.json()
            if body.get("error"):
                raise TreasuryError(str(body["error"]))
            tx_hash = body.get("result")
            if not tx_hash:
                raise TreasuryError(f"No tx hash: {send.text}")
            return tx_hash


treasury_service = TreasuryService()
