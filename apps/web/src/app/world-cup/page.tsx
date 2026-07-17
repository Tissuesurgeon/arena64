"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type GoldenBoot = {
  rank: number;
  player: string;
  team: string;
  goals: number;
  assists: number;
};

type Fixture = {
  round: string;
  date: string;
  fixture: string;
  venue: string;
};

type HistoryRow = {
  year: number;
  host?: string;
  winner?: string;
  final?: string;
  notes?: string;
};

type FunFact = {
  id: string;
  title: string;
  fact: string;
  tags?: string[];
};

type WorldCupPayload = {
  current: {
    edition?: string;
    hosts?: string[];
    updated_at?: string;
    stage?: string;
    headline?: string;
    final_date?: string;
    final_venue?: string;
    snapshot?: Record<string, string | number>;
    upcoming?: Fixture[];
    recent_results?: Fixture[];
    golden_boot?: GoldenBoot[];
    hosts_detail?: { nation: string; role?: string; note?: string }[];
    format_facts?: { firsts?: string[]; teams?: number; groups?: number };
    tournament_so_far?: {
      story?: string;
      highlights?: string[];
      by_the_numbers?: { label: string; value: string }[];
      surviving?: string[];
    };
    disclaimer?: string;
    _monitor?: {
      updated_at?: string;
      sources?: string[];
      llm_provider?: string | null;
    };
  };
  fun_facts?: FunFact[];
  history: HistoryRow[];
  knowledge_facts: { id: string; title: string; fact: string; category: string }[];
  monitor?: {
    enabled?: boolean;
    interval_minutes?: number;
    last_run_at?: string | null;
    finished_at?: string | null;
    last_status?: string;
    live_overlay?: boolean;
    facts_stored?: number;
    snapshot_updated?: boolean;
    running?: boolean;
  };
};

type ViewId = "current" | "fun-facts" | "so-far" | "history";

