"""Verify on-chain USDC ERC-20 transfers to Arena64 treasury."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class DepositError(Exception):
    pass


def _topic_address(topic: str) -> str:
    """Decode padded address topic to 0x-prefixed checksum-agnostic address."""
    h = topic.lower().removeprefix("0x")
    return "0x" + h[-40:]


def _pad_address_topic(addr: str) -> str:
    return "0x" + addr.lower().removeprefix("0x").zfill(64)


def _receipt_ok(status: Any) -> bool:
    if status is None:
        return False
    if status in (1, "1", True):
        return True
    s = str(status).lower()
    return s in ("0x1", "0x01", "success")


class UsdcDepositVerifier:
    def __init__(self) -> None:
        settings = get_settings()
        self.rpc_url = settings.injective_rpc_url or ""
        self.usdc = (settings.injective_usdc_address or "").lower()
        self.treasury = (settings.arena64_treasury_address or "").lower()
        self.chain_id = settings.injective_evm_chain_id

    async def _rpc(self, method: str, params: list[Any]) -> Any:
        if not self.rpc_url:
            raise DepositError("INJECTIVE_RPC_URL not configured")
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                self.rpc_url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            )
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise DepositError(str(data["error"]))
            return data.get("result")

    async def _get_receipt(self, tx_hash: str, *, attempts: int = 8, delay_s: float = 1.5) -> dict:
        last_err: Exception | None = None
        for i in range(attempts):
            try:
                receipt = await self._rpc("eth_getTransactionReceipt", [tx_hash])
                if receipt:
                    return receipt
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning("deposit receipt poll %s/%s failed: %s", i + 1, attempts, exc)
            await asyncio.sleep(delay_s)
        if last_err:
            raise DepositError(f"Could not fetch transaction receipt: {last_err}") from last_err
        raise DepositError("Transaction not found or not yet mined — wait a few seconds and verify again")

    def _parse_transfer_amount(
        self,
        receipt: dict,
        *,
        expected_from: str,
    ) -> int:
        usdc_total = 0
        fallback_total = 0
        for log in receipt.get("logs") or []:
            topics = log.get("topics") or []
            if len(topics) < 3:
                continue
            if (topics[0] or "").lower() != TRANSFER_TOPIC:
                continue
            from_addr = _topic_address(topics[1])
            to_addr = _topic_address(topics[2])
            if to_addr != self.treasury:
                continue
            if from_addr != expected_from:
                raise DepositError("Transfer sender does not match your connected wallet")
            raw = log.get("data") or "0x0"
            try:
                amount = int(raw, 16)
            except ValueError:
                continue
            if amount <= 0:
                continue
            log_addr = (log.get("address") or "").lower()
            if log_addr == self.usdc:
                usdc_total += amount
            else:
                fallback_total += amount

        total = usdc_total if usdc_total > 0 else fallback_total
        if total <= 0:
            raise DepositError("No USDC Transfer to Arena64 treasury found in this transaction")
        return total

    def _verified_payload(self, *, tx_hash: str, expected_from: str, amount_usdc_micro: int, **extra: Any) -> dict[str, Any]:
        return {
            "tx_hash": tx_hash,
            "from": expected_from,
            "to": self.treasury,
            "amount_usdc_micro": amount_usdc_micro,
            "usdc": self.usdc,
            "chain_id": self.chain_id,
            **extra,
        }

    async def _scan_transfer_window(
        self,
        *,
        expected_from: str,
        lookback_blocks: int,
        window: int,
    ) -> list[dict[str, Any]]:
        latest_hex = await self._rpc("eth_blockNumber", [])
        latest = int(latest_hex, 16)
        from_topic = _pad_address_topic(expected_from)
        to_topic = _pad_address_topic(self.treasury)

        found: list[dict[str, Any]] = []
        scanned = 0
        while scanned < lookback_blocks:
            to_b = latest - scanned
            from_b = max(0, to_b - window + 1)
            try:
                logs = await self._rpc(
                    "eth_getLogs",
                    [
                        {
                            "address": self.usdc,
                            "fromBlock": hex(from_b),
                            "toBlock": hex(to_b),
                            "topics": [TRANSFER_TOPIC, from_topic, to_topic],
                        }
                    ],
                )
            except DepositError as exc:
                logger.warning("deposit log scan %s-%s failed: %s", from_b, to_b, exc)
                # Shrink window on RPC range errors
                if window > 1_000:
                    window = max(1_000, window // 2)
                    continue
                logs = []
            for log in logs or []:
                raw = log.get("data") or "0x0"
                try:
                    amount = int(raw, 16)
                except ValueError:
                    continue
                if amount <= 0:
                    continue
                txh = (log.get("transactionHash") or "").lower()
                if not txh:
                    continue
                found.append(
                    self._verified_payload(
                        tx_hash=txh,
                        expected_from=expected_from,
                        amount_usdc_micro=amount,
                        recovered_from_logs=True,
                        block_number=log.get("blockNumber"),
                    )
                )
            scanned += window
            if from_b == 0:
                break

        found.sort(key=lambda row: int(row.get("block_number") or "0x0", 16), reverse=True)
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for row in found:
            h = row["tx_hash"]
            if h in seen:
                continue
            seen.add(h)
            unique.append(row)
        return unique

    async def list_recent_transfers(
        self,
        expected_from: str,
        *,
        lookback_blocks: int = 200_000,
        window: int = 9_000,
    ) -> list[dict[str, Any]]:
        """Newest-first USDC Transfer logs: wallet → treasury (MetaMask hash recovery)."""
        if not self.treasury or not self.usdc:
            return []
        expected_from = expected_from.lower()
        # Fast recent pass first (Injective deposits usually appear here)
        recent = await self._scan_transfer_window(
            expected_from=expected_from,
            lookback_blocks=min(12_000, lookback_blocks),
            window=min(4_000, window),
        )
        if recent or lookback_blocks <= 12_000:
            return recent
        deeper = await self._scan_transfer_window(
            expected_from=expected_from,
            lookback_blocks=lookback_blocks,
            window=window,
        )
        seen = {r["tx_hash"] for r in recent}
        for row in deeper:
            if row["tx_hash"] not in seen:
                recent.append(row)
                seen.add(row["tx_hash"])
        return recent

    async def balance_of(self, owner: str) -> int:
        """ERC-20 USDC balanceOf (raw micro-units, 6 decimals)."""
        if not self.usdc:
            raise DepositError("USDC address not configured")
        owner = owner.lower().removeprefix("0x")
        data = "0x70a08231" + owner.zfill(64)
        result = await self._rpc("eth_call", [{"to": self.usdc, "data": data}, "latest"])
        if result is None:
            raise DepositError("USDC balanceOf returned empty")
        return int(str(result), 16)

    async def verify_transfer(self, *, tx_hash: str, expected_from: str) -> dict[str, Any]:
        if not self.treasury:
            raise DepositError("ARENA64_TREASURY_ADDRESS not configured")
        if not self.usdc:
            raise DepositError("USDC address not configured")

        tx_hash = (tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}").lower()
        expected_from = expected_from.lower()

        # Injective RPC often returns null for eth_getTransactionReceipt / ByHash even
        # when the Transfer is present in eth_getLogs — prefer logs when receipt misses.
        try:
            receipt = await self._get_receipt(tx_hash, attempts=4, delay_s=1.0)
            status = receipt.get("status")
            if status is not None and not _receipt_ok(status):
                raise DepositError("Transaction failed on-chain")
            total = self._parse_transfer_amount(receipt, expected_from=expected_from)
            return self._verified_payload(
                tx_hash=tx_hash, expected_from=expected_from, amount_usdc_micro=total
            )
        except DepositError as receipt_err:
            logger.warning("receipt path failed for %s (%s); matching getLogs", tx_hash, receipt_err)
            candidates = await self.list_recent_transfers(expected_from)
            for cand in candidates:
                if cand["tx_hash"] == tx_hash:
                    return {**cand, "verified_via": "eth_getLogs"}
            raise DepositError(
                "Transaction not found or not yet mined — wait a few seconds and verify again"
            ) from receipt_err
