/** User-facing copy only — never surface raw API / viem / backend strings. */

function rawText(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "object" && err && "shortMessage" in err) {
    return String((err as { shortMessage: unknown }).shortMessage ?? "");
  }
  if (typeof err === "object" && err && "details" in err) {
    return String((err as { details: unknown }).details ?? "");
  }
  return typeof err === "string" ? err : "";
}

export function formatWalletError(err: unknown, context: "deposit" | "withdraw" | "generic" = "generic"): string {
  const lower = rawText(err).toLowerCase();

  if (
    lower.includes("user rejected") ||
    lower.includes("user denied") ||
    lower.includes("rejected the request") ||
    lower.includes("denied transaction signature") ||
    lower.includes("request rejected")
  ) {
    if (context === "withdraw") return "Withdraw cancelled.";
    if (context === "deposit") return "Deposit cancelled — you rejected the transaction in your wallet.";
    return "Request cancelled in your wallet.";
  }

  if (
    lower.includes("get testnet inj") ||
    lower.includes("inj for gas") ||
    (lower.includes("faucet.injective") && lower.includes("gas"))
  ) {
    return "Get testnet INJ for gas (Injective faucet), then retry Deposit.";
  }

  if (
    lower.includes("restricted action") ||
    lower.includes("outofgas") ||
    lower.includes("out of gas") ||
    lower.includes("needs more gas")
  ) {
    return "USDC on Injective needs more gas — retry Deposit.";
  }

  if (lower.includes("insufficient") || lower.includes("need ") || lower.includes("exceeds balance")) {
    if (context === "withdraw") return "Not enough Available balance to withdraw.";
    if (lower.includes("inj") || lower.includes("gas")) {
      return "Get testnet INJ for gas (Injective faucet), then retry Deposit.";
    }
    return "Not enough USDC (or gas) in your Connected Wallet.";
  }

  if (lower.includes("chain") && (lower.includes("mismatch") || lower.includes("switch"))) {
    return "Switch your wallet to Injective EVM Testnet, then try again.";
  }

  if (lower.includes("already recorded") || lower.includes("already credited")) {
    return "This transfer was already credited to your Arena64 Account.";
  }

  if (
    lower.includes("still in your wallet") ||
    lower.includes("no usdc transfer to the arena64 treasury") ||
    lower.includes("no usdc left")
  ) {
    return "No deposit reached Arena64. MetaMask often returns a fake hash on Injective — your USDC is still in your wallet. Try Deposit again.";
  }

  if (
    lower.includes("not found") ||
    lower.includes("not yet mined") ||
    lower.includes("verify again") ||
    lower.includes("could not fetch") ||
    lower.includes("never mined")
  ) {
    return "That hash is not on Injective testnet (MetaMask often shows a dead hash). Paste the real Blockscout USDC transfer hash under Verify & credit, or click Sync deposits.";
  }

  if (lower.includes("no usdc transfer") || lower.includes("sender does not match")) {
    return "That tx does not look like a USDC deposit from your connected wallet to Arena64. Check the hash and try again.";
  }

  if (
    lower.includes("transaction failed") ||
    lower.includes("reverted") ||
    (lower.includes("failed") && (lower.includes("rpc") || lower.includes("receipt")))
  ) {
    return "Wallet may show failed on Injective even when the transfer succeeded. Check Blockscout, then Verify & credit with the tx hash.";
  }

  if (lower.includes("private key") || (context === "withdraw" && lower.includes("treasury"))) {
    return "Withdrawals are not enabled yet (treasury payout key not configured).";
  }

  if (lower.includes("treasury") || lower.includes("not configured")) {
    return "Deposits are temporarily unavailable. Please try again later.";
  }

  if (context === "withdraw") return "Withdraw failed. Please try again.";
  if (context === "deposit") return "Deposit failed. Please try again — or paste the tx hash under Already sent USDC.";
  return "Something went wrong. Please try again.";
}

export function formatDashboardError(_err?: unknown): string {
  return "Something went wrong. Please try again.";
}
