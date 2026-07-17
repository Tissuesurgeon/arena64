function normalizeApiUrl(raw: string): string {
  return raw.trim().replace(/\/+$/, "");
}

const API_URL = normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");

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

function assertApiReachable(): void {
  if (typeof window === "undefined") return;
  const pageHttps = window.location.protocol === "https:";
  if (pageHttps && API_URL.startsWith("http://")) {
    throw new Error(
      "API is configured with http:// but the site is https:// — set NEXT_PUBLIC_API_URL to your Railway https URL and redeploy Vercel."
    );
  }
  if (
    pageHttps &&
    (API_URL.includes("localhost") || API_URL.includes("127.0.0.1"))
  ) {
    throw new Error(
      "NEXT_PUBLIC_API_URL still points at localhost. Set it to your Railway API URL in Vercel env and redeploy."
    );
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  assertApiReachable();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(init?.headers || {}),
      },
    });
  } catch {
    throw new Error(
      `Cannot reach API at ${API_URL}. Check NEXT_PUBLIC_API_URL and Railway CORS (API_CORS_ORIGINS).`
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

export { API_URL };
