"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAccount } from "wagmi";
import { api, getStoredUser } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type FaucetStatus = {
  enabled: boolean;
  network?: string;
  chain_id?: number;
  faucet_address?: string | null;
  claim_amount_inj?: number;
  claimed?: boolean;
  faucet_balance_inj?: number;
  wallet_inj_balance?: number | null;
  explorer_url?: string;
  once_per_wallet?: boolean;
};

type ClaimResult = {
  tx_hash?: string;
  claimed?: boolean;
  explorer_url?: string;
  claim_amount_inj?: number;
};

export default function ClaimInjPage() {
  const { user, shortAddress } = useAuth();
  const { isConnected } = useAccount();
  const [status, setStatus] = useState<FaucetStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [txHash, setTxHash] = useState("");

  const refresh = useCallback(async () => {
    if (!getStoredUser()) return;
    const s = await api<FaucetStatus>("/api/faucet/inj/status");
    setStatus(s);
  }, []);

  useEffect(() => {
    refresh().catch(() => setMsg("Could not load faucet status."));
  }, [refresh, user?.id]);

  async function claim() {
    setMsg("");
    setTxHash("");
    setBusy(true);
    try {
      const res = await api<ClaimResult>("/api/faucet/inj/claim", {
        method: "POST",
        body: "{}",
      });
      setTxHash(res.tx_hash || "");
      setMsg(`Claimed ${res.claim_amount_inj ?? 1} INJ for gas. One claim per wallet.`);
      await refresh();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Claim failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Testnet gas</p>
        <h1 className="led-title mt-2 text-4xl">Claim INJ</h1>
        <p className="mt-3 text-[var(--floodlight)]/60">
          Connect your wallet and sign in to claim 1 testnet INJ for deposit gas.
        </p>
      </div>
    );
  }

  const claimed = Boolean(status?.claimed);
  const enabled = Boolean(status?.enabled);
  const explorer = status?.explorer_url || "https://testnet.blockscout.injective.network";

  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Testnet gas</p>
      <h1 className="led-title mt-2 text-5xl">Claim 1 INJ</h1>
      <p className="mt-3 text-[var(--floodlight)]/65">
        One claim per wallet — forever. Use this INJ to pay gas when depositing USDC into your Arena64
        Account.
      </p>

      <div className="mt-8 space-y-4 chalk-line pitch-surface p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs uppercase opacity-50">Connected Wallet</p>
            <p className="mt-1 font-mono text-sm">{shortAddress || user.wallet_address}</p>
            {!isConnected && (
              <p className="mt-1 text-xs text-[var(--whistle-red)]">Reconnect MetaMask if balances look stale.</p>
            )}
          </div>
          <div>
            <p className="text-xs uppercase opacity-50">Your on-chain INJ</p>
            <p className="led-title mt-1 text-3xl">
              {status?.wallet_inj_balance == null ? "—" : Number(status.wallet_inj_balance).toFixed(4)}
            </p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 border-t border-white/10 pt-4">
          <div>
            <p className="text-xs uppercase opacity-50">Faucet status</p>
            <p className="mt-1 text-sm">
              {!enabled
                ? "Not configured"
                : claimed
                  ? "Already claimed"
                  : "Ready — 1 INJ available once"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase opacity-50">Faucet balance</p>
            <p className="mt-1 font-mono text-sm">
              {status?.faucet_balance_inj == null
                ? "—"
                : `${Number(status.faucet_balance_inj).toFixed(2)} INJ`}
            </p>
          </div>
        </div>

        {status?.faucet_address && (
          <p className="text-xs break-all opacity-45">
            Contract:{" "}
            <a
              className="underline"
              href={`${explorer}/address/${status.faucet_address}`}
              target="_blank"
              rel="noreferrer"
            >
              {status.faucet_address}
            </a>
          </p>
        )}

        <button
          type="button"
          disabled={busy || !enabled || claimed}
          onClick={claim}
          className="btn-press btn-tap mt-2 bg-[var(--trophy-gold)] px-6 py-3 text-sm font-semibold uppercase text-[var(--night-sky)] disabled:opacity-40"
        >
          {busy ? "Claiming…" : claimed ? "Already claimed" : "Claim 1 INJ"}
        </button>

        {claimed && (
          <p className="text-sm text-[var(--trophy-gold)]/90">
            This wallet already claimed its 1 INJ. No second drip.
          </p>
        )}
        {!enabled && (
          <p className="text-sm text-[var(--whistle-red)]">
            Faucet is offline (missing INJ_FAUCET_ADDRESS / INJ_KEY_EVM on the API).
          </p>
        )}
        {msg && <p className="text-sm text-[var(--trophy-gold)]">{msg}</p>}
        {txHash && (
          <p className="text-xs break-all opacity-70">
            Tx:{" "}
            <a className="underline" href={`${explorer}/tx/${txHash}`} target="_blank" rel="noreferrer">
              {txHash}
            </a>
          </p>
        )}
      </div>

      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/wallet" className="btn-press bg-[var(--kit-home)] px-5 py-3 text-sm font-semibold uppercase">
          Deposit USDC
        </Link>
        <Link href="/dashboard" className="btn-press border border-[var(--turf-line)] px-5 py-3 text-sm uppercase">
          Dashboard
        </Link>
      </div>
    </div>
  );
}
