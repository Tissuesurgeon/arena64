from app.core.config import get_settings
from app.integrations.injective.networks import get_profile


def test_testnet_profile_usdc_not_mainnet():
    get_settings.cache_clear()
    s = get_settings()
    assert s.injective_network == "testnet"
    profile = get_profile("testnet")
    assert s.injective_usdc_address.lower() == profile.usdc_address.lower()
    assert s.injective_usdc_address.lower() != "0xa00c59ff5a080d2b954d0c75e46e22a0c371235a"
    assert s.injective_evm_chain_id == 1439
    assert s.x402_network == "eip155:1439"
    assert "sandbox" in (s.cctp_iris_api or "")
    assert s.demo_faucet_enabled is False


def test_mainnet_disables_faucet(monkeypatch):
    monkeypatch.setenv("INJECTIVE_NETWORK", "mainnet")
    get_settings.cache_clear()
    s = get_settings()
    assert s.injective_network == "mainnet"
    assert s.injective_evm_chain_id == 1776
    assert s.demo_faucet_enabled is False
    assert s.x402_allow_testnet_fallback is False
    get_settings.cache_clear()
