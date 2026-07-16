"""Injective EVM network profiles — testnet default, mainnet gated."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkProfile:
    name: str
    evm_chain_id: int
    x402_network: str  # CAIP-2
    usdc_address: str
    cctp_iris_api: str
    cctp_domain: int  # Circle domain for Injective
    rpc_url: str
    explorer_url: str
    faucet_enabled_default: bool


NETWORKS: dict[str, NetworkProfile] = {
    "testnet": NetworkProfile(
        name="testnet",
        evm_chain_id=1439,
        x402_network="eip155:1439",
        # Injective EVM testnet USDC (CCTP demo) — NOT mainnet USDC
        usdc_address="0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d",
        cctp_iris_api="https://iris-api-sandbox.circle.com",
        cctp_domain=29,
        rpc_url="https://k8s.testnet.json-rpc.injective.network/",
        explorer_url="https://testnet.blockscout.injective.network",
        faucet_enabled_default=False,  # product mode: real testnet USDC deposits
    ),
    "mainnet": NetworkProfile(
        name="mainnet",
        evm_chain_id=1776,
        x402_network="eip155:1776",
        usdc_address="0xa00C59fF5a080D2b954d0c75e46E22a0c371235a",
        cctp_iris_api="https://iris-api.circle.com",
        cctp_domain=19,  # Injective mainnet CCTP domain (confirm before prod)
        rpc_url="https://jrpc.injective.network",
        explorer_url="https://blockscout.injective.network",
        faucet_enabled_default=False,
    ),
}


def get_profile(network: str) -> NetworkProfile:
    key = (network or "testnet").strip().lower()
    if key not in NETWORKS:
        raise ValueError(f"Unknown INJECTIVE_NETWORK={network!r}; use testnet|mainnet")
    return NETWORKS[key]
