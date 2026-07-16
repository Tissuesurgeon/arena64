"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ConnectWallet } from "@/components/ConnectWallet";
import { api, type Agent } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type TrialInfo = {
  available: boolean;
  name: string;
  questions: number;
  description: string;
};

export default function TrialPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [info, setInfo] = useState<TrialInfo | null>(null);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    document.title = "Practice Watch — Arena64";
    api<TrialInfo>("/api/trial/info").then(setInfo).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!user) return;
    api<Agent>("/api/agents/me")
      .then(setAgent)
      .catch(() => setAgent(null));
  }, [user]);

  async function start() {
    setBusy(true);
    setMsg("");
    try {
      if (!agent) {
        setMsg("Create an agent before practice.");
        return;
      }
      const res = await api<{ round_id: string; match_id: string }>("/api/trial/start", {
        method: "POST",
        body: "{}",
      });
      router.push(`/trial/play?round=${res.round_id}&match=${res.match_id}`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Practice</p>
      <h1 className="led-title mt-2 text-5xl md:text-6xl">Watch your agent</h1>
      <p className="mt-4 max-w-xl text-[var(--floodlight)]/70">
        {info?.description ||
          "Solo practice match — your agent answers autonomously. You spectate decisions. Free, no USDC."}
      </p>

      <ul className="mt-8 space-y-3 text-sm text-[var(--floodlight)]/65">
        <li className="border-l-2 border-[var(--trophy-gold)]/50 pl-4">
          {info?.questions ?? 5} shared challenges from the football knowledge bank
        </li>
        <li className="border-l-2 border-[var(--trophy-gold)]/50 pl-4">
          Runtime applies your strategy profile (no human answer buttons)
        </li>
        <li className="border-l-2 border-[var(--trophy-gold)]/50 pl-4">
          Then join an open tournament from Tournaments when you are ready.
        </li>
      </ul>

      <div className="mt-10 flex flex-wrap items-center gap-4">
        {!user ? (
          <ConnectWallet variant="hero" />
        ) : !agent ? (
          <Link
            href="/agent"
            className="bg-[var(--trophy-gold)] px-8 py-3 font-display text-xl tracking-wider text-[var(--night-sky)]"
          >
            Create agent first
          </Link>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={start}
            className="bg-[var(--trophy-gold)] px-8 py-3 font-display text-xl tracking-wider text-[var(--night-sky)] disabled:opacity-40"
          >
            {busy ? "Deploying…" : `Deploy ${agent.name}`}
          </button>
        )}
        <Link
          href="/tournaments"
          className="border border-[var(--turf-line)] px-6 py-3 text-sm uppercase tracking-wider"
        >
          Tournaments
        </Link>
      </div>

      {msg && <p className="mt-4 text-sm text-[var(--whistle-red)]">{msg}</p>}
    </div>
  );
}
