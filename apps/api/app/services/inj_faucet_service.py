"""Injective testnet INJ faucet — one claim per wallet via on-chain InjFaucet.claimFor."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from eth_account import Account
from eth_utils import keccak, to_checksum_address

from app.core.config import get_settings
from app.integrations.injective.networks import get_profile

logger = logging.getLogger(__name__)

# claimFor(address) — first 4 bytes of keccak
_CLAIM_FOR_SELECTOR = keccak(text="claimFor(address)")[:4]
_HAS_CLAIMED_SELECTOR = keccak(text="hasClaimed(address)")[:4]


class InjFaucetError(Exception):
    pass


def _pad_address(addr: str) -> bytes:
    return bytes.fromhex(addr.lower().replace("0x", "").zfill(64))


def _encode_claim_for(to_address: str) -> str:
    return "0x" + (_CLAIM_FOR_SELECTOR + _pad_address(to_address)).hex()


def _encode_has_claimed(to_address: str) -> str:
    return "0x" + (_HAS_CLAIMED_SELECTOR + _pad_address(to_address)).hex()


class InjFaucetService:
    def enabled(self) -> bool:
        settings = get_settings()
        if settings.is_mainnet:
            return False
        if not (settings.inj_key_evm or "").strip():
            return False
        if not (settings.inj_faucet_address or "").strip():
            return False
        return True

    def explorer_tx_url(self, tx_hash: str) -> str:
        profile = get_profile(get_settings().injective_network)
        return f"{profile.explorer_url}/tx/{tx_hash}"

    async def _rpc(self, method: str, params: list[Any]) -> Any:
        settings = get_settings()
        rpc = settings.injective_rpc_url or get_profile(settings.injective_network).rpc_url
        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(
                rpc,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            )
            body = res.json()
            if body.get("error"):
                raise InjFaucetError(str(body["error"]))
            return body.get("result")

    async def faucet_balance_wei(self) -> int:
        settings = get_settings()
        addr = settings.inj_faucet_address
        if not addr:
            return 0
        raw = await self._rpc("eth_getBalance", [to_checksum_address(addr), "latest"])
        return int(raw or "0x0", 16)

    async def has_claimed(self, wallet: str) -> bool:
        settings = get_settings()
        faucet = settings.inj_faucet_address
        if not faucet:
            return False
        data = _encode_has_claimed(wallet)
        raw = await self._rpc(
            "eth_call",
            [{"to": to_checksum_address(faucet), "data": data}, "latest"],
        )
        if not raw or raw == "0x":
            return False
        return int(raw, 16) != 0

    async def wallet_inj_balance_wei(self, wallet: str) -> float:
        raw = await self._rpc("eth_getBalance", [to_checksum_address(wallet), "latest"])
        return int(raw or "0x0", 16) / 1e18

    async def status(self, wallet: str | None) -> dict[str, Any]:
        settings = get_settings()
        enabled = self.enabled()
        bal_wei = 0
        claimed = False
        wallet_inj = None
        if enabled:
            try:
                bal_wei = await self.faucet_balance_wei()
            except InjFaucetError as exc:
                logger.warning("faucet balance read failed: %s", exc)
            if wallet:
                try:
                    claimed = await self.has_claimed(wallet)
                    wallet_inj = await self.wallet_inj_balance_wei(wallet)
                except InjFaucetError as exc:
                    logger.warning("faucet status for wallet failed: %s", exc)
        return {
            "enabled": enabled,
            "network": settings.injective_network,
            "chain_id": settings.injective_evm_chain_id,
            "faucet_address": settings.inj_faucet_address or None,
            "claim_amount_inj": 1.0,
            "claimed": claimed,
            "faucet_balance_inj": bal_wei / 1e18,
            "wallet_inj_balance": wallet_inj,
            "explorer_url": get_profile(settings.injective_network).explorer_url,
            "once_per_wallet": True,
        }

    async def claim_for(self, wallet: str) -> dict[str, Any]:
        settings = get_settings()
        if settings.is_mainnet:
            raise InjFaucetError("INJ faucet is testnet-only")
        if not self.enabled():
            raise InjFaucetError("INJ faucet is not configured (need INJ_KEY_EVM + INJ_FAUCET_ADDRESS)")

        wallet = wallet.strip().lower()
        if not wallet.startswith("0x") or len(wallet) != 42:
            raise InjFaucetError("Invalid wallet address")

        if await self.has_claimed(wallet):
            raise InjFaucetError("This wallet already claimed its 1 INJ")

        bal = await self.faucet_balance_wei()
        if bal < 10**18:
            raise InjFaucetError("Faucet empty — refill the InjFaucet contract with testnet INJ")

        pk = settings.inj_key_evm.strip()
        if not pk.startswith("0x"):
            pk = "0x" + pk
        account = Account.from_key(pk)
        faucet = to_checksum_address(settings.inj_faucet_address)
        data = _encode_claim_for(wallet)

        nonce_hex = await self._rpc("eth_getTransactionCount", [account.address, "pending"])
        gas_price_hex = await self._rpc("eth_gasPrice", [])
        gas_price = int(gas_price_hex or "0x3b9aca00", 16)
        chain_id = int(settings.injective_evm_chain_id or 1439)

        # USDC-hook style overhead not needed for native transfer; still leave headroom
        signed = account.sign_transaction(
            {
                "nonce": int(nonce_hex, 16),
                "gasPrice": gas_price,
                "gas": 200_000,
                "to": faucet,
                "value": 0,
                "data": data,
                "chainId": chain_id,
            }
        )
        raw_bytes = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        raw = raw_bytes.hex() if hasattr(raw_bytes, "hex") else str(raw_bytes)
        if not raw.startswith("0x"):
            raw = "0x" + raw

        try:
            tx_hash = await self._rpc("eth_sendRawTransaction", [raw])
        except InjFaucetError as exc:
            msg = str(exc).lower()
            if "alreadyclaimed" in msg or "already claimed" in msg:
                raise InjFaucetError("This wallet already claimed its 1 INJ") from exc
            if "insufficientfaucetbalance" in msg or "insufficient" in msg:
                raise InjFaucetError("Faucet empty — refill the InjFaucet contract with testnet INJ") from exc
            raise

        if not tx_hash:
            raise InjFaucetError("No transaction hash returned from RPC")

        logger.info("inj faucet claim wallet=%s tx=%s", wallet, tx_hash)
        return {
            "status": "claimed",
            "tx_hash": tx_hash,
            "claimed": True,
            "claim_amount_inj": 1.0,
            "to": wallet,
            "explorer_url": self.explorer_tx_url(tx_hash),
        }


inj_faucet_service = InjFaucetService()
