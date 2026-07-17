"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useState } from "react";
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

const CONFIDENCE_OPTIONS = [
  { value: 0.3, label: "0.30 — Low (asks for help often)" },
  { value: 0.4, label: "0.40 — Cautious" },
  { value: 0.5, label: "0.50 — Balanced" },
  { value: 0.55, label: "0.55 — Default" },
  { value: 0.65, label: "0.65 — Confident" },
  { value: 0.75, label: "0.75 — Very confident" },
  { value: 0.85, label: "0.85 — Rarely seeks help" },
  { value: 0.95, label: "0.95 — Maximum confidence" },
] as const;

const THINKING_TIME_OPTIONS = [
  { value: 200, label: "200 ms — Instant" },
  { value: 400, label: "400 ms — Fast" },
  { value: 800, label: "800 ms — Default" },
  { value: 1200, label: "1,200 ms — Deliberate" },
  { value: 1800, label: "1,800 ms — Careful" },
  { value: 2400, label: "2,400 ms — Slow" },
  { value: 3000, label: "3,000 ms — Maximum think time" },
] as const;

const RISK_OPTIONS = [
  { value: "low", label: "Low — safer picks" },
  { value: "medium", label: "Medium — balanced" },
  { value: "high", label: "High — aggressive" },
] as const;

const MCP_CALL_OPTIONS = [
  { value: 0, label: "0 — No MCP research" },
  { value: 1, label: "1 call / tournament" },
  { value: 2, label: "2 calls — Default" },
  { value: 3, label: "3 calls" },
  { value: 5, label: "5 calls" },
  { value: 8, label: "8 calls" },
  { value: 10, label: "10 calls" },
  { value: 15, label: "15 calls" },
  { value: 20, label: "20 — Maximum" },
] as const;

const PREMIUM_BUDGET_OPTIONS = [
  { value: 0, label: "0 — No x402 premium" },
  { value: 1, label: "1 — Default" },
  { value: 2, label: "2 insights" },
  { value: 3, label: "3 insights" },
  { value: 5, label: "5 insights" },
  { value: 8, label: "8 insights" },
  { value: 10, label: "10 — Maximum" },
] as const;

const CONSERVATION_OPTIONS = [
  { value: 0, label: "0.00 — Spend freely" },
  { value: 0.25, label: "0.25 — Light conservation" },
  { value: 0.5, label: "0.50 — Balanced — Default" },
  { value: 0.75, label: "0.75 — Conserve resources" },
  { value: 1, label: "1.00 — Maximum conservation" },
] as const;

const selectClass =
  "w-full cursor-pointer appearance-none border border-[var(--turf-line)] bg-[var(--night-sky)] py-3 pl-4 pr-12 text-[var(--floodlight)] outline-none transition focus:border-[var(--trophy-gold)]/60 disabled:cursor-not-allowed disabled:opacity-40";

function nearestOption<T extends number>(value: number, options: readonly { value: T }[]): T {
  let best = options[0].value;
  let bestDist = Math.abs(value - best);
  for (const opt of options) {
    const dist = Math.abs(value - opt.value);
    if (dist < bestDist) {
      best = opt.value;
      bestDist = dist;
    }
  }
  return best;
}

function DropdownField({
  label,
  hint,
  disabled,
  children,
}: {
  label: string;
  hint?: string;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/45">
        {label}
      </span>
      <div className={`relative mt-2 ${disabled ? "opacity-40" : ""}`}>
        {children}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 flex w-12 items-center justify-center text-[var(--trophy-gold)]"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="opacity-90">
            <path
              d="M3.5 6L8 10.5L12.5 6"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </div>
      {hint ? (
        <span className="mt-1 block text-xs text-[var(--floodlight)]/50">{hint}</span>
      ) : null}
    </label>
  );
}

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
            confidence_threshold: nearestOption(
              a.strategy.confidence_threshold,
              CONFIDENCE_OPTIONS
            ),
            thinking_time_ms: nearestOption(a.strategy.thinking_time_ms, THINKING_TIME_OPTIONS),
            risk_level: RISK_OPTIONS.some((o) => o.value === a.strategy?.risk_level)
              ? a.strategy.risk_level
              : "medium",
            max_mcp_calls: nearestOption(a.strategy.max_mcp_calls, MCP_CALL_OPTIONS),
            premium_insight_budget: nearestOption(
              a.strategy.premium_insight_budget,
              PREMIUM_BUDGET_OPTIONS
            ),
            resource_conservation: nearestOption(
              a.strategy.resource_conservation,
              CONSERVATION_OPTIONS
            ),
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
        Choose each setting from the menu. Controls how your agent spends time, MCP research, and
        x402 premium budget. Locked when a tournament kicks off.
      </p>

      {locked && (
        <div className="mt-6 border border-[var(--whistle-red)]/40 px-4 py-3 text-sm text-[var(--whistle-red)]">
          Strategy locked for the active tournament. Edit again after the Final.
        </div>
      )}

      <form onSubmit={save} className="mt-10 space-y-8">
        <DropdownField
          label="Confidence threshold"
          hint="Below this, the agent may seek MCP / premium help."
          disabled={locked}
        >
          <select
            disabled={locked}
            value={form.confidence_threshold}
            onChange={(e) =>
              setForm({ ...form, confidence_threshold: Number(e.target.value) })
            }
            className={selectClass}
          >
            {CONFIDENCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </DropdownField>

        <DropdownField label="Thinking time" disabled={locked}>
          <select
            disabled={locked}
            value={form.thinking_time_ms}
            onChange={(e) => setForm({ ...form, thinking_time_ms: Number(e.target.value) })}
            className={selectClass}
          >
            {THINKING_TIME_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </DropdownField>

        <DropdownField label="Risk level" disabled={locked}>
          <select
            disabled={locked}
            value={form.risk_level}
            onChange={(e) =>
              setForm({ ...form, risk_level: e.target.value as StrategyProfile["risk_level"] })
            }
            className={selectClass}
          >
            {RISK_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </DropdownField>

        <DropdownField label="Max MCP calls / tournament" disabled={locked}>
          <select
            disabled={locked}
            value={form.max_mcp_calls}
            onChange={(e) => setForm({ ...form, max_mcp_calls: Number(e.target.value) })}
            className={selectClass}
          >
            {MCP_CALL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </DropdownField>

        <DropdownField label="Premium insight budget (x402)" disabled={locked}>
          <select
            disabled={locked}
            value={form.premium_insight_budget}
            onChange={(e) =>
              setForm({ ...form, premium_insight_budget: Number(e.target.value) })
            }
            className={selectClass}
          >
            {PREMIUM_BUDGET_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </DropdownField>

        <DropdownField label="Resource conservation" disabled={locked}>
          <select
            disabled={locked}
            value={form.resource_conservation}
            onChange={(e) =>
              setForm({ ...form, resource_conservation: Number(e.target.value) })
            }
            className={selectClass}
          >
            {CONSERVATION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </DropdownField>

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
