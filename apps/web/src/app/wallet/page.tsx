"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAccount, usePublicClient, useWalletClient } from "wagmi";
import { parseUnits, type Hex } from "viem";
import { api, getStoredUser } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { INJECTIVE_CHAIN_ID } from "@/lib/chain";
import {
  INJECTIVE_TESTNET_FAUCET,
  sendUsdcDepositToTreasury,
  USDC_ERC20_ABI,
} from "@/lib/depositUsdc";
import { formatWalletError } from "@/lib/walletErrors";

/** MetaMask often marks Injective txs "failed" after broadcast; recover the hash if present. */
function extractTxHash(err: unknown): Hex | null {
  if (!err || typeof err !== "object") return null;
  const rec = err as Record<string, unknown>;
  for (const key of ["hash", "transactionHash", "txHash"] as const) {
    const v = rec[key];
    if (typeof v === "string" && /^0x[a-fA-F0-9]{64}$/.test(v)) return v as Hex;
  }
  if (rec.cause) {
    const nested = extractTxHash(rec.cause);
    if (nested) return nested;
  }
  try {
    const m = JSON.stringify(err).match(/0x[a-fA-F0-9]{64}/);
    if (m) return m[0] as Hex;
  } catch {
    /* ignore */
  }
  return null;
}

type WalletConfig = {
  network?: string;
  chain_id?: number;
  usdc_address?: string;
  treasury_address?: string | null;
  explorer_url?: string;
  faucet_enabled?: boolean;
  withdraw_enabled?: boolean;
  external_faucets?: { circle?: string; injective?: string };
};

type BalanceSnap = {
  available_usdc?: number;
  locked_usdc?: number;
  usdc?: number;
  usdc_total?: number;
  coach_credits?: number;
  xp?: number;
};

