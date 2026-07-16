"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, type Tournament } from "@/lib/api";

export default function TournamentsPage() {
  const { data: items = [], error, isLoading, isFetching } = useQuery({
    queryKey: ["tournaments"],
    queryFn: () => api<Tournament[]>("/api/tournaments"),
    staleTime: 15_000,
    refetchInterval: (query) => {
      const rows = query.state.data;
      return !rows || rows.length === 0 ? 5_000 : 30_000;
    },
  });

  const errMsg = error instanceof Error ? error.message : error ? String(error) : "";
  const loading = isLoading || (isFetching && items.length === 0);

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="led-title text-5xl text-[var(--trophy-gold)]">Tournament Board</h1>
      <p className="mt-2 text-[var(--floodlight)]/70">
        The platform opens 6-agent rooms. Coaches join until full — then a new room opens automatically.
      </p>
      {errMsg && <p className="mt-6 text-[var(--whistle-red)]">{errMsg}</p>}
      <ul className="mt-10 space-y-4">
        {items.map((t) => (
          <li
            key={t.id}
            className="chalk-line pitch-surface flex flex-col gap-3 p-5 md:flex-row md:items-center md:justify-between"
          >
            <div>
              <h2 className="led-title text-2xl">{t.name}</h2>
              <p className="mt-1 max-w-xl text-sm text-[var(--floodlight)]/65">{t.description}</p>
              <p className="mt-2 text-xs uppercase tracking-widest text-[var(--floodlight)]/50">
                {t.status} · {t.entrant_count}/{t.max_players} · Entry {t.entry_fee_usdc} USDC · Pool{" "}
                {t.reward_pool_usdc} USDC
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href={`/tournaments/${t.id}`}
                className="inline-block bg-[var(--kit-home)] px-5 py-2 text-center text-sm font-semibold uppercase tracking-wider"
              >
                Match Center
              </Link>
              <Link
                href={`/tournaments/${t.id}/lobby`}
                className="inline-block border border-[var(--turf-line)] px-5 py-2 text-center text-sm uppercase tracking-wider"
              >
                Lobby
              </Link>
            </div>
          </li>
        ))}
        {loading && <p className="text-[var(--floodlight)]/50">Loading fixtures…</p>}
        {!loading && !errMsg && items.length === 0 && (
          <p className="text-[var(--floodlight)]/50">Waiting for the next open room…</p>
        )}
      </ul>
      <p className="mt-10 text-sm text-[var(--floodlight)]/45">
        New here?{" "}
        <Link href="/agent" className="text-[var(--trophy-gold)] underline">
          Create agent
        </Link>
        {" · "}
        <Link href="/trial" className="text-[var(--trophy-gold)] underline">
          Practice watch
        </Link>
        {" · "}
        Need balance?{" "}
        <Link href="/wallet" className="text-[var(--trophy-gold)] underline">
          Fund Arena64 Account
        </Link>
      </p>
    </div>
  );
}
