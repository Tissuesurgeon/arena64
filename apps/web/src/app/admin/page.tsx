"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getStoredUser } from "@/lib/api";

type Stats = {
  users: number;
  tournaments: number;
  questions: number;
  knowledge_entries?: number;
  scrape_jobs?: number;
};

type ScoutResult = {
  job_id: string;
  status: string;
  pages_scraped: number;
  facts_stored: number;
  questions_created: number;
  error?: string | null;
};

type Tournament = { id: string; name: string; status: string; entrant_count: number };
type MatchRow = { id: string; stage: string; status: string; player_a_id?: string; player_b_id?: string };
type FairPlayRow = { user_id: string; score: number; needs_review?: boolean; counts?: Record<string, number> };

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [msg, setMsg] = useState("");
  const [scouting, setScouting] = useState(false);
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selectedTid, setSelectedTid] = useState("");
  const [matches, setMatches] = useState<MatchRow[]>([]);
  const [roundId, setRoundId] = useState("");
  const [fairPlay, setFairPlay] = useState<FairPlayRow[]>([]);

  async function refreshStats() {
    const s = await api<Stats>("/api/admin/stats");
    setStats(s);
  }

  const refreshTournaments = useCallback(async () => {
    const list = await api<Tournament[]>("/api/tournaments");
    setTournaments(list);
    if (!selectedTid && list[0]) setSelectedTid(list[0].id);
  }, [selectedTid]);

  async function loadMatches(tid: string) {
    if (!tid) return;
    const rows = await api<MatchRow[]>(`/api/admin/tournaments/${tid}/matches`);
    setMatches(rows);
  }

  async function loadFairPlay() {
    const rows = await api<FairPlayRow[]>("/api/admin/fair-play");
    setFairPlay(rows);
  }

  useEffect(() => {
    refreshStats().catch((e) => setMsg(String(e.message || e)));
    refreshTournaments().catch(() => undefined);
    loadFairPlay().catch(() => undefined);
  }, [refreshTournaments]);

  useEffect(() => {
    if (selectedTid) loadMatches(selectedTid).catch(() => setMatches([]));
  }, [selectedTid]);

  async function seed() {
    try {
      const res = await api<{ id: string; name: string }>("/api/admin/seed-demo-tournament", { method: "POST" });
      setMsg(`Created ${res.name} (${res.id})`);
      await refreshStats();
      await refreshTournaments();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  async function runScout() {
    setScouting(true);
    setMsg("Web Scout: DuckDuckGo + Ollama/Qwen extraction…");
    try {
      const res = await api<ScoutResult>("/api/admin/scout/run", {
        method: "POST",
        body: JSON.stringify({ topic: "world-cup" }),
      });
      setMsg(
        `Scout ${res.status}: ${res.pages_scraped} pages · ${res.facts_stored} facts · ${res.questions_created} questions` +
          (res.error ? ` · ${res.error}` : "")
      );
      await refreshStats();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setScouting(false);
    }
  }

  async function startGroups() {
    if (!selectedTid) return;
    try {
      const res = await api<{ status: string }>(`/api/tournaments/${selectedTid}/start-groups`, { method: "POST" });
      setMsg(`Groups started · status ${res.status}`);
      await loadMatches(selectedTid);
      await refreshTournaments();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  async function startMatch(matchId: string) {
    try {
      const res = await api<{ round_id: string }>(`/api/matches/${matchId}/start`, { method: "POST" });
      setRoundId(res.round_id);
      setMsg(`Match started · round ${res.round_id}`);
      await loadMatches(selectedTid);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  async function nextQuestion() {
    if (!roundId) {
      setMsg("Start a match first to get a round id.");
      return;
    }
    try {
      const res = await api<{ done?: boolean; index?: number }>(`/api/rounds/${roundId}/next`, { method: "POST" });
      setMsg(res.done ? "Round complete" : `Advanced to question index ${res.index}`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  async function finalizeRewards() {
    if (!selectedTid) return;
    try {
      const res = await api<unknown[]>(`/api/tournaments/${selectedTid}/finalize-rewards`, { method: "POST" });
      setMsg(`Finalized ${Array.isArray(res) ? res.length : 0} rewards`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  if (!getStoredUser()) return <div className="p-12">Admin requires login.</div>;

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <h1 className="led-title text-4xl">Ops Console</h1>
      <p className="mt-2 text-sm opacity-50">
        Web Scout + tournament progression. Settlement defaults to Injective testnet.
      </p>
      {stats && (
        <div className="mt-8 grid grid-cols-2 gap-4 text-center sm:grid-cols-5">
          <div className="border border-white/10 p-4">
            <p className="text-2xl">{stats.users}</p>
            <p className="text-xs opacity-50">Users</p>
          </div>
          <div className="border border-white/10 p-4">
            <p className="text-2xl">{stats.tournaments}</p>
            <p className="text-xs opacity-50">Tournaments</p>
          </div>
          <div className="border border-white/10 p-4">
            <p className="text-2xl">{stats.questions}</p>
            <p className="text-xs opacity-50">Questions</p>
          </div>
          <div className="border border-white/10 p-4">
            <p className="text-2xl">{stats.knowledge_entries ?? 0}</p>
            <p className="text-xs opacity-50">Facts</p>
          </div>
          <div className="border border-white/10 p-4">
            <p className="text-2xl">{stats.scrape_jobs ?? 0}</p>
            <p className="text-xs opacity-50">Scout jobs</p>
          </div>
        </div>
      )}

      <div className="mt-8 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={runScout}
          disabled={scouting}
          className="border border-[var(--trophy-gold)] px-4 py-2 text-sm text-[var(--trophy-gold)] disabled:opacity-50"
        >
          {scouting ? "Scouting…" : "Run Web Scout"}
        </button>
        <button type="button" onClick={seed} className="border border-white/20 px-4 py-2 text-sm">
          Seed demo tournament
        </button>
      </div>

      <section className="mt-12 border border-white/10 p-6">
        <h2 className="text-sm uppercase tracking-widest text-[var(--trophy-gold)]">Tournament ops</h2>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <select
            className="bg-transparent border border-white/20 px-3 py-2 text-sm"
            value={selectedTid}
            onChange={(e) => setSelectedTid(e.target.value)}
          >
            <option value="">Select tournament</option>
            {tournaments.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} · {t.status} · {t.entrant_count} players
              </option>
            ))}
          </select>
          <button type="button" onClick={startGroups} className="border border-white/20 px-3 py-2 text-sm">
            Start groups
          </button>
          <button type="button" onClick={nextQuestion} className="border border-white/20 px-3 py-2 text-sm">
            Next question
          </button>
          <button type="button" onClick={finalizeRewards} className="border border-white/20 px-3 py-2 text-sm">
            Finalize rewards
          </button>
        </div>
        {roundId && <p className="mt-2 text-xs opacity-50 break-all">Active round: {roundId}</p>}
        <ul className="mt-4 max-h-48 space-y-2 overflow-auto text-sm">
          {matches.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 py-2">
              <span>
                {m.stage} · {m.status}
              </span>
              <button
                type="button"
                disabled={m.status === "COMPLETED"}
                onClick={() => startMatch(m.id)}
                className="border border-[var(--kit-home)] px-2 py-1 text-xs disabled:opacity-40"
              >
                Start match
              </button>
            </li>
          ))}
          {!matches.length && <li className="opacity-40">No matches yet — start groups after players join.</li>}
        </ul>
      </section>

      <section className="mt-8 border border-white/10 p-6">
        <h2 className="text-sm uppercase tracking-widest text-[var(--trophy-gold)]">Fair Play review</h2>
        <ul className="mt-4 max-h-40 space-y-1 overflow-auto text-xs">
          {fairPlay.slice(0, 20).map((r) => (
            <li key={r.user_id} className="flex justify-between gap-2 opacity-80">
              <span className="truncate">{r.user_id.slice(0, 8)}…</span>
              <span>
                {r.score.toFixed(1)}
                {r.needs_review ? " · review" : ""}
              </span>
            </li>
          ))}
          {!fairPlay.length && <li className="opacity-40">No fair-play rows yet.</li>}
        </ul>
      </section>

      {msg && <p className="mt-4 text-sm text-amber-300">{msg}</p>}
    </div>
  );
}
