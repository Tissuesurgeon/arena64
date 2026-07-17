import { createPublicClient, http, type Address, type PublicClient } from "viem";
import { injectiveEvm, INJECTIVE_CHAIN_ID } from "@/lib/chain";
import { USDC_ERC20_ABI } from "@/lib/depositUsdc";

/** Circle CCTP USDC on Injective EVM testnet (chain 1439). */
export const INJECTIVE_TESTNET_USDC =
  "0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d" as Address;

/** Known Arena64 testnet treasury (overridden by API config when present). */
export const DEFAULT_TREASURY_TESTNET =
  "0xaf71511B2e34703f0bD39B66eABfd020F60574f2" as Address;

const RPC_URLS = [
  injectiveEvm.rpcUrls.default.http[0],
  "https://k8s.testnet.json-rpc.injective.network/",
].filter((u, i, arr) => Boolean(u) && arr.indexOf(u) === i);

let cached: PublicClient | null = null;

/**
 * Public client pinned to Injective — independent of MetaMask's active chain.
 * wagmi's usePublicClient can be undefined while the wallet is on another network.
 */
export function getInjectivePublicClient(): PublicClient {
  if (!cached) {
    cached = createPublicClient({
      chain: injectiveEvm,
      transport: http(RPC_URLS[0], { timeout: 20_000, retryCount: 2 }),
    });
  }
  return cached;
}

export function defaultUsdcAddress(): Address {
  if (INJECTIVE_CHAIN_ID === 1776) {
    return "0xa00C59fF5a080D2b954d0c75e46E22a0c371235a";
  }
  return INJECTIVE_TESTNET_USDC;
}

export function defaultTreasuryAddress(): Address | null {
  if (INJECTIVE_CHAIN_ID === 1776) return null;
  return DEFAULT_TREASURY_TESTNET;
}

export async function readUsdcBalanceOf(
  owner: Address,
  usdcAddress: Address = defaultUsdcAddress()
): Promise<bigint> {
  const client = getInjectivePublicClient();
  return (await client.readContract({
    address: usdcAddress,
    abi: USDC_ERC20_ABI,
    functionName: "balanceOf",
    args: [owner],
  })) as bigint;
}