type TxRow = {
  id: string;
  type: string;
  amount_usdc: number;
  created_at: string;
  external_ref?: string | null;
};

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export default function Arena64AccountPage() {
  const { user, refreshUser, shortAddress } = useAuth();
  const { address, isConnected, chainId } = useAccount();
  const publicClient = usePublicClient({ chainId: INJECTIVE_CHAIN_ID });
  const { data: walletClient } = useWalletClient({ chainId: INJECTIVE_CHAIN_ID });
  const [bal, setBal] = useState<BalanceSnap | null>(null);
  const [cfg, setCfg] = useState<WalletConfig | null>(null);
  const [txs, setTxs] = useState<TxRow[]>([]);
  const [source, setSource] = useState<"injective" | "cctp">("injective");
  const [amount, setAmount] = useState("5");
  const [withdrawAmt, setWithdrawAmt] = useState("1");
  const [manualHash, setManualHash] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState("");
  const [cctpHash, setCctpHash] = useState("");
  const [cctpAttest, setCctpAttest] = useState("");
  const [cctpAmount, setCctpAmount] = useState("25");
  const [submittedHash, setSubmittedHash] = useState<string>("");
  const [walletUsdc, setWalletUsdc] = useState<number | null>(null);
  const creditedHashes = useRef<Set<string>>(new Set());
  const creditInFlight = useRef<string | null>(null);

  const readUsdcBalance = useCallback(async (): Promise<bigint | null> => {
    if (!publicClient || !cfg?.usdc_address || !address) return null;
    try {
      return (await publicClient.readContract({
        address: cfg.usdc_address as `0x${string}`,
        abi: USDC_ERC20_ABI,
        functionName: "balanceOf",
        args: [address],
      })) as bigint;
    } catch {
      return null;
    }
  }, [publicClient, cfg?.usdc_address, address]);

  const refreshWalletUsdc = useCallback(async () => {
    const raw = await readUsdcBalance();
    if (raw == null) {
      setWalletUsdc(null);
      return;
    }
    setWalletUsdc(Number(raw) / 1e6);
  }, [readUsdcBalance]);

  const refresh = useCallback(async () => {
    if (!getStoredUser()) return;
    const b = await api<BalanceSnap>("/api/wallet/balance");
    setBal(b);
    const rows = await api<TxRow[]>("/api/wallet/transactions").catch(() => []);
    setTxs(rows);
    await refreshUser?.();
    await refreshWalletUsdc().catch(() => undefined);
  }, [refreshUser, refreshWalletUsdc]);

  const trySyncCredit = useCallback(async (): Promise<boolean> => {
    const res = await api<{
      credited_count: number;
      credited_usdc: number;
      available_usdc?: number;
    }>("/api/wallet/deposit/sync", { method: "POST", body: "{}" });
    if (res.credited_count > 0) {
      setMsg(
        `Synced ${res.credited_count} on-chain deposit(s) · +${res.credited_usdc} USDC · Available: ${res.available_usdc ?? "—"}`
      );
      setPhase("Done");
      await refresh();
      return true;
    }
    return false;
  }, [refresh]);

  const syncDeposits = useCallback(
    async ({ quiet = false }: { quiet?: boolean } = {}) => {
      if (!getStoredUser()) return;
      try {
        const ok = await trySyncCredit();
        if (!ok && !quiet) {
          setMsg(
            "No new wallet→treasury USDC transfers found. If MetaMask showed success but your Connected Wallet USDC did not drop, the transfer never mined — try Deposit again."
          );
          await refresh();
        } else if (ok || quiet) {
          await refresh();
        }
      } catch {
        await refresh().catch(() => undefined);
      }
    },
    [refresh, trySyncCredit]
  );

  useEffect(() => {
    syncDeposits({ quiet: true }).catch(() => undefined);
    api<WalletConfig>("/api/wallet/cctp/config").then(setCfg).catch(() => undefined);
  }, [syncDeposits]);

  useEffect(() => {
    refreshWalletUsdc().catch(() => undefined);
  }, [refreshWalletUsdc, address, cfg?.usdc_address]);

  // MetaMask on Injective can sit on "pending/failed" while the send never resolves.
  useEffect(() => {
    if (!busy && !phase.startsWith("Approve")) return;
    const t = window.setTimeout(() => {
      setMsg(
        "If MetaMask shows failed but Blockscout shows success, paste the tx hash below and click Verify & credit."
      );
    }, 35_000);
    return () => window.clearTimeout(t);
  }, [busy, phase]);

  const waitForOnchainCredit = useCallback(
    async (opts: {
      hash?: string | null;
      amountMicro: bigint;
      balanceBefore: bigint | null;
    }) => {
      setBusy(true);
      setPhase("Confirming on-chain transfer…");
      try {
        for (let i = 0; i < 18; i++) {
          // Prefer sync — recovers real Transfer logs even when MetaMask hash is fake.
          try {
            if (await trySyncCredit()) return;
          } catch {
            /* keep polling */
          }

          const after = await readUsdcBalance();
          const leftWallet =
            opts.balanceBefore != null &&
            after != null &&
            after + opts.amountMicro <= opts.balanceBefore;

          if (leftWallet) {
            setPhase("USDC left wallet — crediting Arena64 Account…");
            try {
              if (await trySyncCredit()) return;
            } catch {
              /* keep polling */
            }
          }

          // Only hammer a hash if it actually exists on RPC (skip MetaMask phantoms).
          if (opts.hash && publicClient && i % 3 === 1) {
            try {
              const tx = await publicClient.getTransaction({ hash: opts.hash as Hex });
              if (tx) {
                setSubmittedHash(opts.hash);
                setManualHash(opts.hash);
                setPhase("On-chain tx found — verifying…");
                // Delegate to creditDeposit path below via API
                const res = await api<{ credited_usdc: number; available_usdc: number }>(
                  "/api/wallet/deposit",
                  { method: "POST", body: JSON.stringify({ tx_hash: opts.hash }) }
                );
                creditedHashes.current.add(opts.hash.toLowerCase());
                setMsg(
                  `Credited to Arena64 Account · +${res.credited_usdc} USDC · Available: ${res.available_usdc}`
                );
                setPhase("Done");
                await refresh();
                return;
              }
            } catch {
              /* phantom or not mined yet */
            }
          }

          setPhase(`Waiting for Injective confirmation… (${i + 1}/18)`);
          await sleep(2200);
        }

        const after = await readUsdcBalance();
        if (opts.balanceBefore != null && after != null && after >= opts.balanceBefore) {
          setMsg(
            "No USDC left your Connected Wallet. MetaMask on Injective often returns a hash that never mined — your funds are still there. Try Deposit again."
          );
        } else {
          setMsg(
            "USDC left your wallet but Arena64 has not credited yet. Click Sync deposits, or paste the Blockscout transfer hash under Verify & credit."
          );
        }
        setPhase("");
        await refreshWalletUsdc().catch(() => undefined);
      } finally {
        setBusy(false);
      }
    },
    [trySyncCredit, readUsdcBalance, publicClient, refresh, refreshWalletUsdc]
  );

  const creditDeposit = useCallback(
    async (hash: string, { retries = 8 }: { retries?: number } = {}) => {
      const key = hash.toLowerCase();
      if (creditedHashes.current.has(key)) return;
      if (creditInFlight.current === key) return;
      creditInFlight.current = key;
      setBusy(true);
      setSubmittedHash(hash);
      setManualHash(hash);
      setPhase("Crediting Arena64 Account…");
      let lastErr: unknown;
      try {
        // Skip hammering known-phantom hashes: if RPC has no tx, go straight to sync.
        if (publicClient) {
          try {
            const tx = await publicClient.getTransaction({ hash: hash as Hex });
            if (!tx) {
              setPhase("Hash not on-chain — scanning treasury transfers…");
              if (await trySyncCredit()) return;
              setMsg(
                "That hash never landed on Injective. Your USDC is likely still in your Connected Wallet — try Deposit again, or Sync deposits after a successful Blockscout transfer."
              );
              setPhase("");
              return;
            }
          } catch {
            /* continue with normal retries */
          }
        }

        for (let i = 0; i < retries; i++) {
          try {
            const res = await api<{ credited_usdc: number; available_usdc: number }>(
              "/api/wallet/deposit",
              {
                method: "POST",
                body: JSON.stringify({ tx_hash: hash }),
              }
            );
            creditedHashes.current.add(key);
            setMsg(
              `Credited to Arena64 Account · +${res.credited_usdc} USDC · Available: ${res.available_usdc}`
            );
            setPhase("Done");
            await refresh();
            return;
          } catch (e: unknown) {
            lastErr = e;
            const text = e instanceof Error ? e.message.toLowerCase() : String(e).toLowerCase();
            if (text.includes("already recorded") || text.includes("already credited")) {
              creditedHashes.current.add(key);
              setMsg("This transfer was already credited to your Arena64 Account.");
              setPhase("Done");
              await refresh().catch(() => undefined);
              return;
            }
            if (text.includes("still in your wallet") || text.includes("no usdc transfer to the arena64")) {
              break;
            }
            const retryable =
              text.includes("not found") ||
              text.includes("not yet mined") ||
              text.includes("verify again") ||
              text.includes("could not fetch") ||
              text.includes("timeout") ||
              text.includes("network");
            if (!retryable || i === retries - 1) break;
            setPhase(`Waiting for chain receipt… (${i + 1}/${retries})`);
            await sleep(2500 + i * 400);
          }
        }
        try {
          setPhase("Scanning treasury transfers…");
          if (await trySyncCredit()) return;
        } catch {
          /* fall through */
        }
        setMsg(formatWalletError(lastErr, "deposit"));
        setPhase("");
      } finally {
        if (creditInFlight.current === key) creditInFlight.current = null;
        setBusy(false);
      }
    },
    [refresh, publicClient, trySyncCredit]
  );

  async function depositOnchain() {
    setMsg("");
    setSubmittedHash("");
    if (!cfg?.treasury_address) {
      setMsg("Deposits are temporarily unavailable. Please try again later.");
      return;
    }
    if (!cfg.usdc_address) {
      setMsg("Deposits are temporarily unavailable. Please try again later.");
      return;
    }
    if (!isConnected || !address) {
      setMsg("Connect the same wallet you signed in with.");
      return;
    }
    if (user?.wallet_address && address.toLowerCase() !== user.wallet_address.toLowerCase()) {
      setMsg("Connected wallet must match your Arena64 login.");
      return;
    }
    if (chainId == null || chainId !== INJECTIVE_CHAIN_ID) {
      setMsg("Switch your wallet to Injective EVM Testnet, then try again.");
      return;
    }
    if (!publicClient || !walletClient) {
      setMsg("Wallet not ready. Reconnect MetaMask and try again.");
      return;
    }
    const value = Number(amount);
    if (!value || value <= 0) {
      setMsg("Enter a positive USDC amount.");
      return;
    }
    const amountMicro = parseUnits(String(value), 6);
    const balanceBefore = await readUsdcBalance();

    try {
      setBusy(true);
      setPhase("Approve in MetaMask…");
      const result = await sendUsdcDepositToTreasury({
        publicClient,
        walletClient,
        account: address,
        chainId,
        usdcAddress: cfg.usdc_address as `0x${string}`,
        treasuryAddress: cfg.treasury_address as `0x${string}`,
        amountMicro,
      });
      setSubmittedHash(result.hash);
      setManualHash(result.hash);
      setBusy(false);

      if (result.confirmed) {
        setMsg("Transfer confirmed on-chain — crediting Arena64 Account…");
        await creditDeposit(result.hash, { retries: 6 });
      } else {
        setMsg("Waiting for USDC to settle — recovering via treasury sync…");
        await waitForOnchainCredit({ hash: result.hash, amountMicro, balanceBefore });
      }
    } catch (e: unknown) {
      setBusy(false);
      const recovered = extractTxHash(e);
      if (recovered) {
        setSubmittedHash(recovered);
        setManualHash(recovered);
        setMsg("Wallet reported an error, but a tx hash was found — verifying on-chain…");
        await waitForOnchainCredit({ hash: recovered, amountMicro, balanceBefore });
        return;
      }
      setMsg(formatWalletError(e, "deposit"));
      setPhase("");
    }
  }

  async function submitManual() {
    if (!manualHash.trim().startsWith("0x") || manualHash.trim().length !== 66) {
      setMsg("Paste a full 0x transaction hash (66 chars).");
      return;
    }
    await creditDeposit(manualHash.trim());
  }

  async function fundCctp() {
    try {
      if (!cctpHash.trim()) {
        setMsg("Enter a CCTP burn tx hash.");
        return;
      }
      setPhase("Verifying CCTP…");
      const res = await api<{ available_usdc?: number }>("/api/wallet/cctp/deposit", {
        method: "POST",
        body: JSON.stringify({
          burn_tx_hash: cctpHash.trim(),
          source_domain: 6,
          amount_usdc: Number(cctpAmount) || 25,
          attestation: cctpAttest.trim() || undefined,
        }),
      });
      setMsg(`CCTP credited to Arena64 Account · Available: ${res.available_usdc ?? "—"}`);
      setPhase("Done");
      await refresh();
    } catch (e: unknown) {
      setMsg(formatWalletError(e, "deposit"));
      setPhase("");
    }
  }

  async function doWithdraw() {
    setMsg("");
    const value = Number(withdrawAmt);
    if (!value || value <= 0) {
      setMsg("Enter a positive withdraw amount.");
      return;
    }
    setBusy(true);
    try {
      const res = await api<{ tx_hash?: string; available_usdc?: number }>("/api/wallet/withdraw", {
        method: "POST",
        body: JSON.stringify({ amount_usdc: value, to_address: address || user?.wallet_address }),
      });
      setMsg(`Withdrawn to Connected Wallet · Available: ${res.available_usdc ?? "—"}`);
      await refresh();
    } catch (e: unknown) {
      setMsg(formatWalletError(e, "withdraw"));
    } finally {
      setBusy(false);
    }
  }

  const network = String(cfg?.network || "testnet");
  const explorer = cfg?.explorer_url || "https://testnet.blockscout.injective.network";
  const available = bal?.available_usdc ?? user?.available_usdc ?? user?.usdc_balance ?? 0;
  const locked = bal?.locked_usdc ?? user?.locked_usdc ?? 0;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Arena64 Account</p>
      <h1 className="led-title mt-2 text-5xl">Arena64 Balance</h1>
      <p className="mt-3 text-[var(--floodlight)]/65">
        Move USDC from your Connected Wallet into your Arena64 Account. Agents spend from this balance —
        not from your chain wallet mid-match.
      </p>
      <p className="mt-2 inline-block border border-[var(--trophy-gold)]/40 px-3 py-1 text-xs uppercase tracking-widest text-[var(--trophy-gold)]">
        {network} · chain {String(cfg?.chain_id ?? "—")}
        {chainId ? ` · wallet ${chainId}` : ""}
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 chalk-line pitch-surface p-6">
        <div>
          <p className="text-xs uppercase opacity-50">Connected Wallet</p>
          <p className="mt-1 font-mono text-sm">{shortAddress || user?.wallet_address || "—"}</p>
          <p className="mt-2 text-xs text-[var(--floodlight)]/55">
            On-chain USDC: {walletUsdc == null ? "—" : walletUsdc.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase opacity-50">Arena64 Balance</p>
          <p className="led-title text-3xl">{(Number(available) + Number(locked)).toFixed(2)}</p>
          <p className="mt-1 text-xs text-[var(--floodlight)]/55">
            Available {Number(available).toFixed(2)} · Locked {Number(locked).toFixed(2)}
          </p>
        </div>
      </div>

      <div className="mt-8 space-y-4 border border-[var(--trophy-gold)]/30 p-5">
        <p className="led-title text-2xl text-[var(--trophy-gold)]">Fund Arena64 Account</p>
        <p className="text-sm font-mono text-[var(--floodlight)]/55">
          Connected Wallet → Arena64 Treasury → Arena64 Account (Available ↑)
        </p>
        <div className="flex gap-2 text-xs uppercase tracking-wider">
          <button
            type="button"
            onClick={() => setSource("injective")}
            className={`btn-press btn-tap px-3 py-2 ${source === "injective" ? "bg-[var(--trophy-gold)] text-[var(--night-sky)]" : "border border-white/20"}`}
          >
            On Injective
          </button>
          <button
            type="button"
            onClick={() => setSource("cctp")}
            className={`btn-press btn-tap px-3 py-2 ${source === "cctp" ? "bg-[var(--trophy-gold)] text-[var(--night-sky)]" : "border border-white/20"}`}
          >
            From another chain (CCTP)
          </button>
        </div>

        {source === "injective" ? (
          <>
            <p className="text-sm text-[var(--floodlight)]/60">
              Get USDC from the{" "}
              <a
                className="underline"
                href={cfg?.external_faucets?.circle || "https://faucet.circle.com/"}
                target="_blank"
                rel="noreferrer"
              >
                Circle faucet
              </a>{" "}
              and testnet INJ for gas from{" "}
              <Link className="underline" href="/claim">
                Claim 1 INJ on Arena64
              </Link>{" "}
              (one per wallet) or the{" "}
              <a
                className="underline"
                href={cfg?.external_faucets?.injective || INJECTIVE_TESTNET_FAUCET}
                target="_blank"
                rel="noreferrer"
              >
                Injective faucet
              </a>
              , then deposit. Watch Connected Wallet USDC drop — if it does not, the transfer never mined.
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-xs uppercase tracking-wider opacity-60">
                Amount
                <input
                  className="w-28 border border-white/20 bg-transparent px-3 py-2 text-sm text-[var(--floodlight)]"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </label>
              <button
                type="button"
                disabled={busy || !cfg?.treasury_address}
                onClick={depositOnchain}
                className="btn-press btn-tap bg-[var(--trophy-gold)] px-5 py-3 text-sm font-semibold uppercase text-[var(--night-sky)] disabled:opacity-40"
              >
                {busy ? "Confirming…" : "Deposit to Arena64 Account"}
              </button>
            </div>
            {phase && <p className="text-xs text-[var(--trophy-gold)]/80">{phase}</p>}
            {(submittedHash || manualHash) && (
              <p className="text-xs break-all opacity-70">
                Tx:{" "}
                <a
                  className="underline"
                  href={`${explorer}/tx/${submittedHash || manualHash}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {submittedHash || manualHash}
                </a>
              </p>
            )}
            <details className="border-t border-white/10 pt-4" open={Boolean(manualHash || submittedHash)}>
              <summary className="cursor-pointer text-xs uppercase tracking-widest opacity-50">
                Already sent USDC to treasury?
              </summary>
              <p className="mt-2 text-xs text-[var(--floodlight)]/50">
                If MetaMask says failed but the explorer shows success, paste the hash here to credit your account.
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <input
                  className="min-w-[16rem] flex-1 border border-white/20 bg-transparent px-3 py-2 text-sm font-mono"
                  placeholder="0x… tx hash"
                  value={manualHash}
                  onChange={(e) => setManualHash(e.target.value)}
                />
                <button
                  type="button"
                  disabled={busy}
                  onClick={submitManual}
                  className="btn-press btn-tap border border-[var(--turf-line)] px-4 py-2 text-xs uppercase"
                >
                  Verify & credit account
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setBusy(true);
                    setPhase("Scanning treasury transfers…");
                    syncDeposits()
                      .catch(() => undefined)
                      .finally(() => {
                        setBusy(false);
                        setPhase((p) => (p === "Scanning treasury transfers…" ? "" : p));
                      });
                  }}
                  className="btn-press btn-tap border border-[var(--trophy-gold)]/50 px-4 py-2 text-xs uppercase text-[var(--trophy-gold)]"
                >
                  Sync deposits
                </button>
              </div>
            </details>
          </>
        ) : (
          <div className="space-y-3">
            <input
              className="w-full bg-transparent border border-white/20 px-3 py-2 text-sm"
              placeholder="Burn tx hash"
              value={cctpHash}
              onChange={(e) => setCctpHash(e.target.value)}
            />
            <input
              className="w-full bg-transparent border border-white/20 px-3 py-2 text-sm"
              placeholder="Iris attestation"
              value={cctpAttest}
              onChange={(e) => setCctpAttest(e.target.value)}
            />
            <input
              className="w-full bg-transparent border border-white/20 px-3 py-2 text-sm"
              placeholder="Amount USDC"
              value={cctpAmount}
              onChange={(e) => setCctpAmount(e.target.value)}
            />
            <button
              type="button"
              onClick={fundCctp}
              className="btn-press btn-tap bg-[var(--trophy-gold)] px-5 py-3 uppercase text-sm font-semibold text-[var(--night-sky)]"
            >
              Deposit to Arena64 Account via CCTP
            </button>
          </div>
        )}
      </div>

      <div className="mt-8 space-y-3 border border-white/10 p-5">
        <p className="led-title text-xl">Return USDC to Connected Wallet</p>
        <p className="text-sm text-[var(--floodlight)]/55">
          Withdraws from Available only. Locked funds stay until the tournament ends.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs uppercase tracking-wider opacity-60">
            Amount
            <input
              className="w-28 border border-white/20 bg-transparent px-3 py-2 text-sm"
              value={withdrawAmt}
              onChange={(e) => setWithdrawAmt(e.target.value)}
            />
          </label>
          <button
            type="button"
            disabled={busy || !cfg?.withdraw_enabled}
            onClick={doWithdraw}
            className="btn-press btn-tap border border-[var(--kit-home)] px-5 py-3 text-sm uppercase disabled:opacity-40"
          >
            Withdraw
          </button>
        </div>
        {!cfg?.withdraw_enabled && (
          <p className="text-xs opacity-50">
            Withdrawals need the Arena64 treasury hot-wallet private key configured on the API
            (`ARENA64_TREASURY_PRIVATE_KEY`, matching `ARENA64_TREASURY_ADDRESS`).
          </p>
        )}
      </div>

      <div className="mt-8">
        <p className="text-xs uppercase tracking-widest opacity-50 mb-3">Activity</p>
        <ul className="space-y-2 text-sm">
          {txs.map((t) => (
            <li key={t.id} className="flex justify-between border-b border-white/5 py-2 font-mono text-xs">
              <span>{t.type}</span>
              <span>
                {t.amount_usdc > 0 ? "+" : ""}
                {t.amount_usdc} · {new Date(t.created_at).toLocaleString()}
              </span>
            </li>
          ))}
          {!txs.length && <li className="opacity-40">No ledger rows yet.</li>}
        </ul>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link href="/dashboard" className="btn-press border border-[var(--turf-line)] px-5 py-3 uppercase text-sm">
          Dashboard
        </Link>
        <Link href="/tournaments" className="btn-press bg-[var(--kit-home)] px-5 py-3 uppercase text-sm font-semibold">
          Enter tournaments
        </Link>
      </div>

      {msg && <p className="mt-4 text-[var(--trophy-gold)]">{msg}</p>}
      {!getStoredUser() && (
        <p className="mt-4 text-[var(--whistle-red)]">Connect and sign in from the nav to fund your account.</p>
      )}
    </div>
  );
}
