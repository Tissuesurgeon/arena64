import { defineChain } from "viem";

const chainId = Number(process.env.NEXT_PUBLIC_CHAIN_ID || 1439);
const rpcUrl =
  process.env.NEXT_PUBLIC_RPC_URL || "https://k8s.testnet.json-rpc.injective.network/";
/** Archival JSON-RPC from Injective network docs (fallback for balance/tx lookups). */
const archivalRpcUrl =
  process.env.NEXT_PUBLIC_ARCHIVAL_RPC_URL ||
  "https://testnet.evm.archival.chain.virtual.json-rpc.injective.network/";
const chainName = process.env.NEXT_PUBLIC_CHAIN_NAME || "Injective EVM Testnet";

/** Injective EVM (testnet default: 1439, mainnet: 1776). */
export const injectiveEvm = defineChain({
  id: chainId,
  name: chainName,
  nativeCurrency: { name: "Injective", symbol: "INJ", decimals: 18 },
  rpcUrls: {
    default: { http: [rpcUrl, archivalRpcUrl] },
  },
  blockExplorers: {
    default: {
      name: "Blockscout",
      url:
        chainId === 1776
          ? "https://blockscout.injective.network"
          : "https://testnet.blockscout.injective.network",
    },
  },
  testnet: chainId !== 1776,
});

export const INJECTIVE_CHAIN_ID = chainId;

/** MetaMask wallet_addEthereumChain params (chainId as hex). */
export function injectiveAddChainParams() {
  return {
    chainId: `0x${INJECTIVE_CHAIN_ID.toString(16)}`,
    chainName: injectiveEvm.name,
    nativeCurrency: {
      name: injectiveEvm.nativeCurrency.name,
      symbol: injectiveEvm.nativeCurrency.symbol,
      decimals: injectiveEvm.nativeCurrency.decimals,
    },
    rpcUrls: [...injectiveEvm.rpcUrls.default.http],
    blockExplorerUrls: [injectiveEvm.blockExplorers.default.url],
  };
}

type EthereumProvider = {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
};

/**
 * Switch MetaMask to Injective EVM; add the network if missing.
 * Triggers a MetaMask popup when the user is on another chain.
 */
export async function ensureInjectiveChain(options?: {
  currentChainId?: number | null;
  switchChainAsync?: (args: { chainId: number }) => Promise<unknown>;
}): Promise<void> {
  const current = options?.currentChainId;
  if (current === INJECTIVE_CHAIN_ID) return;

  if (options?.switchChainAsync) {
    try {
      await options.switchChainAsync({ chainId: INJECTIVE_CHAIN_ID });
      return;
    } catch {
      /* fall through to wallet_addEthereumChain */
    }
  }

  const ethereum = (typeof window !== "undefined"
    ? (window as Window & { ethereum?: EthereumProvider }).ethereum
    : undefined) as EthereumProvider | undefined;

  if (!ethereum?.request) {
    throw new Error("MetaMask not found. Install MetaMask and try again.");
  }

  try {
    await ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: `0x${INJECTIVE_CHAIN_ID.toString(16)}` }],
    });
  } catch (err: unknown) {
    const code =
      err && typeof err === "object" && "code" in err
        ? Number((err as { code: unknown }).code)
        : 0;
    // 4902 = unrecognized chain — add it
    if (code === 4902 || code === -32603) {
      await ethereum.request({
        method: "wallet_addEthereumChain",
        params: [injectiveAddChainParams()],
      });
      return;
    }
    const msg = err instanceof Error ? err.message : String(err);
    if (/reject|denied|cancel/i.test(msg)) {
      throw new Error("Network switch rejected in MetaMask — approve Injective EVM Testnet to deposit.");
    }
    throw new Error(
      `Switch MetaMask to Injective EVM Testnet (chain ${INJECTIVE_CHAIN_ID}), then try Deposit again.`
    );
  }
}
