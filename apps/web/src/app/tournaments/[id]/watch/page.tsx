"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { SpectatorHud } from "@/components/SpectatorHud";
import { api } from "@/lib/api";

function WatchInner() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const roundId = search.get("round");
  const matchId = search.get("match");
  const [names, setNames] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!id) return;
    api<{
      players: { agent_id?: string | null; agent_name?: string | null }[];
    }>(`/api/tournaments/${id}/lobby`)
      .then((lob) => {
        const map: Record<string, string> = {};
        for (const p of lob.players) {
          if (p.agent_id && p.agent_name) map[p.agent_id] = p.agent_name;
        }
        setNames(map);
      })
      .catch(() => undefined);
  }, [id]);

  return (
    <SpectatorHud
      roundId={roundId}
      matchId={matchId}
      agentNames={names}
      backHref={`/tournaments/${id}/lobby`}
      emptyHint={
        <div className="mx-auto max-w-lg px-4 py-16">
          <p className="led-title text-3xl text-[var(--trophy-gold)]">Spectator</p>
          <p className="mt-4 text-[var(--floodlight)]/70">
            Open Watch from the lobby when your match is live.
          </p>
        </div>
      }
    />
  );
}

export default function WatchPage() {
  return (
    <Suspense fallback={<div className="p-12 opacity-60">Opening spectator…</div>}>
      <WatchInner />
    </Suspense>
  );
}
