"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { SpectatorHud } from "@/components/SpectatorHud";

function TrialPlayInner() {
  const search = useSearchParams();
  const roundId = search.get("round");
  const matchId = search.get("match");

  return (
    <SpectatorHud
      roundId={roundId}
      matchId={matchId}
      trial
      backHref="/trial"
      emptyHint={
        <div className="mx-auto max-w-lg px-4 py-16">
          <p className="led-title text-3xl text-[var(--trophy-gold)]">Practice spectator</p>
          <p className="mt-4 text-[var(--floodlight)]/70">Start a practice match from Trial.</p>
        </div>
      }
    />
  );
}

export default function TrialPlayPage() {
  return (
    <Suspense fallback={<div className="p-12 opacity-60">Opening practice…</div>}>
      <TrialPlayInner />
    </Suspense>
  );
}
