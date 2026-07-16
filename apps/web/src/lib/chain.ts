import { defineChain } from "viem";

const chainId = Number(process.env.NEXT_PUBLIC_CHAIN_ID || 1439);
const rpcUrl =
  process.env.NEXT_PUBLIC_RPC_URL || "https://k8s.testnet.json-rpc.injective.network/";
const chainName = process.env.NEXT_PUBLIC_CHAIN_NAME || "Injective EVM Testnet";

/** Injective EVM (testnet default: 1439, mainnet: 1776). */
export const injectiveEvm = defineChain({
  id: chainId,
  name: chainName,
  nativeCurrency: { name: "Injective", symbol: "INJ", decimals: 18 },
  rpcUrls: {
    default: { http: [rpcUrl] },
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
