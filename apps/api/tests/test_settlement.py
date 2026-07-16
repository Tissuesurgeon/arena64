import pytest

from app.integrations.cctp.iris import IrisClient, IrisError
from app.integrations.x402.facilitator import require_x402_payment
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_iris_rejects_demo_attestation_when_required(monkeypatch):
    monkeypatch.setenv("CCTP_REQUIRE_ATTESTATION", "true")
    get_settings.cache_clear()
    client = IrisClient()
    with pytest.raises(IrisError, match="Demo attestations"):
        await client.verify_deposit(
            burn_tx_hash="0xabc",
            source_domain=6,
            attestation="demo-attestation",
            message_bytes=None,
        )
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_iris_accepts_client_attestation(monkeypatch):
    monkeypatch.setenv("CCTP_REQUIRE_ATTESTATION", "true")
    get_settings.cache_clear()
    client = IrisClient()
    result = await client.verify_deposit(
        burn_tx_hash="0xabc",
        source_domain=6,
        attestation="0x" + "ab" * 32,
        message_bytes="0xmsg",
    )
    assert result["ok"] is True
    assert result["mode"] == "client_attestation"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_x402_verify_disabled_accepts_proof(monkeypatch):
    monkeypatch.setenv("X402_REQUIRE_VERIFY", "false")
    get_settings.cache_clear()
    meta = await require_x402_payment("proof-header-value", amount_micro="1000000")
    assert meta["ok"] is True
    assert meta["mode"] == "verify_disabled"
    get_settings.cache_clear()
