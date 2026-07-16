# Shared TypeScript types for Arena64 (optional client stubs)

export type TournamentStatus =
  | "UPCOMING"
  | "LOBBY"
  | "GROUP_STAGE"
  | "R16"
  | "QF"
  | "SF"
  | "FINAL"
  | "COMPLETED"
  | "CANCELLED";

export type ChallengeType =
  | "FOOTBALL"
  | "MEMORY"
  | "STADIUM"
  | "PLAYER_ID"
  | "FLAG"
  | "FORMATION";

export interface TournamentSummary {
  id: string;
  name: string;
  status: TournamentStatus;
  max_players: number;
  entrant_count: number;
  entry_fee_usdc: number;
  reward_pool_usdc: number;
}

export interface StrategyProfile {
  confidence_threshold: number;
  thinking_time_ms: number;
  risk_level: "low" | "medium" | "high" | string;
  max_mcp_calls: number;
  premium_insight_budget: number;
  resource_conservation: number;
  locked_at?: string | null;
  locked_tournament_id?: string | null;
}

export interface AgentSummary {
  id: string;
  user_id: string;
  name: string;
  arena_rating: number;
  strategy?: StrategyProfile | null;
  is_system_agent?: boolean;
}
