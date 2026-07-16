"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { api, getStoredUser } from "@/lib/api";
import { podiumLift, registerGsap } from "@/lib/gsap";

type RewardRow = {
  id: string;
  tournament_id: string;
  placement: number;
  usdc: number;
  xp: number;
  claimed: boolean;
};

export default function RewardsPage() {
  const root = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const [rewards, setRewards] = useState<RewardRow[]>([]);
  const [msg, setMsg] = useState("");

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!getStoredUser()) return;
    api<RewardRow[]>("/api/tournaments/me/rewards")
      .then(setRewards)
      .catch((e) => setMsg(e instanceof Error ? e.message : String(e)));
  }, []);

  useGSAP(
    () => {
      registerGsap();
      if (root.current) podiumLift(root.current);
    },
    { dependencies: [mounted] }
  );

  async function claim(id: string) {
    try {
      const res = await api<{ claimed: boolean; usdc: number }>(`/api/tournaments/rewards/${id}/claim`, {
        method: "POST",
      });
      setMsg(`Claimed ${res.usdc} USDC`);
      setRewards((rows) => rows.map((r) => (r.id === id ? { ...r, claimed: true } : r)));
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-3xl flex-col items-center px-4 py-16 text-center">
      <div ref={root}>
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Podium</p>
        <h1 className="led-title mt-4 text-6xl md:text-8xl text-[var(--trophy-gold)]">Champion</h1>
        <p className="mt-6 max-w-md text-[var(--floodlight)]/70">
          Reward Manager credits USDC to your Arena64 balance after the final whistle.
        </p>
        <div className="mt-10 flex justify-center gap-4">
          <div className="h-24 w-20 bg-[var(--pitch-mid)] pt-8 text-sm opacity-80">2nd</div>
          <div className="h-36 w-24 bg-[var(--trophy-gold)]/90 pt-6 text-[var(--night-sky)] font-bold">1st</div>
          <div className="h-16 w-20 bg-[var(--pitch-mid)] pt-4 text-sm opacity-80">3rd</div>
        </div>
      </div>

      <div className="mt-12 w-full max-w-lg text-left">
        <h2 className="text-xs uppercase tracking-widest opacity-50">Your rewards</h2>
        {!getStoredUser() && (
          <p className="mt-3 text-sm text-[var(--whistle-red)]">Enter the arena to view claimable rewards.</p>
        )}
        <ul className="mt-4 space-y-3">
          {rewards.map((r) => (
            <li key={r.id} className="flex items-center justify-between border border-white/10 px-4 py-3 text-sm">
              <div>
                <p>
                  #{r.placement} · {r.usdc} USDC · {r.xp} XP
                </p>
                <p className="text-xs opacity-40 truncate">{r.tournament_id}</p>
              </div>
              {r.claimed ? (
                <span className="text-xs uppercase opacity-50">Claimed</span>
              ) : (
                <button
                  type="button"
                  onClick={() => claim(r.id)}
                  className="border border-[var(--trophy-gold)] px-3 py-1 text-xs text-[var(--trophy-gold)]"
                >
                  Claim
                </button>
              )}
            </li>
          ))}
          {getStoredUser() && !rewards.length && (
            <li className="text-sm opacity-50">No rewards yet — finish a tournament first.</li>
          )}
        </ul>
        {msg && <p className="mt-4 text-sm text-[var(--trophy-gold)]">{msg}</p>}
        <Link href="/tournaments" className="mt-6 inline-block text-sm underline opacity-70">
          Back to fixtures
        </Link>
      </div>
    </div>
  );
}