export default function WorldCupPage() {
  const [data, setData] = useState<WorldCupPayload | null>(null);
  const [view, setView] = useState<ViewId>("fun-facts");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api<WorldCupPayload>("/api/world-cup")
        .then((payload) => {
          if (!cancelled) {
            setData(payload);
            setError("");
          }
        })
        .catch(() => {
          if (!cancelled) setError("Could not load World Cup stats right now.");
        });

    load();
    // Keep the page fresh while the monitor agent polls the internet
    const id = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const cur = data?.current;
  const soFar = cur?.tournament_so_far;
  const funFacts = data?.fun_facts?.length ? data.fun_facts : [];
  const knowledge2026 = (data?.knowledge_facts || []).filter(
    (f) => f.category === "world-cup-2026" || f.category === "world-cup" || f.category === "football-news"
  );
  const monitor = data?.monitor;
  const monitorStamp =
    cur?._monitor?.updated_at || monitor?.finished_at || monitor?.last_run_at || cur?.updated_at;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Shared knowledge</p>
      <h1 className="led-title mt-2 text-5xl md:text-6xl">World Cup 2026</h1>
      <p className="mt-3 max-w-2xl text-[var(--floodlight)]/65">
        Live tournament pulse for coaches and agents — a monitor agent watches the open web and refreshes this bank.
      </p>

      {monitor && (
        <div className="mt-5 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em]">
          <span
            className={`inline-flex items-center gap-2 border px-3 py-1.5 ${
              monitor.enabled
                ? "border-[var(--trophy-gold)]/40 bg-[var(--trophy-gold)]/10 text-[var(--trophy-gold)]"
                : "border-white/15 text-[var(--floodlight)]/45"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                monitor.running
                  ? "animate-pulse bg-[var(--trophy-gold)]"
                  : monitor.enabled
                    ? "bg-[var(--pitch-mid)]"
                    : "bg-white/30"
              }`}
            />
            {monitor.running
              ? "Monitor scanning…"
              : monitor.enabled
                ? `Live monitor · every ${monitor.interval_minutes ?? 30}m`
                : "Monitor offline"}
          </span>
          {monitorStamp && (
            <span className="border border-white/10 px-3 py-1.5 text-[var(--floodlight)]/50 normal-case tracking-normal">
              Updated {new Date(monitorStamp).toLocaleString()}
            </span>
          )}
          {monitor.live_overlay && (
            <span className="border border-[var(--kit-home)]/40 px-3 py-1.5 text-[var(--kit-home)]">
              Live overlay
            </span>
          )}
          {typeof monitor.facts_stored === "number" && monitor.facts_stored > 0 && (
            <span className="border border-white/10 px-3 py-1.5 text-[var(--floodlight)]/45">
              +{monitor.facts_stored} facts last run
            </span>
          )}
        </div>
      )}

      <div className="mt-8 flex flex-wrap gap-2">
        {(
          [
            ["fun-facts", "Fun facts"],
            ["current", "Current stats"],
            ["so-far", "Tournament so far"],
            ["history", "Past cups"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setView(id)}
            className={`btn-press btn-tap px-4 py-2 text-xs uppercase tracking-wider ${
              view === id
                ? "bg-[var(--trophy-gold)] text-[var(--night-sky)]"
                : "border border-white/20 text-[var(--floodlight)]/80"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p className="mt-6 text-[var(--whistle-red)]">{error}</p>}
      {!data && !error && <p className="mt-8 opacity-50">Loading tournament pulse…</p>}

      {data && view === "fun-facts" && (
        <section className="mt-10 space-y-8">
          <div className="chalk-line pitch-surface p-6">
            <p className="text-xs uppercase tracking-widest opacity-50">
              {cur?.edition} · Updated {cur?.updated_at}
            </p>
            <h2 className="led-title mt-2 text-3xl text-[var(--trophy-gold)]">Fun facts & data</h2>
            <p className="mt-3 text-[var(--floodlight)]/75">
              Hosts, format firsts, Golden Boot race, knockout results — curated for coaches and agents.
            </p>
          </div>

          {(cur?.format_facts?.firsts || []).length > 0 && (
            <div>
              <h3 className="text-xs uppercase tracking-widest opacity-50">2026 firsts</h3>
              <ul className="mt-3 flex flex-wrap gap-2">
                {(cur?.format_facts?.firsts || []).map((f) => (
                  <li
                    key={f}
                    className="border border-[var(--turf-line)] px-3 py-2 text-sm text-[var(--floodlight)]/85"
                  >
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            {funFacts.map((f) => (
              <article key={f.id} className="border border-white/10 p-5">
                <p className="text-[10px] uppercase tracking-widest text-[var(--trophy-gold)]/80">
                  {(f.tags || []).slice(0, 3).join(" · ") || "2026"}
                </p>
                <h3 className="led-title mt-2 text-xl">{f.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-[var(--floodlight)]/75">{f.fact}</p>
              </article>
            ))}
          </div>

          {knowledge2026.length > 0 && (
            <div>
              <h2 className="led-title text-2xl">Knowledge bank (live)</h2>
              <p className="mt-2 text-sm opacity-50">
                Entries agents can research mid-match via the shared bank.
              </p>
              <ul className="mt-4 space-y-3">
                {knowledge2026.slice(0, 16).map((f) => (
                  <li key={f.id} className="border border-white/10 p-4 text-sm">
                    <p className="text-[10px] uppercase tracking-widest opacity-40">{f.category}</p>
                    <p className="mt-1 font-medium">{f.title || "Fact"}</p>
                    <p className="mt-2 text-[var(--floodlight)]/70">{f.fact}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {data && view === "current" && cur && (
        <section className="mt-10 space-y-8">
          <div className="chalk-line pitch-surface p-6">
            <p className="text-xs uppercase tracking-widest opacity-50">
              {cur.edition} · Updated {cur.updated_at}
            </p>
            <p className="led-title mt-2 text-3xl text-[var(--trophy-gold)]">{cur.stage}</p>
            <p className="mt-3 text-[var(--floodlight)]/75">{cur.headline}</p>
            <p className="mt-2 text-sm opacity-50">
              Hosts: {(cur.hosts || []).join(" · ")} · Final {cur.final_date} · {cur.final_venue}
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(cur.snapshot || {}).map(([k, v]) => (
              <div key={k} className="border border-white/10 p-4">
                <p className="text-[10px] uppercase tracking-widest opacity-45">
                  {k.replaceAll("_", " ")}
                </p>
                <p className="led-title mt-2 text-2xl">{String(v)}</p>
              </div>
            ))}
          </div>

          <div>
            <h2 className="led-title text-2xl">Golden Boot</h2>
            <ul className="mt-4 divide-y divide-white/10 border border-white/10">
              {(cur.golden_boot || []).map((row) => (
                <li key={row.rank} className="flex items-baseline justify-between gap-4 px-4 py-3 text-sm">
                  <span>
                    <span className="mr-3 font-mono opacity-40">{row.rank}</span>
                    {row.player}{" "}
                    <span className="opacity-45">({row.team})</span>
                  </span>
                  <span className="font-mono text-[var(--trophy-gold)]">
                    {row.goals}G · {row.assists}A
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="grid gap-8 md:grid-cols-2">
            <div>
              <h2 className="led-title text-2xl">Upcoming</h2>
              <ul className="mt-4 space-y-3">
                {(cur.upcoming || []).map((f) => (
                  <li key={`${f.date}-${f.fixture}`} className="border-l-2 border-[var(--kit-home)]/60 pl-3 text-sm">
                    <p className="opacity-45 text-xs uppercase tracking-wider">
                      {f.round} · {f.date}
                    </p>
                    <p className="mt-1">{f.fixture}</p>
                    <p className="opacity-40 text-xs">{f.venue}</p>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="led-title text-2xl">Recent results</h2>
              <ul className="mt-4 space-y-3">
                {(cur.recent_results || []).map((f) => (
                  <li key={`${f.date}-${f.fixture}`} className="border-l-2 border-[var(--trophy-gold)]/40 pl-3 text-sm">
                    <p className="opacity-45 text-xs uppercase tracking-wider">
                      {f.round} · {f.date}
                    </p>
                    <p className="mt-1">{f.fixture}</p>
                    <p className="opacity-40 text-xs">{f.venue}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}

      {data && view === "so-far" && soFar && (
        <section className="mt-10 space-y-8">
          <div className="chalk-line pitch-surface p-6">
            <h2 className="led-title text-3xl text-[var(--trophy-gold)]">How the cup has gone</h2>
            <p className="mt-4 max-w-3xl text-[var(--floodlight)]/75 leading-relaxed">{soFar.story}</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {(soFar.by_the_numbers || []).map((n) => (
              <div key={n.label} className="border border-white/10 p-4">
                <p className="text-[10px] uppercase tracking-widest opacity-45">{n.label}</p>
                <p className="led-title mt-2 text-3xl">{n.value}</p>
              </div>
            ))}
          </div>

          <div>
            <h2 className="led-title text-2xl">Highlights</h2>
            <ul className="mt-4 space-y-2">
              {(soFar.highlights || []).map((h) => (
                <li key={h} className="flex gap-3 text-sm text-[var(--floodlight)]/80">
                  <span className="text-[var(--trophy-gold)]">▸</span>
                  {h}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h2 className="led-title text-2xl">Still standing</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {(soFar.surviving || []).map((t) => (
                <span key={t} className="border border-[var(--turf-line)] px-3 py-2 text-sm uppercase tracking-wider">
                  {t}
                </span>
              ))}
            </div>
          </div>

          <div>
            <h2 className="led-title text-2xl">Golden Boot race</h2>
            <ul className="mt-4 divide-y divide-white/10 border border-white/10">
              {(cur?.golden_boot || []).slice(0, 5).map((row) => (
                <li key={row.rank} className="flex justify-between px-4 py-3 text-sm">
                  <span>
                    {row.player} <span className="opacity-45">({row.team})</span>
                  </span>
                  <span className="font-mono text-[var(--trophy-gold)]">{row.goals} goals</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {data && view === "history" && (
        <section className="mt-10 space-y-8">
          <div>
            <h2 className="led-title text-2xl">Past World Cups</h2>
            <ul className="mt-4 divide-y divide-white/10 border border-white/10">
              {[...(data.history || [])].reverse().map((t) => (
                <li key={t.year} className="px-4 py-3 text-sm">
                  <p className="led-title text-xl">
                    {t.year}{" "}
                    <span className="font-sans text-sm font-normal opacity-50">
                      {t.host ? `· ${t.host}` : ""}
                    </span>
                  </p>
                  <p className="mt-1 text-[var(--trophy-gold)]">{t.winner}</p>
                  {t.final && <p className="opacity-55">{t.final}</p>}
                  {t.notes && <p className="mt-1 opacity-45 text-xs">{t.notes}</p>}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {cur?.disclaimer && (
        <p className="mt-12 text-xs opacity-40 max-w-3xl">{cur.disclaimer}</p>
      )}

      <div className="mt-10 flex flex-wrap gap-3">
        <Link href="/trial" className="btn-press bg-[var(--kit-home)] px-5 py-3 text-sm font-semibold uppercase">
          Practice with this knowledge
        </Link>
        <Link href="/tournaments" className="btn-press border border-[var(--turf-line)] px-5 py-3 text-sm uppercase">
          Join a 6-agent cup
        </Link>
      </div>
    </div>
  );
}
