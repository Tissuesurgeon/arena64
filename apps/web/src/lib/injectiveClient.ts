import {
  createPublicClient,
  createWalletClient,
  custom,
  fallback,
  http,
  type Address,
  type PublicClient,
  type WalletClient,
} from "viem";
import { injectiveEvm, INJECTIVE_CHAIN_ID } from "@/lib/chain";
import { USDC_ERC20_ABI } from "@/lib/depositUsdc";

/** Circle CCTP USDC on Injective EVM testnet (chain 1439). */
export const INJECTIVE_TESTNET_USDC =
  "0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d" as Address;

/** Known Arena64 testnet treasury (overridden by API config when present). */
export const DEFAULT_TREASURY_TESTNET =
  "0xaf71511B2e34703f0bD39B66eABfd020F60574f2" as Address;

/** Official + archival RPCs from Injective network docs. */
const RPC_URLS = [
  injectiveEvm.rpcUrls.default.http[0],
  "https://k8s.testnet.json-rpc.injective.network/",
  "https://testnet.evm.archival.chain.virtual.json-rpc.injective.network/",
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
      transport: fallback(
        RPC_URLS.map((url) => http(url, { timeout: 20_000, retryCount: 1 }))
      ),
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

type EthereumProvider = {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
};

/** Fresh MetaMask wallet client on Injective (Injective MetaMask docs pattern). */
export function getMetaMaskWalletClient(account: Address): WalletClient {
  const ethereum = (
    typeof window !== "undefined"
      ? (window as Window & { ethereum?: EthereumProvider }).ethereum
      : undefined
  ) as EthereumProvider | undefined;
  if (!ethereum?.request) {
    throw new Error("MetaMask not found. Install MetaMask and try again.");
  }
  return createWalletClient({
    account,
    chain: injectiveEvm,
    transport: custom(ethereum),
  });
}

/** Prompt MetaMask to import the correct Injective USDC token. */
export async function watchInjectiveUsdc(
  usdcAddress: Address = defaultUsdcAddress()
): Promise<boolean> {
  const ethereum = (
    typeof window !== "undefined"
      ? (window as Window & { ethereum?: EthereumProvider }).ethereum
      : undefined
  ) as EthereumProvider | undefined;
  if (!ethereum?.request) {
    throw new Error("MetaMask not found.");
  }
  // MetaMask wallet_watchAsset takes a single object param (not an array).
  const request = ethereum.request as (args: {
    method: string;
    params?: unknown;
  }) => Promise<unknown>;
  const ok = await request({
    method: "wallet_watchAsset",
    params: {
      type: "ERC20",
      options: {
        address: usdcAddress,
        symbol: "USDC",
        decimals: 6,
      },
    },
  });
  return Boolean(ok);
}

/**
 * Read Injective USDC balance.
 * Order: same-origin Next proxy → Railway API → direct browser RPC.
 */
export async function readUsdcBalanceOf(
  owner: Address,
  usdcAddress: Address = defaultUsdcAddress()
): Promise<bigint> {
  // 1) Same-origin Next.js proxy (most reliable in the browser)
  try {
    const res = await fetch(`/api/onchain-usdc?address=${encodeURIComponent(owner)}`, {
      cache: "no-store",
    });
    if (res.ok) {
      const json = (await res.json()) as { balance_micro?: string };
      if (json.balance_micro != null) return BigInt(json.balance_micro);
    }
  } catch {
    /* try next */
  }

  // 2) Arena64 API (JWT) — server RPC on Railway
  try {
    if (typeof window !== "undefined" && localStorage.getItem("arena64_token")) {
      const { api } = await import("@/lib/api");
      const res = await api<{ balance_micro: string }>("/api/wallet/onchain-usdc");
      return BigInt(res.balance_micro);
    }
  } catch {
    /* try next */
  }

  // 3) Direct browser → Injective RPC
  const client = getInjectivePublicClient();
  return (await client.readContract({
    address: usdcAddress,
    abi: USDC_ERC20_ABI,
    functionName: "balanceOf",
    args: [owner],
  })) as bigint;
}
