import {
  encodeFunctionData,
  type Address,
  type Hex,
  type PublicClient,
  type WalletClient,
} from "viem";
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

/**
 * Injective USDC (MTS) runs a compliance EVM hook on every transfer.
 * Under-gassing surfaces as "transfer is restricted by EVM hook / ErrorOutOfGas"
 * even when the transfer is allowed — use a high explicit gas limit.
 * @see https://docs.injective.network/developers-defi/usdc-stablecoin
 */
const USDC_GAS_FLOOR = BigInt(2_000_000);
const USDC_GAS_FALLBACK = BigInt(3_000_000);
const RECEIPT_TIMEOUT_MS = 90_000;

export const INJECTIVE_TESTNET_FAUCET = "https://testnet.faucet.injective.network";
export const CIRCLE_FAUCET = "https://faucet.circle.com/";

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
 * Send USDC to Arena64 treasury via MetaMask.
 * Uses sendTransaction + explicit gas (Injective USDC hook-safe).
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
    throw new DepositSendError(
      `Not enough Injective USDC (${Number(usdcBal) / 1e6} available). ` +
        `Get testnet USDC from ${CIRCLE_FAUCET} — select Injective, not Sepolia.`
    );
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
    const buffered = estimated * BigInt(3);
    gas = buffered > USDC_GAS_FLOOR ? buffered : USDC_GAS_FLOOR;
  } catch {
    gas = USDC_GAS_FALLBACK;
  }

  const data = encodeFunctionData({
    abi: USDC_ERC20_ABI,
    functionName: "transfer",
    args: [treasuryAddress, amountMicro],
  });

  // MetaMask + Injective: prefer sendTransaction with forced gas over writeContract defaults
  const hash = await walletClient.sendTransaction({
    chain: injectiveEvm,
    account,
    to: usdcAddress,
    data,
    gas,
  });

  try {
    const receipt = await publicClient.waitForTransactionReceipt({
      hash,
      timeout: RECEIPT_TIMEOUT_MS,
    });
    if (receipt.status !== "success") {
      throw new DepositSendError(
        "Transaction failed on-chain. Injective USDC often needs higher gas — retry Deposit. Check Blockscout if unsure."
      );
    }
    return { hash, confirmed: true };
  } catch (err: unknown) {
    if (err instanceof DepositSendError) throw err;
    return { hash, confirmed: false };
  }
}
