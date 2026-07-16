"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, getStoredUser, type User } from "@/lib/api";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!getStoredUser()) return;
    api<User>("/api/users/me").then(setUser).catch(() => setUser(getStoredUser()));
  }, []);

  if (!user) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <p className="led-title text-3xl text-[var(--trophy-gold)]">Player Card</p>
        <p className="mt-4 text-[var(--floodlight)]/65">Connect your wallet and sign in to view your card.</p>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Player Card</p>
      <h1 className="led-title mt-2 text-5xl">{user.display_name}</h1>
      <p className="mt-2 font-mono text-sm opacity-50">{user.wallet_address}</p>
      <div className="mt-8 grid grid-cols-2 gap-4 chalk-line pitch-surface p-6">
        <div>
          <p className="text-xs uppercase opacity-50">XP</p>
          <p className="led-title text-3xl">{user.xp}</p>
        </div>
        <div>
          <p className="text-xs uppercase opacity-50">Fair Play</p>
          <p className="led-title text-3xl">{user.fair_play_score.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-xs uppercase opacity-50">USDC</p>
          <p className="led-title text-3xl">{user.usdc_balance}</p>
        </div>
        <div>
          <p className="text-xs uppercase opacity-50">Coach</p>
          <p className="led-title text-3xl">{user.coach_credits}</p>
        </div>
      </div>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/wallet" className="bg-[var(--trophy-gold)] px-5 py-3 text-sm font-semibold uppercase text-[var(--night-sky)]">
          Deposit USDC
        </Link>
        <Link href="/tournaments" className="border border-[var(--turf-line)] px-5 py-3 text-sm uppercase">
          Tournaments
        </Link>
      </div>
    </div>
  );
}
