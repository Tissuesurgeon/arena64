"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { api } from "@/lib/api";
import { gsap, registerGsap } from "@/lib/gsap";

type QuestionPayload = {
  done?: boolean;
  winner_id?: string | null;
  round_id?: string;
  index?: number;
  total?: number;
  seconds?: number;
  memory_seconds?: number;
  user_answered?: boolean;
  question?: {
    id: string;
    challenge_type: string;
    prompt: string;
    media_url?: string | null;
    memory_payload?: { title: string; facts: string[]; display_seconds: number };
    options: { id: string; label: string }[];
  };
};

type DecisionLog = {
  id: string;
  agent_id: string;
  match_id: string;
  question_id: string;
  option_id: string | null;
  confidence: number;
  used_mcp: boolean;
  used_premium: boolean;
  used_coach_credit: boolean;
  reasoning: string;
  latency_ms: number;
  accelerated: boolean;
  created_at: string;
};

type SpectatorHudProps = {
  roundId: string | null;
  matchId?: string | null;
  agentNames?: Record<string, string>;
  trial?: boolean;
  emptyHint?: React.ReactNode;
  backHref?: string;
};

export function SpectatorHud({
  roundId,
  matchId,
  agentNames = {},
  trial = false,
  emptyHint,
  backHref,
}: SpectatorHudProps) {
  const [payload, setPayload] = useState<QuestionPayload | null>(null);
  const [decisions, setDecisions] = useState<DecisionLog[]>([]);
  const [scores, setScores] = useState<{ a: number; b: number } | null>(null);
  const [loadError, setLoadError] = useState("");
  const [phase, setPhase] = useState<"memory" | "question">("question");
  const [secondsLeft, setSecondsLeft] = useState(20);
  const root = useRef<HTMLDivElement>(null);
  const questionIndexRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    if (!roundId) return;
    try {
      const data = await api<QuestionPayload>(`/api/rounds/${roundId}/current`);
      setPayload(data);
      setLoadError("");
      const q = data.question;
      const same = questionIndexRef.current === (data.index ?? null);
      if (q && !same) {
        questionIndexRef.current = data.index ?? null;
        const hasMemory = q.challenge_type === "MEMORY" && !!q.memory_payload;
        if (hasMemory && !data.user_answered) {
          setPhase("memory");
          setSecondsLeft(data.memory_seconds || 10);
        } else {
          setPhase("question");
          setSecondsLeft(data.seconds || 20);
        }
      }
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : String(e));
    }
    if (matchId) {
      try {
        const logs = await api<DecisionLog[]>(`/api/agents/matches/${matchId}/decisions`);
        setDecisions(logs);
      } catch {
        /* optional */
      }
      try {
        const m = await api<{ score_a: number; score_b: number }>(`/api/matches/${matchId}`);
        setScores({ a: m.score_a, b: m.score_b });
      } catch {
        /* optional */
      }
    }
  }, [roundId, matchId]);

  useEffect(() => {
    if (!roundId) return;
    refresh();
    const t = setInterval(() => refresh(), 2000);
    return () => clearInterval(t);
  }, [roundId, refresh]);

  useEffect(() => {
    if (phase !== "question" && phase !== "memory") return;
    if (payload?.done || payload?.user_answered) return;
    const t = setInterval(() => {
      setSecondsLeft((s) => Math.max(0, s - 1));
    }, 1000);
    return () => clearInterval(t);
  }, [phase, payload?.done, payload?.user_answered, payload?.question?.id]);

  useEffect(() => {
    if (phase === "memory" && secondsLeft <= 0) {
      setPhase("question");
      setSecondsLeft(payload?.seconds || 20);
    }
  }, [phase, secondsLeft, payload?.seconds]);

  useGSAP(
    () => {
      registerGsap();
      if (!root.current) return;
      gsap.from(root.current.querySelectorAll("[data-spectate]"), {
        opacity: 0,
        y: 12,
        stagger: 0.06,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: root, dependencies: [payload?.question?.id, decisions.length] }
  );

  if (!roundId) {
    return <>{emptyHint}</>;
  }

  if (loadError && !payload) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <p className="led-title text-2xl text-[var(--whistle-red)]">Spectator feed unavailable</p>
        <p className="mt-3 text-sm text-[var(--floodlight)]/60">{loadError}</p>
        <button
          type="button"
          onClick={() => refresh()}
          className="mt-6 border border-[var(--turf-line)] px-5 py-2 text-sm uppercase"
        >
          Retry
        </button>
      </div>
    );
  }

  if (payload?.done) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <p className="led-title text-4xl text-[var(--trophy-gold)]">Full time</p>
        <p className="mt-4 text-[var(--floodlight)]/70">
          {trial
            ? "Your agent finished the practice match. Check career for lessons."
            : "Match resolved — agents advance by score."}
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {backHref && (
            <Link
              href={backHref}
              className="bg-[var(--trophy-gold)] px-6 py-3 text-sm font-semibold uppercase text-[var(--night-sky)]"
            >
              Back
            </Link>
          )}
          <Link
            href="/agent/career"
            className="border border-[var(--turf-line)] px-6 py-3 text-sm uppercase"
          >
            Career
          </Link>
        </div>
      </div>
    );
  }

  const q = payload?.question;
  const qDecisions = decisions.filter((d) => d.question_id === q?.id);

  return (
    <div ref={root} className="mx-auto max-w-3xl px-4 py-10">
      <div data-spectate className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">
            {trial ? "Practice watch" : "Live spectator"}
          </p>
          <p className="mt-1 text-sm text-[var(--floodlight)]/55">
            Agents answer autonomously — you coach, you watch.
          </p>
        </div>
        <div className="text-right">
          {scores && (
            <p className="led-title text-xl text-[var(--trophy-gold)]">
              {scores.a} – {scores.b}
            </p>
          )}
          <p className="led-title text-3xl text-[var(--floodlight)]">
            {String(secondsLeft).padStart(2, "0")}
          </p>
          <p className="text-[10px] uppercase tracking-widest text-[var(--floodlight)]/40">
            {phase === "memory" ? "Memory" : "Clock"}
          </p>
        </div>
      </div>

      <p data-spectate className="mt-6 text-xs uppercase tracking-widest text-[var(--floodlight)]/45">
        Q{(payload?.index ?? 0) + 1} / {payload?.total ?? "—"} · {q?.challenge_type || "…"}
      </p>

      {phase === "memory" && q?.memory_payload ? (
        <div data-spectate className="mt-6 chalk-line pitch-surface p-6">
          <p className="led-title text-2xl text-[var(--trophy-gold)]">{q.memory_payload.title}</p>
          <ul className="mt-4 space-y-2 text-sm text-[var(--floodlight)]/75">
            {q.memory_payload.facts.map((f) => (
              <li key={f} className="border-l border-[var(--turf-line)] pl-3">
                {f}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <>
          <h1 data-spectate className="led-title mt-4 text-3xl md:text-4xl">
            {q?.prompt || "Waiting for next challenge…"}
          </h1>
          <ul data-spectate className="mt-8 space-y-3">
            {(q?.options || []).map((opt, i) => {
              const picked = qDecisions.some((d) => d.option_id === opt.id);
              return (
                <li
                  key={opt.id}
                  className={`border px-4 py-3 text-sm transition ${
                    picked
                      ? "border-[var(--trophy-gold)] bg-[var(--trophy-gold)]/10"
                      : "border-[var(--turf-line)] text-[var(--floodlight)]/70"
                  }`}
                >
                  <span className="mr-3 font-mono text-[var(--trophy-gold)]/70">
                    {String.fromCharCode(65 + i)}
                  </span>
                  {opt.label}
                  {picked && (
                    <span className="ml-2 text-[10px] uppercase tracking-widest text-[var(--trophy-gold)]">
                      selected
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}

      <div data-spectate className="mt-10">
        <p className="text-xs uppercase tracking-[0.3em] text-[var(--trophy-gold)]">Agent decisions</p>
        {qDecisions.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--floodlight)]/50">
            Your agent is answering… keep this tab open.
          </p>
        ) : (
          <ul className="mt-4 space-y-4">
            {qDecisions.map((d) => (
              <li key={d.id} className="border-l-2 border-[var(--kit-home)]/50 pl-4">
                <p className="led-title text-lg">
                  {agentNames[d.agent_id] || d.agent_id.slice(0, 8)}
                  <span className="ml-2 font-sans text-xs font-normal text-[var(--floodlight)]/50">
                    {(d.confidence * 100).toFixed(0)}% conf · {d.latency_ms}ms
                    {d.accelerated ? " · accel" : ""}
                  </span>
                </p>
                <p className="mt-1 text-sm text-[var(--floodlight)]/70">{d.reasoning || "—"}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-wider">
                  {d.used_mcp && (
                    <span className="border border-[var(--floodlight)]/30 px-2 py-0.5">MCP</span>
                  )}
                  {d.used_premium && (
                    <span className="border border-[var(--trophy-gold)]/50 px-2 py-0.5 text-[var(--trophy-gold)]">
                      x402
                    </span>
                  )}
                  {d.used_coach_credit && (
                    <span className="border border-[var(--kit-home)]/50 px-2 py-0.5">Coach</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {backHref && (
        <Link
          href={backHref}
          className="mt-10 inline-block border border-[var(--turf-line)] px-5 py-2 text-xs uppercase tracking-wider"
        >
          Leave watch
        </Link>
      )}
    </div>
  );
}
