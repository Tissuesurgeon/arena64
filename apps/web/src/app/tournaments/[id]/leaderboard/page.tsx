"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Row = { user_id: string; points: number; wins: number; placement: number | null };

export default function LeaderboardPage() {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    if (!id) return;
    const load = () => api<Row[]>(`/api/tournaments/${id}/leaderboard`).then(setRows).catch(console.error);
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [id]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="led-title text-5xl text-[var(--trophy-gold)]">LIVE Scoreboard</h1>
      <table className="mt-8 w-full text-left text-sm">
        <thead className="border-b border-[var(--turf-line)] text-xs uppercase tracking-widest opacity-50">
          <tr>
            <th className="py-2">#</th>
            <th>Player</th>
            <th>Wins</th>
            <th>Points</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.user_id} className="border-b border-[var(--turf-line)]/40">
              <td className="py-3 text-[var(--trophy-gold)]">{r.placement || i + 1}</td>
              <td className="font-mono">{r.user_id.slice(0, 10)}…</td>
              <td>{r.wins}</td>
              <td className="led-title text-xl">{r.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="mt-6 opacity-50">No scores yet.</p>}
    </div>
  );
}