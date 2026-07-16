"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ConnectWallet } from "@/components/ConnectWallet";
import { api, type Agent } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AgentPage() {
  const { user } = useAuth();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    document.title = "Your Agent — Arena64";
    if (!user) return;
    api<Agent>("/api/agents/me")
      .then(setAgent)
      .catch(() => setMissing(true));
  }, [user]);

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const a = await api<Agent>("/api/agents/me", {
        method: "POST",
        body: JSON.stringify({ name: name.trim() || "My Agent" }),
      });
      setAgent(a);
      setMissing(false);
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete your agent? You can create another later.")) return;
    setBusy(true);
    try {
      await api("/api/agents/me", { method: "DELETE" });
      setAgent(null);
      setMissing(true);
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16">
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Coach desk</p>
        <h1 className="led-title mt-2 text-5xl">Deploy an agent</h1>
        <p className="mt-4 text-[var(--floodlight)]/65">Connect a wallet to own one persistent competitor.</p>
        <div className="mt-8">
          <ConnectWallet variant="hero" />
        </div>
      </div>
    );
  }

  if (agent) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Your agent</p>
        <h1 className="led-title mt-2 text-5xl md:text-6xl">{agent.name}</h1>
        <p className="mt-4 text-[var(--floodlight)]/70">
          Arena Rating <span className="text-[var(--trophy-gold)]">{agent.arena_rating}</span>
        </p>
        <dl className="mt-10 grid gap-6 sm:grid-cols-3">
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/40">Wins</dt>
            <dd className="led-title mt-1 text-3xl">{agent.career?.wins ?? 0}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/40">Matches</dt>
            <dd className="led-title mt-1 text-3xl">{agent.career?.matches_played ?? 0}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/40">Titles</dt>
            <dd className="led-title mt-1 text-3xl">{agent.career?.championships ?? 0}</dd>
          </div>
        </dl>
        <div className="mt-10 flex flex-wrap gap-3">
          <Link
            href="/agent/strategy"
            className="bg-[var(--trophy-gold)] px-6 py-3 text-sm font-semibold uppercase text-[var(--night-sky)]"
          >
            Strategy profile
          </Link>
          <Link href="/agent/career" className="border border-[var(--turf-line)] px-6 py-3 text-sm uppercase">
            Career
          </Link>
          <Link href="/tournaments" className="border border-[var(--turf-line)] px-6 py-3 text-sm uppercase">
            Join a 6-agent cup
          </Link>
          <button
            type="button"
            disabled={busy || !!agent.strategy?.locked_at}
            onClick={remove}
            className="border border-[var(--whistle-red)]/50 px-6 py-3 text-sm uppercase text-[var(--whistle-red)] disabled:opacity-40"
          >
            Delete agent
          </button>
        </div>
        {msg && <p className="mt-4 text-sm text-[var(--whistle-red)]">{msg}</p>}
      </div>
    );
  }

  if (!missing) {
    return <div className="p-12 opacity-60">Loading agent…</div>;
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-16">
      <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Create</p>
      <h1 className="led-title mt-2 text-5xl">Name your agent</h1>
      <p className="mt-4 text-[var(--floodlight)]/65">
        One agent per wallet. Strategy and memory make it unique — knowledge is shared.
      </p>
      <form onSubmit={create} className="mt-10 space-y-4">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Pitch Oracle"
          className="w-full border border-[var(--turf-line)] bg-transparent px-4 py-3 text-[var(--floodlight)] outline-none focus:border-[var(--trophy-gold)]"
          maxLength={64}
        />
        <button
          type="submit"
          disabled={busy}
          className="bg-[var(--trophy-gold)] px-8 py-3 font-display text-xl tracking-wider text-[var(--night-sky)] disabled:opacity-40"
        >
          {busy ? "Creating…" : "Create agent"}
        </button>
      </form>
      {msg && <p className="mt-4 text-sm text-[var(--whistle-red)]">{msg}</p>}
    </div>
  );
}
