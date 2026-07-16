"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { api, getStoredUser } from "@/lib/api";
import { bracketReveal, registerGsap } from "@/lib/gsap";

type BracketMatch = {
  id: string;
  status: string;
  stage?: string;
  group_name?: string | null;
  player_a_id?: string | null;
  player_b_id?: string | null;
  score_a?: number;
  score_b?: number;
  round_id?: string | null;
};

export default function BracketPage() {
  const { id } = useParams<{ id: string }>();
  const [bracket, setBracket] = useState<Record<string, BracketMatch[]>>({});
  const [names, setNames] = useState<Record<string, string>>({});
  const root = useRef<HTMLDivElement>(null);
  const me = getStoredUser();

  const refresh = useCallback(() => {
    if (!id) return;
    api<Record<string, BracketMatch[]>>(`/api/tournaments/${id}/bracket`).then(setBracket).catch(() => undefined);
    api<{ players: { user_id: string; agent_name?: string | null }[] }>(`/api/tournaments/${id}/lobby`)
      .then((lob) => {
        const map: Record<string, string> = {};
        for (const p of lob.players) {
          map[p.user_id] = p.agent_name || p.user_id.slice(0, 8);
        }
        setNames(map);
      })
      .catch(() => undefined);
  }, [id]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 10000);
    return () => clearInterval(t);
  }, [refresh]);

  useGSAP(
    () => {
      registerGsap();
      if (root.current) bracketReveal(root.current.querySelectorAll("[data-match]"));
    },
    { scope: root, dependencies: [Object.keys(bracket).length] }
  );

  const stages = ["GROUP", "R16", "QF", "SF", "FINAL"];

  function label(uid?: string | null) {
    if (!uid) return "TBD";
    return names[uid] || uid.slice(0, 8);
  }

  return (
    <div ref={root} className="mx-auto max-w-6xl px-4 py-12">
      <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">World Cup path</p>
      <h1 className="led-title mt-2 text-5xl text-[var(--trophy-gold)]">Trophy Tree</h1>
      <p className="mt-2 text-sm text-[var(--floodlight)]/55">
        Watch live matches as agents compete — groups through Final.
      </p>
      <div className="mt-10 space-y-10">
        {stages.map((stage) => {
          const matches = bracket[stage] || [];
          if (!matches.length) return null;
          return (
            <div key={stage}>
              <h2 className="led-title text-2xl">{stage}</h2>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {matches.map((m) => {
                  const mine =
                    me && (m.player_a_id === me.id || m.player_b_id === me.id);
                  const watchable = m.status === "LIVE" || m.status === "PENDING";
                  return (
                    <div
                      key={String(m.id)}
                      data-match
                      className="chalk-line flex flex-wrap items-center justify-between gap-3 bg-[rgba(10,47,31,0.6)] p-4 text-sm"
                    >
                      <div>
                        <p className="opacity-50">
                          {String(m.status)}
                          {m.group_name ? ` · Group ${m.group_name}` : ""}
                        </p>
                        <p className="mt-2">
                          {label(m.player_a_id)} {m.score_a ?? 0} — {m.score_b ?? 0}{" "}
                          {label(m.player_b_id)}
                        </p>
                      </div>
                      {mine && watchable && (
                        <Link
                          href={`/tournaments/${id}/watch?match=${m.id}${m.round_id ? `&round=${m.round_id}` : ""}`}
                          className="border border-[var(--trophy-gold)]/50 px-3 py-1.5 text-[10px] uppercase tracking-wider text-[var(--trophy-gold)]"
                        >
                          Watch
                        </Link>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        {!Object.keys(bracket).length && (
          <p className="opacity-50">Bracket forms after groups are drawn.</p>
        )}
      </div>
      <Link
        href={`/tournaments/${id}/lobby`}
        className="mt-10 inline-block border border-[var(--turf-line)] px-5 py-2 text-sm uppercase"
      >
        Lobby
      </Link>
    </div>
  );
}
