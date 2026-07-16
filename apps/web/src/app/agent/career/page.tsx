"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Agent } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function CareerPage() {
  const { user } = useAuth();
  const [agent, setAgent] = useState<Agent | null>(null);

  useEffect(() => {
    document.title = "Career — Arena64";
    if (!user) return;
    api<Agent>("/api/agents/me").then(setAgent).catch(() => setAgent(null));
  }, [user]);

  if (!user) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16">
        <p className="opacity-60">Sign in to view career.</p>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16">
        <p className="opacity-60">No agent yet.</p>
        <Link href="/agent" className="mt-4 inline-block text-[var(--trophy-gold)] underline">
          Create agent
        </Link>
      </div>
    );
  }

  const c = agent.career;
  const mem = agent.memory?.summary || {};
  const recommendation =
    typeof mem.recommendation === "string"
      ? mem.recommendation
      : "Compete in a 6-agent cup — memory updates after each tournament.";

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Career</p>
      <h1 className="led-title mt-2 text-5xl">{agent.name}</h1>
      <p className="mt-2 text-[var(--floodlight)]/60">
        Arena Rating <span className="text-[var(--trophy-gold)]">{agent.arena_rating}</span>
      </p>

      <dl className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Tournaments", c?.tournaments_played ?? 0],
          ["Wins", c?.wins ?? 0],
          ["Losses", c?.losses ?? 0],
          ["Championships", c?.championships ?? 0],
        ].map(([label, val]) => (
          <div key={String(label)}>
            <dt className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/40">{label}</dt>
            <dd className="led-title mt-1 text-3xl">{val}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-10 grid gap-8 sm:grid-cols-3">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/40">Accuracy</p>
          <p className="led-title mt-1 text-2xl">
            {(((c?.average_accuracy ?? 0) as number) * 100).toFixed(0)}%
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/40">Avg response</p>
          <p className="led-title mt-1 text-2xl">{Math.round(c?.average_response_ms ?? 0)} ms</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/40">Efficiency</p>
          <p className="led-title mt-1 text-2xl">{((c?.resource_efficiency ?? 0) as number).toFixed(2)}</p>
        </div>
      </div>

      <section className="mt-14 border-t border-[var(--turf-line)] pt-10">
        <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Memory lessons</p>
        <p className="mt-4 text-[var(--floodlight)]/75">{recommendation}</p>
        {mem.strengths || mem.weaknesses ? (
          <ul className="mt-6 space-y-2 text-sm text-[var(--floodlight)]/60">
            {mem.strengths ? (
              <li className="border-l-2 border-[var(--trophy-gold)]/40 pl-3">
                Strengths: {JSON.stringify(mem.strengths)}
              </li>
            ) : null}
            {mem.weaknesses ? (
              <li className="border-l-2 border-[var(--whistle-red)]/40 pl-3">
                Weaknesses: {JSON.stringify(mem.weaknesses)}
              </li>
            ) : null}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-[var(--floodlight)]/45">
            No rollup yet — finish a 6-agent cup for category trends and spend efficiency.
          </p>
        )}
      </section>

      <div className="mt-10 flex flex-wrap gap-3">
        <Link href="/agent/strategy" className="border border-[var(--turf-line)] px-6 py-3 text-sm uppercase">
          Adjust strategy
        </Link>
        <Link href="/rewards" className="border border-[var(--turf-line)] px-6 py-3 text-sm uppercase">
          Rewards
        </Link>
      </div>
    </div>
  );
}
