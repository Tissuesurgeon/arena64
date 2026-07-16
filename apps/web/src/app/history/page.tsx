"use client";

import { useEffect, useState } from "react";
import { api, getStoredUser } from "@/lib/api";

export default function HistoryPage() {
  const [data, setData] = useState<{ recent: { tournament_id: string; placement: number; points: number }[]; insight: string } | null>(
    null
  );

  useEffect(() => {
    if (!getStoredUser()) return;
    api<typeof data extends infer T ? NonNullable<T> : never>("/api/player/analysis").then(setData).catch(console.error);
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="led-title text-5xl">Career Sheet</h1>
      {!getStoredUser() && <p className="mt-4 opacity-60">Login required.</p>}
      {data && (
        <>
          <p className="mt-4 text-[var(--floodlight)]/70">{data.insight}</p>
          <ul className="mt-8 space-y-3">
            {data.recent.map((r) => (
              <li key={r.tournament_id + r.placement} className="chalk-line p-4 flex justify-between">
                <span className="font-mono text-sm">{r.tournament_id.slice(0, 8)}…</span>
                <span>
                  #{r.placement} · {r.points} pts
                </span>
              </li>
            ))}
            {!data.recent.length && <li className="opacity-50">No tournaments yet.</li>}
          </ul>
        </>
      )}
    </div>
  );
}