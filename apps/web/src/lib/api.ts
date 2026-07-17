function normalizeApiUrl(raw: string): string {
  return raw.trim().replace(/\/+$/, "");
}

/**
 * Browser: always use same-origin `/arena-api` proxy (see next.config.js rewrites).
 * That way Vercel works even if NEXT_PUBLIC_API_URL was left as localhost.
 * Server/SSR: use absolute URL.
 */
export function getApiUrl(): string {
  if (typeof window !== "undefined") {
    return "/arena-api";
  }
  const env = normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL || "");
  if (env && !/localhost|127\.0\.0\.1/.test(env)) return env;
  if (process.env.VERCEL) return "https://arena64-production.up.railway.app";
  return env || "http://localhost:8000";
}

/** @deprecated use getApiUrl() — kept for imports that read a constant */
export const API_URL =
  typeof window === "undefined"
    ? normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    : "/arena-api";

export type User = {
  id: string;
  wallet_address: string;
  display_name: string | null;
  xp: number;
  is_admin: boolean;
  usdc_balance: number;
  available_usdc?: number;
  locked_usdc?: number;
  coach_credits: number;
  fair_play_score: number;
};

export type Tournament = {
  id: string;
  name: string;
  description: string;
  max_players: number;
  entry_fee_usdc: number;
  reward_pool_usdc: number;
  status: string;
  entrant_count: number;
  challenge_types: string[];
  difficulty: string;
  questions_per_round: number;
};

export type StrategyProfile = {
  confidence_threshold: number;
  thinking_time_ms: number;
  risk_level: "low" | "medium" | "high" | string;
  max_mcp_calls: number;
  premium_insight_budget: number;
  resource_conservation: number;
  locked_at?: string | null;
  locked_tournament_id?: string | null;
  updated_at?: string | null;
};

export type AgentCareer = {
  tournaments_played: number;
  matches_played: number;
  wins: number;
  losses: number;
  championships: number;
  average_accuracy: number;
  average_response_ms: number;
  resource_efficiency: number;
  category_stats?: Record<string, unknown>;
};

export type Agent = {
  id: string;
  user_id: string;
  name: string;
  arena_rating: number;
  created_at?: string;
  strategy?: StrategyProfile | null;
  career?: AgentCareer | null;
  memory?: { summary: Record<string, unknown>; updated_at?: string | null } | null;
  is_system_agent?: boolean;
};

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("arena64_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiUrl();
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(init?.headers || {}),
      },
    });
  } catch {
    throw new Error(
      `Cannot reach API (${base}). On Vercel, ensure the /arena-api rewrite points at Railway.`
    );
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}

export async function demoLogin(displayName?: string): Promise<{ access_token: string; user: User }> {
  const wallet = `0xdemo${Math.random().toString(16).slice(2, 10)}`;
  const nonce = await api<{ message: string }>(`/api/auth/nonce?wallet_address=${wallet}`);
  const data = await api<{ access_token: string; user: User }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({
      wallet_address: wallet,
      signature: "demo",
      message: nonce.message,
      display_name: displayName || "Arena Player",
    }),
  });
  localStorage.setItem("arena64_token", data.access_token);
  localStorage.setItem("arena64_user", JSON.stringify(data.user));
  return data;
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("arena64_user");
  return raw ? JSON.parse(raw) : null;
}

export function logout() {
  localStorage.removeItem("arena64_token");
  localStorage.removeItem("arena64_user");
}
