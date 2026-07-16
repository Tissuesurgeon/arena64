from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NonceResponse(BaseModel):
    message: str
    nonce: str


class AuthLoginRequest(BaseModel):
    wallet_address: str
    signature: str
    message: str
    display_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    wallet_address: str
    display_name: Optional[str]
    xp: int
    is_admin: bool
    usdc_balance: float
    available_usdc: float = 0
    locked_usdc: float = 0
    coach_credits: int
    fair_play_score: float

    class Config:
        from_attributes = True


class TournamentCreate(BaseModel):
    name: str
    description: str = ""
    max_players: int = 6
    entry_fee_usdc: float = 0
    reward_pool_usdc: float = 0
    start_time: Optional[datetime] = None
    challenge_types: list[str] = Field(default_factory=lambda: ["FOOTBALL", "MEMORY"])
    difficulty: str = "medium"
    questions_per_round: int = 5
    coach_enabled: bool = True
    platform_fee_bps: int = 500
    visibility: str = "PUBLIC"
    invite_code: Optional[str] = None


class TournamentOut(BaseModel):
    id: str
    name: str
    description: str
    max_players: int
    entry_fee_usdc: float
    reward_pool_usdc: float
    start_time: Optional[datetime]
    challenge_types: list[str]
    difficulty: str
    questions_per_round: int
    coach_enabled: bool
    platform_fee_bps: int
    visibility: str
    status: str
    entrant_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class JoinRequest(BaseModel):
    invite_code: Optional[str] = None


class AnswerSubmit(BaseModel):
    round_id: str
    question_id: str
    option_id: Optional[str] = None
    remaining_seconds: float = 0
    nonce: str


class CoachAbilityRequest(BaseModel):
    ability: str
    question_id: Optional[str] = None
    match_id: Optional[str] = None


class CoachPackPurchase(BaseModel):
    pack: str  # starter | pro | champion
    payment_proof: Optional[str] = None  # x402 receipt / demo


class CCTPDepositRequest(BaseModel):
    burn_tx_hash: str
    source_domain: int = 6  # Base example
    amount_usdc: float
    attestation: Optional[str] = None
    message_bytes: Optional[str] = None


class DemoFaucetRequest(BaseModel):
    amount_usdc: Optional[float] = None


class FairPlayEvent(BaseModel):
    event: str
    meta: dict[str, Any] = Field(default_factory=dict)


class QuestionPublic(BaseModel):
    id: str
    challenge_type: str
    prompt: str
    memory_payload: Optional[dict] = None
    media_url: Optional[str] = None
    difficulty: str
    options: list[dict]


class StrategyProfileIn(BaseModel):
    confidence_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    thinking_time_ms: int = Field(default=1200, ge=200, le=15000)
    risk_level: str = Field(default="medium", pattern="^(low|medium|high)$")
    max_mcp_calls: int = Field(default=3, ge=0, le=20)
    premium_insight_budget: float = Field(default=2.0, ge=0.0, le=100.0)
    resource_conservation: float = Field(default=0.5, ge=0.0, le=1.0)


class StrategyProfileOut(StrategyProfileIn):
    locked_at: Optional[datetime] = None
    locked_tournament_id: Optional[str] = None
    updated_at: Optional[datetime] = None


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    strategy: Optional[StrategyProfileIn] = None


class AgentCareerOut(BaseModel):
    tournaments_played: int = 0
    matches_played: int = 0
    wins: int = 0
    losses: int = 0
    championships: int = 0
    average_accuracy: float = 0.0
    average_response_ms: float = 0.0
    resource_efficiency: float = 0.0
    category_stats: dict[str, Any] = Field(default_factory=dict)


class AgentMemoryOut(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None


class AgentOut(BaseModel):
    id: str
    user_id: str
    name: str
    arena_rating: float
    created_at: datetime
    strategy: Optional[StrategyProfileOut] = None
    career: Optional[AgentCareerOut] = None
    memory: Optional[AgentMemoryOut] = None
    is_system_agent: bool = False

    class Config:
        from_attributes = True


class DecisionLogOut(BaseModel):
    id: str
    agent_id: str
    match_id: str
    question_id: str
    option_id: Optional[str] = None
    confidence: float
    used_mcp: bool
    used_premium: bool
    used_coach_credit: bool
    reasoning: str
    latency_ms: int
    accelerated: bool = False
    is_correct: Optional[bool] = None
    created_at: datetime


class DecisionLogCreate(BaseModel):
    agent_id: str
    match_id: str
    round_id: Optional[str] = None
    question_id: str
    option_id: Optional[str] = None
    confidence: float = 0.0
    used_mcp: bool = False
    used_premium: bool = False
    used_coach_credit: bool = False
    reasoning: str = ""
    latency_ms: int = 0
    accelerated: bool = False
    is_correct: Optional[bool] = None


TokenResponse.model_rebuild()