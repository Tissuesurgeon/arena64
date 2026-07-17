"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAccount, useSwitchChain } from "wagmi";
import { getAddress, parseUnits, type Address, type Hex } from "viem";
import { api, getStoredUser } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ensureInjectiveChain, INJECTIVE_CHAIN_ID } from "@/lib/chain";
import {
  defaultTreasuryAddress,
  defaultUsdcAddress,
  getInjectivePublicClient,
  getMetaMaskWalletClient,
  readUsdcBalanceOf,
  watchInjectiveUsdc,
} from "@/lib/injectiveClient";
import {
  CIRCLE_FAUCET,
  INJECTIVE_TESTNET_FAUCET,
  sendUsdcDepositToTreasury,
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

function shortenHash(hash: string) {
  if (hash.length < 14) return hash;
  return `${hash.slice(0, 8)}…${hash.slice(-6)}`;
}

function formatTxType(type: string) {
  return type.replaceAll("_", " ").toLowerCase();
}

const DEPOSIT_PRESETS = ["1", "5", "10", "25"] as const;

export default function Arena64AccountPage() {
  const { user, refreshUser, shortAddress } = useAuth();
  const { address, isConnected, chainId } = useAccount();
  const { switchChainAsync } = useSwitchChain();
  const publicClient = useMemo(() => getInjectivePublicClient(), []);
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
  const [walletUsdcStatus, setWalletUsdcStatus] = useState<"idle" | "loading" | "ok" | "error">(
    "idle"
  );
  const creditedHashes = useRef<Set<string>>(new Set());
  const creditInFlight = useRef<string | null>(null);

  /** Prefer live MetaMask account; fall back to signed-in wallet for balance reads. */
  const ownerAddress = useMemo((): Address | null => {
    const raw = address || user?.wallet_address;
    if (!raw) return null;
    try {
      return getAddress(raw);
    } catch {
      return null;
    }
  }, [address, user?.wallet_address]);

  const usdcAddress = useMemo((): Address => {
    const fromCfg = cfg?.usdc_address;
    if (fromCfg) {
      try {
        return getAddress(fromCfg);
      } catch {
        /* fall through */
      }
    }
    return defaultUsdcAddress();
  }, [cfg?.usdc_address]);

  const treasuryAddress = useMemo((): Address | null => {
    const fromCfg = cfg?.treasury_address;
    if (fromCfg) {
      try {
        return getAddress(fromCfg);
      } catch {
        /* fall through */
      }
    }
    return defaultTreasuryAddress();
  }, [cfg?.treasury_address]);

  const readUsdcBalance = useCallback(async (): Promise<bigint | null> => {
    if (!ownerAddress) return null;
    try {
      return await readUsdcBalanceOf(ownerAddress, usdcAddress);
    } catch {
      return null;
    }
  }, [ownerAddress, usdcAddress]);

  const refreshWalletUsdc = useCallback(async () => {
    if (!ownerAddress) {
      setWalletUsdc(null);
      setWalletUsdcStatus("idle");
      return;
    }
    setWalletUsdcStatus("loading");
    const raw = await readUsdcBalance();
    if (raw == null) {
      setWalletUsdc(null);
      setWalletUsdcStatus("error");
      return;
    }
    setWalletUsdc(Number(raw) / 1e6);
    setWalletUsdcStatus("ok");
  }, [readUsdcBalance, ownerAddress]);

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
    api<WalletConfig>("/api/wallet/cctp/config")
      .then(setCfg)
      .catch(() => {
        // Still show balance / allow deposit via hardcoded testnet defaults
        setCfg((prev) => prev ?? { network: "testnet", chain_id: INJECTIVE_CHAIN_ID });
      });
  }, [syncDeposits]);

  useEffect(() => {
    refreshWalletUsdc().catch(() => undefined);
  }, [refreshWalletUsdc, ownerAddress, usdcAddress]);

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
    if (!treasuryAddress) {
      setMsg("Deposits are temporarily unavailable. Please try again later.");
      return;
    }
    if (!isConnected || !address) {
      setMsg("Connect the same wallet you signed in with (MetaMask must be unlocked).");
      return;
    }
    if (user?.wallet_address && address.toLowerCase() !== user.wallet_address.toLowerCase()) {
      setMsg("Connected wallet must match your Arena64 login.");
      return;
    }
    const value = Number(amount);
    if (!value || value <= 0) {
      setMsg("Enter a positive USDC amount.");
      return;
    }
    const amountMicro = parseUnits(String(value), 6);

    try {
      setBusy(true);
      // Login no longer forces Injective — switch/add network so MetaMask can pop for the transfer
      if (chainId !== INJECTIVE_CHAIN_ID) {
        setPhase("Switch to Injective in MetaMask…");
        await ensureInjectiveChain({
          currentChainId: chainId,
          switchChainAsync,
        });
        await sleep(400);
      }

      // Fresh MetaMask client after network switch (wagmi client can stay stale)
      let activeWallet;
      try {
        activeWallet = getMetaMaskWalletClient(address);
      } catch {
        setMsg("MetaMask not found. Install MetaMask, connect, then try again.");
        setBusy(false);
        setPhase("");
        return;
      }

      const balanceBefore = await readUsdcBalance();
      if (balanceBefore == null) {
        setMsg(
          "Could not read Injective USDC. Switch MetaMask to Injective EVM Testnet (1439), import the USDC token below, then retry."
        );
        setBusy(false);
        setPhase("");
        return;
      }
      if (balanceBefore < amountMicro) {
        setMsg(
          `Not enough Injective USDC (have ${(Number(balanceBefore) / 1e6).toFixed(2)}). ` +
            `At Circle faucet select Injective — Sepolia USDC will not show here.`
        );
        setBusy(false);
        setPhase("");
        return;
      }
      setPhase("Approve USDC transfer in MetaMask…");
      const result = await sendUsdcDepositToTreasury({
        publicClient,
        walletClient: activeWallet,
        account: address,
        chainId: INJECTIVE_CHAIN_ID,
        usdcAddress,
        treasuryAddress,
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
        const amountMicroRetry = parseUnits(String(Number(amount) || 0), 6);
        await waitForOnchainCredit({
          hash: recovered,
          amountMicro: amountMicroRetry,
          balanceBefore: null,
        });
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
  const totalArena = Number(available) + Number(locked);
  const onInjective = chainId === INJECTIVE_CHAIN_ID;
  const walletLabel = shortAddress || (user?.wallet_address ? shortenHash(user.wallet_address) : "—");
  const walletUsdcLabel =
    walletUsdcStatus === "loading"
      ? "…"
      : walletUsdcStatus === "error"
        ? "—"
        : walletUsdc == null
          ? "—"
          : walletUsdc.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  async function importUsdcToken() {
    try {
      await ensureInjectiveChain({ currentChainId: chainId, switchChainAsync });
      await watchInjectiveUsdc(usdcAddress);
      setMsg("Approve Import Token in MetaMask, then refresh balance.");
      await refreshWalletUsdc();
    } catch (e: unknown) {
      setMsg(formatWalletError(e, "deposit"));
    }
  }

  function runSyncDeposits() {
    setBusy(true);
    setPhase("Scanning treasury transfers…");
    syncDeposits()
      .catch(() => undefined)
      .finally(() => {
        setBusy(false);
        setPhase((p) => (p === "Scanning treasury transfers…" ? "" : p));
      });
  }

  return (
    <div className="relative mx-auto max-w-5xl px-4 py-10 sm:py-14">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-8 h-56 bg-[radial-gradient(ellipse_at_top,rgba(212,160,23,0.16),transparent_65%)]"
      />

      <header className="relative flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Treasury</p>
          <h1 className="led-title mt-1 text-5xl sm:text-6xl">Arena Wallet</h1>
          <p className="mt-2 max-w-xl text-sm text-[var(--floodlight)]/60">
            Deposit Injective USDC to your Arena64 balance. Agents spend from Available — not from MetaMask mid-match.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-2 border border-[var(--trophy-gold)]/35 bg-[var(--trophy-gold)]/10 px-3 py-1.5 text-[11px] uppercase tracking-[0.2em] text-[var(--trophy-gold)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--trophy-gold)]" />
            {network}
          </span>
          <span
            className={`inline-flex items-center gap-2 border px-3 py-1.5 text-[11px] uppercase tracking-[0.2em] ${
              onInjective
                ? "border-[var(--turf-line)] text-[var(--floodlight)]/70"
                : "border-[var(--whistle-red)]/40 text-[var(--whistle-red)]"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                onInjective ? "bg-[var(--pitch-mid)]" : "bg-[var(--whistle-red)]"
              }`}
            />
            {isConnected
              ? onInjective
                ? `Injective · ${INJECTIVE_CHAIN_ID}`
                : `Wrong network · ${chainId ?? "—"}`
              : "Wallet disconnected"}
          </span>
        </div>
      </header>

      {!getStoredUser() && (
        <div className="relative mt-6 border border-[var(--whistle-red)]/40 bg-[var(--whistle-red)]/10 px-4 py-3 text-sm text-[var(--floodlight)]/90">
          Connect and sign in from the nav to fund your Arena64 account.
        </div>
      )}

      {msg && (
        <div
          role="status"
          className="relative mt-6 flex items-start justify-between gap-3 border border-[var(--trophy-gold)]/40 bg-[var(--trophy-gold)]/10 px-4 py-3 text-sm text-[var(--floodlight)]"
        >
          <p className="min-w-0 flex-1 leading-relaxed">{msg}</p>
          <button
            type="button"
            className="shrink-0 text-xs uppercase tracking-wider text-[var(--trophy-gold)] opacity-80 hover:opacity-100"
            onClick={() => setMsg("")}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Balance hero */}
      <section className="relative mt-8 overflow-hidden border border-[var(--turf-line)]">
        <div className="absolute inset-0 pitch-surface opacity-80" />
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--night-sky)]/40 via-transparent to-[var(--trophy-gold)]/5" />
        <div className="relative grid gap-0 lg:grid-cols-[1.35fr_1fr]">
          <div className="border-b border-[var(--turf-line)] p-6 sm:p-8 lg:border-b-0 lg:border-r">
            <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--floodlight)]/45">
              Arena64 balance
            </p>
            <p className="led-title mt-3 text-6xl tracking-wide text-[var(--floodlight)] sm:text-7xl">
              {totalArena.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
              <span className="ml-2 text-2xl text-[var(--trophy-gold)] sm:text-3xl">USDC</span>
            </p>
            <div className="mt-6 grid grid-cols-2 gap-3">
              <div className="border border-white/10 bg-black/20 px-4 py-3">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[var(--floodlight)]/40">Available</p>
                <p className="mt-1 font-mono text-xl tabular-nums">
                  {Number(available).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </p>
              </div>
              <div className="border border-white/10 bg-black/20 px-4 py-3">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[var(--floodlight)]/40">Locked</p>
                <p className="mt-1 font-mono text-xl tabular-nums">
                  {Number(locked).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col justify-between p-6 sm:p-8">
            <div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--floodlight)]/45">
                  Connected wallet
                </p>
                <button
                  type="button"
                  className="text-[10px] uppercase tracking-[0.18em] text-[var(--trophy-gold)]/80 hover:text-[var(--trophy-gold)]"
                  onClick={() => refreshWalletUsdc().catch(() => undefined)}
                >
                  Refresh
                </button>
              </div>
              <p className="mt-3 font-mono text-sm tracking-wide text-[var(--floodlight)]/90">{walletLabel}</p>
              <p className="led-title mt-5 text-4xl text-[var(--floodlight)]">
                {walletUsdcLabel}
                <span className="ml-2 text-lg text-[var(--floodlight)]/45">USDC</span>
              </p>
              <p className="mt-1 text-xs text-[var(--floodlight)]/45">On-chain · Injective EVM</p>
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={importUsdcToken}
                className="btn-press border border-white/15 bg-black/25 px-3 py-2 text-[10px] uppercase tracking-[0.16em] text-[var(--floodlight)]/75 hover:border-[var(--trophy-gold)]/40 hover:text-[var(--floodlight)]"
              >
                Import USDC
              </button>
              {ownerAddress && (
                <a
                  href={`${explorer}/token/${usdcAddress}?a=${ownerAddress}`}
                  target="_blank"
                  rel="noreferrer"
                  className="btn-press border border-white/15 bg-black/25 px-3 py-2 text-[10px] uppercase tracking-[0.16em] text-[var(--floodlight)]/75 hover:border-[var(--trophy-gold)]/40"
                >
                  Explorer
                </a>
              )}
              <a
                href={cfg?.external_faucets?.circle || CIRCLE_FAUCET}
                target="_blank"
                rel="noreferrer"
                className="btn-press border border-white/15 bg-black/25 px-3 py-2 text-[10px] uppercase tracking-[0.16em] text-[var(--floodlight)]/75 hover:border-[var(--trophy-gold)]/40"
              >
                Circle faucet
              </a>
              <Link
                href="/claim"
                className="btn-press border border-white/15 bg-black/25 px-3 py-2 text-[10px] uppercase tracking-[0.16em] text-[var(--floodlight)]/75 hover:border-[var(--trophy-gold)]/40"
              >
                Claim INJ
              </Link>
            </div>

            {walletUsdcStatus === "ok" && walletUsdc === 0 && (
              <p className="mt-4 text-xs leading-relaxed text-[var(--whistle-red)]/90">
                No Injective USDC yet. At Circle faucet choose Injective — Sepolia balances do not appear here.
              </p>
            )}
            {walletUsdcStatus === "error" && (
              <p className="mt-4 text-xs text-[var(--whistle-red)]/90">
                Could not read on-chain balance. Switch to Injective, then Refresh.
              </p>
            )}
          </div>
        </div>
      </section>

      {/* Transfer desk */}
      <section className="relative mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="border border-[var(--trophy-gold)]/25 bg-[var(--night-sky)]/55 p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="led-title text-3xl text-[var(--trophy-gold)]">Deposit</h2>
              <p className="mt-1 text-xs text-[var(--floodlight)]/50">
                Wallet → Treasury → Arena Available
              </p>
            </div>
            <div className="flex border border-white/10 p-0.5 text-[10px] uppercase tracking-[0.14em]">
              <button
                type="button"
                onClick={() => setSource("injective")}
                className={`btn-press px-3 py-1.5 ${
                  source === "injective"
                    ? "bg-[var(--trophy-gold)] text-[var(--night-sky)]"
                    : "text-[var(--floodlight)]/55 hover:text-[var(--floodlight)]"
                }`}
              >
                Injective
              </button>
              <button
                type="button"
                onClick={() => setSource("cctp")}
                className={`btn-press px-3 py-1.5 ${
                  source === "cctp"
                    ? "bg-[var(--trophy-gold)] text-[var(--night-sky)]"
                    : "text-[var(--floodlight)]/55 hover:text-[var(--floodlight)]"
                }`}
              >
                CCTP
              </button>
            </div>
          </div>

          {source === "injective" ? (
            <div className="mt-6 space-y-5">
              <div className="border border-white/10 bg-black/25 p-4">
                <div className="flex items-center justify-between gap-2">
                  <label className="text-[10px] uppercase tracking-[0.22em] text-[var(--floodlight)]/40">
                    Amount
                  </label>
                  <span className="text-[10px] uppercase tracking-[0.16em] text-[var(--floodlight)]/35">
                    USDC
                  </span>
                </div>
                <div className="mt-2 flex items-baseline gap-3">
                  <input
                    inputMode="decimal"
                    className="w-full bg-transparent font-mono text-4xl tabular-nums text-[var(--floodlight)] outline-none placeholder:text-white/20"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0.00"
                  />
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {DEPOSIT_PRESETS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setAmount(p)}
                      className={`btn-press border px-3 py-1.5 font-mono text-xs tabular-nums ${
                        amount === p
                          ? "border-[var(--trophy-gold)]/60 bg-[var(--trophy-gold)]/15 text-[var(--trophy-gold)]"
                          : "border-white/10 text-[var(--floodlight)]/60 hover:border-white/25"
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                  <button
                    type="button"
                    disabled={walletUsdc == null || walletUsdc <= 0}
                    onClick={() =>
                      setAmount(
                        walletUsdc != null
                          ? String(Math.floor(walletUsdc * 100) / 100)
                          : amount
                      )
                    }
                    className="btn-press border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.16em] text-[var(--floodlight)]/60 hover:border-white/25 disabled:opacity-30"
                  >
                    Max
                  </button>
                </div>
              </div>

              <button
                type="button"
                disabled={busy || !treasuryAddress || !getStoredUser()}
                onClick={depositOnchain}
                className="btn-press btn-tap w-full bg-[var(--trophy-gold)] px-5 py-4 text-sm font-semibold uppercase tracking-[0.12em] text-[var(--night-sky)] disabled:opacity-40"
              >
                {busy && phase ? phase : busy ? "Confirming…" : "Deposit USDC"}
              </button>

              {(phase || submittedHash) && (
                <div className="border border-[var(--trophy-gold)]/20 bg-[var(--trophy-gold)]/5 px-4 py-3 text-xs">
                  {phase && <p className="text-[var(--trophy-gold)]">{phase}</p>}
                  {(submittedHash || manualHash) && (
                    <p className="mt-1 font-mono text-[var(--floodlight)]/65">
                      Tx{" "}
                      <a
                        className="underline decoration-[var(--turf-line)] underline-offset-2 hover:text-[var(--floodlight)]"
                        href={`${explorer}/tx/${submittedHash || manualHash}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {shortenHash(submittedHash || manualHash)}
                      </a>
                    </p>
                  )}
                </div>
              )}

              <details
                className="border-t border-white/10 pt-4"
                open={Boolean(manualHash || submittedHash)}
              >
                <summary className="cursor-pointer text-[11px] uppercase tracking-[0.2em] text-[var(--floodlight)]/40 hover:text-[var(--floodlight)]/70">
                  Recover / verify deposit
                </summary>
                <p className="mt-3 text-xs leading-relaxed text-[var(--floodlight)]/45">
                  If MetaMask failed but Blockscout shows success, paste the hash to credit your account.
                </p>
                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                  <input
                    className="min-w-0 flex-1 border border-white/15 bg-black/30 px-3 py-2.5 font-mono text-xs text-[var(--floodlight)] outline-none focus:border-[var(--trophy-gold)]/50"
                    placeholder="0x… transaction hash"
                    value={manualHash}
                    onChange={(e) => setManualHash(e.target.value)}
                  />
                  <button
                    type="button"
                    disabled={busy}
                    onClick={submitManual}
                    className="btn-press border border-[var(--turf-line)] px-4 py-2.5 text-[10px] uppercase tracking-[0.16em]"
                  >
                    Verify
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={runSyncDeposits}
                    className="btn-press border border-[var(--trophy-gold)]/40 px-4 py-2.5 text-[10px] uppercase tracking-[0.16em] text-[var(--trophy-gold)]"
                  >
                    Sync
                  </button>
                </div>
              </details>

              <p className="text-[11px] leading-relaxed text-[var(--floodlight)]/40">
                Need funds?{" "}
                <a
                  className="text-[var(--floodlight)]/65 underline underline-offset-2 hover:text-[var(--trophy-gold)]"
                  href={cfg?.external_faucets?.circle || CIRCLE_FAUCET}
                  target="_blank"
                  rel="noreferrer"
                >
                  Circle USDC
                </a>{" "}
                (Injective) ·{" "}
                <Link className="text-[var(--floodlight)]/65 underline underline-offset-2 hover:text-[var(--trophy-gold)]" href="/claim">
                  Claim INJ
                </Link>{" "}
                ·{" "}
                <a
                  className="font-mono text-[10px] text-[var(--floodlight)]/50 underline underline-offset-2"
                  href={`${explorer}/token/${usdcAddress}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {shortenHash(usdcAddress)}
                </a>
              </p>
            </div>
          ) : (
            <div className="mt-6 space-y-3">
              <p className="text-xs text-[var(--floodlight)]/50">
                Bridge USDC via CCTP, then submit the burn hash and attestation.
              </p>
              <input
                className="w-full border border-white/15 bg-black/30 px-3 py-3 font-mono text-sm outline-none focus:border-[var(--trophy-gold)]/50"
                placeholder="Burn tx hash"
                value={cctpHash}
                onChange={(e) => setCctpHash(e.target.value)}
              />
              <input
                className="w-full border border-white/15 bg-black/30 px-3 py-3 font-mono text-sm outline-none focus:border-[var(--trophy-gold)]/50"
                placeholder="Iris attestation"
                value={cctpAttest}
                onChange={(e) => setCctpAttest(e.target.value)}
              />
              <input
                className="w-full border border-white/15 bg-black/30 px-3 py-3 font-mono text-sm outline-none focus:border-[var(--trophy-gold)]/50"
                placeholder="Amount USDC"
                value={cctpAmount}
                onChange={(e) => setCctpAmount(e.target.value)}
              />
              <button
                type="button"
                onClick={fundCctp}
                className="btn-press btn-tap w-full bg-[var(--trophy-gold)] px-5 py-4 text-sm font-semibold uppercase tracking-[0.12em] text-[var(--night-sky)]"
              >
                Credit via CCTP
              </button>
            </div>
          )}
        </div>

        <div
          id="withdraw"
          className="flex flex-col border border-white/10 bg-[var(--night-sky)]/55 p-5 sm:p-6"
        >
          <h2 className="led-title text-3xl">Withdraw</h2>
          <p className="mt-1 text-xs text-[var(--floodlight)]/50">
            Returns Available USDC to your connected wallet. Locked stays until the tournament ends.
          </p>

          <div className="mt-6 flex-1 border border-white/10 bg-black/25 p-4">
            <div className="flex items-center justify-between gap-2">
              <label className="text-[10px] uppercase tracking-[0.22em] text-[var(--floodlight)]/40">
                Amount
              </label>
              <button
                type="button"
                disabled={Number(available) <= 0}
                onClick={() =>
                  setWithdrawAmt(String(Math.floor(Number(available) * 100) / 100))
                }
                className="text-[10px] uppercase tracking-[0.16em] text-[var(--trophy-gold)]/80 hover:text-[var(--trophy-gold)] disabled:opacity-30"
              >
                Max {Number(available).toFixed(2)}
              </button>
            </div>
            <input
              inputMode="decimal"
              className="mt-2 w-full bg-transparent font-mono text-4xl tabular-nums outline-none placeholder:text-white/20"
              value={withdrawAmt}
              onChange={(e) => setWithdrawAmt(e.target.value)}
              placeholder="0.00"
            />
          </div>

          <button
            type="button"
            disabled={busy || !cfg?.withdraw_enabled || !getStoredUser()}
            onClick={doWithdraw}
            className="btn-press btn-tap mt-5 w-full border border-[var(--kit-home)] bg-[var(--kit-home)]/15 px-5 py-4 text-sm font-semibold uppercase tracking-[0.12em] text-[var(--floodlight)] disabled:opacity-40"
          >
            Withdraw to wallet
          </button>
          {!cfg?.withdraw_enabled && (
            <p className="mt-3 text-[11px] leading-relaxed text-[var(--floodlight)]/35">
              Withdrawals are offline until the treasury hot wallet is configured on the API.
            </p>
          )}

          <div className="mt-auto flex flex-wrap gap-2 pt-6">
            <Link
              href="/dashboard"
              className="btn-press border border-[var(--turf-line)] px-4 py-2.5 text-[10px] uppercase tracking-[0.16em]"
            >
              Dashboard
            </Link>
            <Link
              href="/tournaments"
              className="btn-press bg-[var(--kit-home)] px-4 py-2.5 text-[10px] font-semibold uppercase tracking-[0.16em]"
            >
              Tournaments
            </Link>
          </div>
        </div>
      </section>

      {/* Activity */}
      <section className="relative mt-6 border border-white/10">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <h2 className="text-[11px] uppercase tracking-[0.28em] text-[var(--floodlight)]/45">Activity</h2>
          <button
            type="button"
            disabled={busy || !getStoredUser()}
            onClick={() => refresh().catch(() => undefined)}
            className="text-[10px] uppercase tracking-[0.16em] text-[var(--floodlight)]/40 hover:text-[var(--trophy-gold)] disabled:opacity-30"
          >
            Refresh
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] text-left text-sm">
            <thead>
              <tr className="border-b border-white/5 text-[10px] uppercase tracking-[0.18em] text-[var(--floodlight)]/35">
                <th className="px-5 py-3 font-normal">Type</th>
                <th className="px-5 py-3 font-normal">Amount</th>
                <th className="px-5 py-3 font-normal">When</th>
                <th className="px-5 py-3 font-normal">Ref</th>
              </tr>
            </thead>
            <tbody>
              {txs.map((t) => (
                <tr key={t.id} className="border-b border-white/5 font-mono text-xs last:border-0">
                  <td className="px-5 py-3 capitalize text-[var(--floodlight)]/80">
                    {formatTxType(t.type)}
                  </td>
                  <td
                    className={`px-5 py-3 tabular-nums ${
                      t.amount_usdc >= 0 ? "text-[var(--trophy-gold)]" : "text-[var(--whistle-red)]"
                    }`}
                  >
                    {t.amount_usdc > 0 ? "+" : ""}
                    {t.amount_usdc} USDC
                  </td>
                  <td className="px-5 py-3 text-[var(--floodlight)]/45">
                    {new Date(t.created_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-[var(--floodlight)]/45">
                    {t.external_ref ? (
                      <a
                        href={`${explorer}/tx/${t.external_ref}`}
                        target="_blank"
                        rel="noreferrer"
                        className="underline underline-offset-2 hover:text-[var(--floodlight)]"
                      >
                        {shortenHash(t.external_ref)}
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
              {!txs.length && (
                <tr>
                  <td colSpan={4} className="px-5 py-10 text-center text-xs text-[var(--floodlight)]/35">
                    No ledger activity yet. Your first deposit will show here.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
