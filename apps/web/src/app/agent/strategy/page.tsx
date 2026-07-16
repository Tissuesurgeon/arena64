"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api, type Agent, type StrategyProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DEFAULTS: StrategyProfile = {
  confidence_threshold: 0.55,
  thinking_time_ms: 800,
  risk_level: "medium",
  max_mcp_calls: 2,
  premium_insight_budget: 1,
  resource_conservation: 0.5,
};

export default function StrategyPage() {
  const { user } = useAuth();
  const [form, setForm] = useState<StrategyProfile>(DEFAULTS);
  const [locked, setLocked] = useState(false);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Strategy Profile — Arena64";
    if (!user) return;
    api<Agent>("/api/agents/me")
      .then((a) => {
        if (a.strategy) {
          setForm({
            confidence_threshold: a.strategy.confidence_threshold,
            thinking_time_ms: a.strategy.thinking_time_ms,
            risk_level: a.strategy.risk_level,
            max_mcp_calls: a.strategy.max_mcp_calls,
            premium_insight_budget: a.strategy.premium_insight_budget,
            resource_conservation: a.strategy.resource_conservation,
            locked_at: a.strategy.locked_at,
            locked_tournament_id: a.strategy.locked_tournament_id,
          });
          setLocked(!!a.strategy.locked_at);
        }
      })
      .catch(() => setMsg("Create an agent first."));
  }, [user]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const s = await api<StrategyProfile>("/api/agents/me/strategy", {
        method: "PATCH",
        body: JSON.stringify({
          confidence_threshold: form.confidence_threshold,
          thinking_time_ms: form.thinking_time_ms,
          risk_level: form.risk_level,
          max_mcp_calls: form.max_mcp_calls,
          premium_insight_budget: form.premium_insight_budget,
          resource_conservation: form.resource_conservation,
        }),
      });
      setForm({ ...form, ...s });
      setMsg("Strategy saved.");
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16">
        <p className="opacity-60">Sign in to edit strategy.</p>
        <Link href="/agent" className="mt-4 inline-block text-[var(--trophy-gold)] underline">
          Agent desk
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Tactics board</p>
      <h1 className="led-title mt-2 text-5xl">Strategy profile</h1>
      <p className="mt-4 text-[var(--floodlight)]/65">
        Controls how your agent spends time, MCP research, and x402 premium budget. Locked when a
        tournament kicks off.
      </p>

      {locked && (
        <div className="mt-6 border border-[var(--whistle-red)]/40 px-4 py-3 text-sm text-[var(--whistle-red)]">
          Strategy locked for the active tournament. Edit again after the Final.
        </div>
      )}

      <form onSubmit={save} className="mt-10 space-y-8">
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/45">
            Confidence threshold ({form.confidence_threshold.toFixed(2)})
          </span>
          <input
            type="range"
            min={0.2}
            max={0.95}
            step={0.05}
            disabled={locked}
            value={form.confidence_threshold}
            onChange={(e) => setForm({ ...form, confidence_threshold: Number(e.target.value) })}
            className="mt-2 w-full"
          />
          <span className="mt-1 block text-xs text-[var(--floodlight)]/50">
            Below this, agent may seek MCP / premium help.
          </span>
        </label>

        <label className="block">
          <span className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/45">
            Thinking time ({form.thinking_time_ms} ms)
          </span>
          <input
            type="range"
            min={200}
            max={3000}
            step={100}
            disabled={locked}
            value={form.thinking_time_ms}
            onChange={(e) => setForm({ ...form, thinking_time_ms: Number(e.target.value) })}
            className="mt-2 w-full"
          />
        </label>

        <label className="block">
          <span className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/45">Risk level</span>
          <select
            disabled={locked}
            value={form.risk_level}
            onChange={(e) =>
              setForm({ ...form, risk_level: e.target.value as StrategyProfile["risk_level"] })
            }
            className="mt-2 w-full border border-[var(--turf-line)] bg-[var(--night-sky)] px-4 py-3"
          >
            <option value="low">Low — safer picks</option>
            <option value="medium">Medium</option>
            <option value="high">High — aggressive</option>
          </select>
        </label>

        <label className="block">
          <span className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/45">
            Max MCP calls / tournament
          </span>
          <input
            type="number"
            min={0}
            max={20}
            disabled={locked}
            value={form.max_mcp_calls}
            onChange={(e) => setForm({ ...form, max_mcp_calls: Number(e.target.value) })}
            className="mt-2 w-full border border-[var(--turf-line)] bg-transparent px-4 py-3"
          />
        </label>

        <label className="block">
          <span className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/45">
            Premium insight budget (x402)
          </span>
          <input
            type="number"
            min={0}
            max={10}
            disabled={locked}
            value={form.premium_insight_budget}
            onChange={(e) => setForm({ ...form, premium_insight_budget: Number(e.target.value) })}
            className="mt-2 w-full border border-[var(--turf-line)] bg-transparent px-4 py-3"
          />
        </label>

        <label className="block">
          <span className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/45">
            Resource conservation ({form.resource_conservation.toFixed(2)})
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            disabled={locked}
            value={form.resource_conservation}
            onChange={(e) => setForm({ ...form, resource_conservation: Number(e.target.value) })}
            className="mt-2 w-full"
          />
        </label>

        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={busy || locked}
            className="bg-[var(--trophy-gold)] px-8 py-3 text-sm font-semibold uppercase text-[var(--night-sky)] disabled:opacity-40"
          >
            {busy ? "Saving…" : "Save strategy"}
          </button>
          <Link href="/agent" className="border border-[var(--turf-line)] px-6 py-3 text-sm uppercase">
            Back
          </Link>
        </div>
      </form>
      {msg && <p className="mt-4 text-sm text-[var(--trophy-gold)]">{msg}</p>}
    </div>
  );
}
