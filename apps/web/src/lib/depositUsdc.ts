import type { Address, Hex, PublicClient, WalletClient } from "viem";
import { INJECTIVE_CHAIN_ID, injectiveEvm } from "@/lib/chain";

/** Minimal ERC-20 ABI for USDC transfer + balance. */
export const USDC_ERC20_ABI = [
  {
    type: "function",
    name: "transfer",
    stateMutability: "nonpayable",
    inputs: [
      { name: "to", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    type: "function",
    name: "balanceOf",
    stateMutability: "view",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ name: "", type: "uint256" }],
  },
] as const;

/** Injective USDC EVM compliance hook needs far more gas than a plain ERC-20 transfer. */
const USDC_GAS_FLOOR = BigInt(500_000);
const USDC_GAS_FALLBACK = BigInt(1_000_000);
const RECEIPT_TIMEOUT_MS = 90_000;

export const INJECTIVE_TESTNET_FAUCET = "https://testnet.faucet.injective.network";

export type SendUsdcDepositParams = {
  publicClient: PublicClient;
  walletClient: WalletClient;
  account: Address;
  chainId: number;
  usdcAddress: Address;
  treasuryAddress: Address;
  amountMicro: bigint;
};

export type SendUsdcDepositResult = {
  hash: Hex;
  confirmed: boolean;
};

export class DepositSendError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DepositSendError";
  }
}

/**
 * Send USDC to Arena64 treasury via MetaMask using Injective best practices:
 * estimate gas (USDC-hook aware), writeContract without forced gasPrice, wait for receipt.
 */
export async function sendUsdcDepositToTreasury(
  params: SendUsdcDepositParams
): Promise<SendUsdcDepositResult> {
  const {
    publicClient,
    walletClient,
    account,
    chainId,
    usdcAddress,
    treasuryAddress,
    amountMicro,
  } = params;

  if (chainId !== INJECTIVE_CHAIN_ID) {
    throw new DepositSendError("Switch your wallet to Injective EVM Testnet, then try again.");
  }
  if (amountMicro <= BigInt(0)) {
    throw new DepositSendError("Enter a positive USDC amount.");
  }

  const usdcBal = (await publicClient.readContract({
    address: usdcAddress,
    abi: USDC_ERC20_ABI,
    functionName: "balanceOf",
    args: [account],
  })) as bigint;
  if (usdcBal < amountMicro) {
    throw new DepositSendError("Not enough USDC in your Connected Wallet for this deposit.");
  }

  const injBal = await publicClient.getBalance({ address: account });
  if (injBal <= BigInt(0)) {
    throw new DepositSendError(
      `Get testnet INJ for gas (${INJECTIVE_TESTNET_FAUCET}), then retry Deposit.`
    );
  }

  let gas = USDC_GAS_FALLBACK;
  try {
    const estimated = await publicClient.estimateContractGas({
      address: usdcAddress,
      abi: USDC_ERC20_ABI,
      functionName: "transfer",
      args: [treasuryAddress, amountMicro],
      account,
    });
    const buffered = estimated * BigInt(2);
    gas = buffered > USDC_GAS_FLOOR ? buffered : USDC_GAS_FLOOR;
  } catch {
    gas = USDC_GAS_FALLBACK;
  }

  // No gasPrice / EIP-1559 overrides — MetaMask fills fees (Injective MetaMask docs).
  const hash = await walletClient.writeContract({
    chain: injectiveEvm,
    account,
    address: usdcAddress,
    abi: USDC_ERC20_ABI,
    functionName: "transfer",
    args: [treasuryAddress, amountMicro],
    gas,
  });

  try {
    const receipt = await publicClient.waitForTransactionReceipt({
      hash,
      timeout: RECEIPT_TIMEOUT_MS,
    });
    if (receipt.status !== "success") {
      throw new DepositSendError(
        "Transaction failed on-chain (USDC on Injective often needs more gas — retry Deposit). Check Blockscout if unsure."
      );
    }
    return { hash, confirmed: true };
  } catch (err: unknown) {
    if (err instanceof DepositSendError) throw err;
    // Timeout / RPC null receipt — caller falls back to balance/sync recovery.
    return { hash, confirmed: false };
  }
}
