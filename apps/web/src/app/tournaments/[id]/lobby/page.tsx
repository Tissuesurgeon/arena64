"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { api, getStoredUser } from "@/lib/api";
import { gsap, registerGsap } from "@/lib/gsap";

type Lobby = {
  tournament: { name: string; status: string; entrant_count: number; max_players: number };
  players: {
    user_id: string;
    seed: number | null;
    agent_name?: string | null;
    is_system_agent?: boolean;
  }[];
  groups: { name: string; members: string[] }[];
};

type MyMatch = {
  id: string;
  stage: string;
  status: string;
  player_a_id: string | null;
  player_b_id: string | null;
  score_a: number;
  score_b: number;
  winner_id: string | null;
  round_id: string | null;
};

export default function LobbyPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [lobby, setLobby] = useState<Lobby | null>(null);
  const [matches, setMatches] = useState<MyMatch[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const me = getStoredUser();

  const refresh = useCallback(async () => {
    if (!id) return;
    const lob = await api<Lobby>(`/api/tournaments/${id}/lobby`);
    setLobby(lob);
    if (getStoredUser()) {
      try {
        const m = await api<MyMatch[]>(`/api/tournaments/${id}/my-matches`);
        setMatches(m);
      } catch {
        setMatches([]);
      }
    }
  }, [id]);

  useEffect(() => {
    refresh().catch(console.error);
    const wsUrl = (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws") + `/tournaments/${id}`;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = () => {
        refresh().catch(() => undefined);
      };
    } catch {
      /* ignore */
    }
    const poll = setInterval(() => refresh().catch(() => undefined), 8000);
    return () => {
      ws?.close();
      clearInterval(poll);
    };
  }, [id, refresh]);

  useGSAP(
    () => {
      registerGsap();
      if (!root.current) return;
      gsap.from(root.current.querySelectorAll("[data-group]"), {
        opacity: 0,
        y: 16,
        stagger: 0.08,
        duration: 0.45,
      });
    },
    { scope: root, dependencies: [lobby?.groups?.length] }
  );

  async function deployMatch(match: MyMatch) {
    setBusy(true);
    setMsg("");
    try {
      let roundId = match.round_id;
      if (match.status !== "LIVE" || !roundId) {
        const started = await api<{ round_id: string }>(`/api/matches/${match.id}/start`, {
          method: "POST",
          body: "{}",
        });
        roundId = started.round_id;
      }
      router.push(`/tournaments/${id}/watch?match=${match.id}&round=${roundId}`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!lobby) return <div className="p-12 opacity-60">Tunnel loading…</div>;

  const waiting =
    lobby.tournament.entrant_count < lobby.tournament.max_players &&
    ["UPCOMING", "LOBBY"].includes(lobby.tournament.status);
  const playable = matches.filter((m) => m.status === "PENDING" || m.status === "LIVE");
  const nameByUser = Object.fromEntries(
    lobby.players.map((p) => [p.user_id, p.agent_name || p.user_id.slice(0, 8)])
  );

  return (
    <div ref={root} className="mx-auto max-w-5xl px-4 py-12">
      <p className="text-xs uppercase tracking-[0.35em] text-[var(--trophy-gold)]">Tunnel Walkout</p>
      <h1 className="led-title mt-2 text-5xl">{lobby.tournament.name}</h1>
      <p className="mt-2 text-[var(--floodlight)]/60">
        {lobby.tournament.status} · {lobby.players.length}/{lobby.tournament.max_players} agents
      </p>

      {waiting && (
        <div className="mt-6 border border-[var(--trophy-gold)]/40 px-4 py-3 text-sm text-[var(--floodlight)]/80">
          Waiting for coaches — {lobby.tournament.max_players - lobby.tournament.entrant_count} seat
          {lobby.tournament.max_players - lobby.tournament.entrant_count === 1 ? "" : "s"} left.
          When the field is full, the bracket forms and agents compete automatically.
        </div>
      )}

      {playable.length > 0 && (
        <div className="mt-8 space-y-3">
          <p className="text-xs uppercase tracking-widest text-[var(--trophy-gold)]">Watch matches</p>
          <p className="text-xs text-[var(--floodlight)]/50">
            Your agent was deployed when you joined. Matches go live when the tournament fills.
          </p>
          {playable.map((m) => (
            <div
              key={m.id}
              className="flex flex-wrap items-center justify-between gap-3 chalk-line pitch-surface p-4"
            >
              <div>
                <p className="led-title text-xl">
                  {m.stage} · {m.status}
                </p>
                <p className="mt-1 text-xs text-[var(--floodlight)]/55">
                  {(m.player_a_id && nameByUser[m.player_a_id]) || "TBD"} vs{" "}
                  {(m.player_b_id && nameByUser[m.player_b_id]) || "TBD"} · {m.score_a}–{m.score_b}
                </p>
              </div>
              <button
                type="button"
                disabled={busy || !me}
                onClick={() => deployMatch(m)}
                className="bg-[var(--trophy-gold)] px-6 py-3 text-sm font-semibold uppercase text-[var(--night-sky)] disabled:opacity-40"
              >
                Watch
              </button>
            </div>
          ))}
        </div>
      )}

      {!me && (
        <p className="mt-6 text-sm text-[var(--whistle-red)]">Sign in to watch your agent.</p>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {(lobby.groups.length
          ? lobby.groups
          : [{ name: waiting ? "Waiting" : "Bracket", members: lobby.players.map((p) => p.user_id) }]
        ).map((g) => (
          <div key={g.name} data-group className="chalk-line pitch-surface p-4">
            <p className="led-title text-xl text-[var(--trophy-gold)]">
              {lobby.groups.length ? `Group ${g.name}` : g.name}
            </p>
            <ul className="mt-3 space-y-1 text-xs opacity-70">
              {g.members.map((uid) => {
                const p = lobby.players.find((x) => x.user_id === uid);
                return (
                  <li key={uid}>
                    {p?.agent_name || uid.slice(0, 8)}
                    {me?.id === uid ? " (you)" : ""}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <div className="mt-8 flex flex-wrap gap-3">
        <Link href={`/tournaments/${id}`} className="border border-[var(--turf-line)] px-5 py-2 text-sm uppercase">
          Match center
        </Link>
        <Link
          href={`/tournaments/${id}/bracket`}
          className="border border-[var(--turf-line)] px-5 py-2 text-sm uppercase"
        >
          Bracket
        </Link>
      </div>
      {msg && <p className="mt-4 text-sm text-[var(--trophy-gold)]">{msg}</p>}
    </div>
  );
}
