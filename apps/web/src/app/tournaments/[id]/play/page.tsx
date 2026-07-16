"use client";

import { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { SpectatorHud } from "@/components/SpectatorHud";

function PlayInner() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const roundId = search.get("round");
  const matchId = search.get("match");

  return (
    <SpectatorHud
      roundId={roundId}
      matchId={matchId}
      backHref={`/tournaments/${id}/lobby`}
      emptyHint={
        <div className="mx-auto max-w-lg px-4 py-16">
          <p className="led-title text-3xl text-[var(--trophy-gold)]">Spectator</p>
          <p className="mt-4 text-[var(--floodlight)]/70">
            Use Watch from the lobby — human MCQ play has been removed.
          </p>
        </div>
      }
    />
  );
}

export default function PlayPage() {
  return (
    <Suspense fallback={<div className="p-12 opacity-60">Loading…</div>}>
      <PlayInner />
    </Suspense>
  );
}
