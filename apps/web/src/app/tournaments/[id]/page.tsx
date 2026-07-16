"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getStoredUser, type Tournament } from "@/lib/api";

export default function TournamentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [t, setT] = useState<Tournament | null>(null);
  const [msg, setMsg] = useState("");
  const [needDeposit, setNeedDeposit] = useState(false);

  useEffect(() => {
    if (id) api<Tournament>(`/api/tournaments/${id}`).then(setT).catch((e) => setMsg(String(e.message || e)));
  }, [id]);

  async function join() {
    if (!getStoredUser()) {
      setMsg("Connect your wallet and sign in first.");
      return;
    }
    setNeedDeposit(false);
    try {
      const res = await api<{ bracket_ready?: boolean }>(`/api/tournaments/${id}/join`, {
        method: "POST",
        body: "{}",
      });
      setMsg(
        res.bracket_ready
          ? "Joined — field full. Bracket is live; watch your agent from the lobby."
          : "Joined. Waiting for more coaches — head to the lobby."
      );
      const refreshed = await api<Tournament>(`/api/tournaments/${id}`);
      setT(refreshed);
    } catch (e: unknown) {
      const text = e instanceof Error ? e.message : String(e);
      setMsg(text);
      if (/deposit|USDC|Need |balance/i.test(text)) setNeedDeposit(true);
    }
  }

  if (!t) return <div className="p-12 text-[var(--floodlight)]/60">{msg || "Loading…"}</div>;

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Match Center</p>
      <h1 className="led-title mt-2 text-5xl">{t.name}</h1>
      <p className="mt-4 text-[var(--floodlight)]/75">{t.description}</p>
      <div className="mt-8 grid gap-4 chalk-line pitch-surface p-6 sm:grid-cols-3">
        <div>
          <p className="text-xs uppercase opacity-50">Status</p>
          <p className="led-title text-2xl">{t.status}</p>
        </div>
        <div>
          <p className="text-xs uppercase opacity-50">Squad</p>
          <p className="led-title text-2xl">
            {t.entrant_count}/{t.max_players}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase opacity-50">Entry / Pool</p>
          <p className="led-title text-2xl">
            {t.entry_fee_usdc} / {t.reward_pool_usdc} USDC
          </p>
        </div>
      </div>
      <p className="mt-4 text-sm text-[var(--floodlight)]/50">
        Entry is paid from your Arena64 ledger (funded by on-chain testnet USDC deposit).
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={join}
          className="bg-[var(--trophy-gold)] px-6 py-3 text-[var(--night-sky)] font-semibold uppercase"
        >
          Join Tournament
        </button>
        <Link href={`/tournaments/${id}/lobby`} className="border border-[var(--turf-line)] px-6 py-3 uppercase">
          Lobby
        </Link>
        <Link href={`/tournaments/${id}/bracket`} className="border border-[var(--turf-line)] px-6 py-3 uppercase">
          Bracket
        </Link>
        <Link href={`/tournaments/${id}/leaderboard`} className="border border-[var(--turf-line)] px-6 py-3 uppercase">
          Scoreboard
        </Link>
        <Link href="/wallet" className="border border-[var(--trophy-gold)]/50 px-6 py-3 uppercase text-[var(--trophy-gold)]">
          Deposit USDC
        </Link>
      </div>
      {needDeposit && (
        <p className="mt-4 text-sm">
          <Link href="/wallet" className="text-[var(--trophy-gold)] underline">
            Deposit testnet USDC
          </Link>{" "}
          then try joining again.
        </p>
      )}
      {msg && <p className="mt-4 text-sm text-[var(--trophy-gold)]">{msg}</p>}
    </div>
  );
}
