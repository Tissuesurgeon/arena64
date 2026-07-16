"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, getStoredUser, type Agent, type Tournament } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const { user, shortAddress } = useAuth();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [tournamentsLoading, setTournamentsLoading] = useState(false);

  useEffect(() => {
    if (!getStoredUser()) return;
    api<Agent>("/api/agents/me")
      .then(setAgent)
      .catch(() => setAgent(null));
    setTournamentsLoading(true);
    api<Tournament[]>("/api/tournaments")
      .then(setTournaments)
      .catch(() => undefined)
      .finally(() => setTournamentsLoading(false));
  }, [user?.id]);

  const live = tournaments.find((t) =>
    ["LOBBY", "GROUP_STAGE", "ROUND_OF_16", "QUARTER_FINAL", "SEMI_FINAL", "FINAL"].includes(t.status)
  );
  const open = tournaments.find(
    (t) =>
      ["UPCOMING", "LOBBY"].includes(t.status) && t.entrant_count < t.max_players
  );
  const status = tournamentsLoading
    ? "Loading…"
    : live
      ? live.status.replaceAll("_", " ")
      : open
        ? "Open room"
        : "Idle";
  const available = user?.available_usdc ?? user?.usdc_balance ?? 0;
  const locked = user?.locked_usdc ?? 0;

  if (!user) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <h1 className="led-title text-4xl">Command Center</h1>
        <p className="mt-3 text-[var(--floodlight)]/60">Connect wallet and sign in to open your dashboard.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Command Center</p>
      <h1 className="led-title mt-2 text-5xl">Dashboard</h1>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="pitch-surface chalk-line p-5">
          <p className="text-xs uppercase opacity-50">Connected Wallet</p>
          <p className="mt-2 font-mono text-sm">{shortAddress}</p>
        </div>
        <div className="pitch-surface chalk-line p-5">
          <p className="text-xs uppercase opacity-50">Arena64 Balance</p>
          <p className="led-title mt-1 text-3xl">{Number(available).toFixed(2)}</p>
          <p className="text-xs opacity-50">Available · Locked {Number(locked).toFixed(2)}</p>
        </div>
        <div className="pitch-surface chalk-line p-5">
          <p className="text-xs uppercase opacity-50">Tournament Status</p>
          <p className="led-title mt-1 text-2xl">{status}</p>
        </div>
        <div className="pitch-surface chalk-line p-5">
          <p className="text-xs uppercase opacity-50">Agent</p>
          <p className="led-title mt-1 text-2xl">{agent?.name || "—"}</p>
        </div>
        <div className="pitch-surface chalk-line p-5">
          <p className="text-xs uppercase opacity-50">Rating</p>
          <p className="led-title mt-1 text-3xl">{agent?.arena_rating ?? 1200}</p>
        </div>
        <div className="pitch-surface chalk-line p-5">
          <p className="text-xs uppercase opacity-50">Memory</p>
          <p className="led-title mt-1 text-2xl">
            {agent?.career?.tournaments_played ?? 0} Tournaments
          </p>
        </div>
      </div>

      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/claim" className="btn-press bg-[var(--trophy-gold)] px-5 py-3 text-sm font-semibold uppercase text-[var(--night-sky)]">
          Claim 1 INJ
        </Link>
        <Link href="/wallet" className="btn-press border border-[var(--turf-line)] px-5 py-3 text-sm uppercase">
          Deposit
        </Link>
        <Link href="/wallet#withdraw" className="btn-press border border-[var(--turf-line)] px-5 py-3 text-sm uppercase">
          Withdraw
        </Link>
        <Link href="/tournaments" className="btn-press bg-[var(--kit-home)] px-5 py-3 text-sm font-semibold uppercase">
          Join Tournament
        </Link>
        {!agent && (
          <Link href="/agent" className="btn-press border border-[var(--trophy-gold)] px-5 py-3 text-sm uppercase text-[var(--trophy-gold)]">
            Create Agent
          </Link>
        )}
      </div>
    </div>
  );
}
