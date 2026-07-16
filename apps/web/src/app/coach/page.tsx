"use client";

import { useEffect, useState } from "react";
import { api, getStoredUser } from "@/lib/api";

type Pack = { id: string; label: string; credits: number; price_usdc: number; x402: boolean };

export default function CoachPage() {
  const [packs, setPacks] = useState<Pack[]>([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api<{ packs: Pack[] }>("/api/coach/packs").then((d) => setPacks(d.packs)).catch(console.error);
  }, []);

  async function buy(pack: string) {
    if (!getStoredUser()) {
      setMsg("Enter arena first.");
      return;
    }
    try {
      const res = await api<{ credits_total: number; paid_via: string }>("/api/coach/packs/purchase", {
        method: "POST",
        body: JSON.stringify({ pack }),
      });
      setMsg(`Pack purchased via ${res.paid_via}. Credits: ${res.credits_total}`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <h1 className="led-title text-5xl text-[var(--trophy-gold)]">AI Coach</h1>
      <p className="mt-2 text-[var(--floodlight)]/65">
        Buy credits before kickoff with ledger USDC (deposit first). x402 preferred — never mid-match.
      </p>
      <div className="mt-10 grid gap-4 md:grid-cols-3">
        {packs.map((p) => (
          <div key={p.id} className="chalk-line pitch-surface p-6">
            <p className="led-title text-2xl">{p.label}</p>
            <p className="mt-2 text-3xl text-[var(--trophy-gold)]">{p.credits} cr</p>
            <p className="mt-1 text-sm opacity-60">{p.price_usdc} USDC · x402</p>
            <button
              type="button"
              onClick={() => buy(p.id)}
              className="mt-6 w-full bg-[var(--trophy-gold)] py-2 text-[var(--night-sky)] font-semibold uppercase"
            >
              Purchase
            </button>
          </div>
        ))}
      </div>
      {msg && <p className="mt-6 text-sm text-[var(--floodlight)]">{msg}</p>}
    </div>
  );
}