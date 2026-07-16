from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    BigInteger,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class TournamentStatus(str, enum.Enum):
    UPCOMING = "UPCOMING"
    LOBBY = "LOBBY"
    GROUP_STAGE = "GROUP_STAGE"
    R16 = "R16"
    QF = "QF"
    SF = "SF"
    FINAL = "FINAL"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Visibility(str, enum.Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


class ChallengeType(str, enum.Enum):
    FOOTBALL = "FOOTBALL"
    MEMORY = "MEMORY"
    STADIUM = "STADIUM"
    PLAYER_ID = "PLAYER_ID"
    FLAG = "FLAG"
    FORMATION = "FORMATION"


class MatchStatus(str, enum.Enum):
    PENDING = "PENDING"
    LIVE = "LIVE"
    COMPLETED = "COMPLETED"


class RewardType(str, enum.Enum):
    USDC = "USDC"
    XP = "XP"
    NFT = "NFT"
    MERCH = "MERCH"
    SPONSOR = "SPONSOR"


class TxType(str, enum.Enum):
    CCTP_DEPOSIT = "CCTP_DEPOSIT"
    ONCHAIN_DEPOSIT = "ONCHAIN_DEPOSIT"
    DEMO_FAUCET = "DEMO_FAUCET"
    ENTRY_FEE = "ENTRY_FEE"  # legacy; prefer ENTRY_LOCK / ENTRY_CONSUME
    ENTRY_LOCK = "ENTRY_LOCK"
    ENTRY_UNLOCK = "ENTRY_UNLOCK"
    ENTRY_CONSUME = "ENTRY_CONSUME"
    COACH_PACK = "COACH_PACK"
    REWARD = "REWARD"
    X402_PREMIUM = "X402_PREMIUM"
    REFUND = "REFUND"
    WITHDRAW = "WITHDRAW"


class EntryFeeStatus(str, enum.Enum):
    LOCKED = "LOCKED"
    CONSUMED = "CONSUMED"
    REFUNDED = "REFUNDED"
    NONE = "NONE"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    wallet_address: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system_agent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    balance: Mapped["Balance"] = relationship(back_populates="user", uselist=False)
    coach_credits: Mapped["CoachCredits"] = relationship(back_populates="user", uselist=False)
    fair_play: Mapped["FairPlayScore"] = relationship(back_populates="user", uselist=False)
    agent: Mapped[Optional["Agent"]] = relationship(back_populates="user", uselist=False)


class Balance(Base):
    """Arena64 Account ledger row (not an on-chain wallet)."""

    __tablename__ = "balances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    # Column name kept as usdc_micro for existing DBs; this is Available balance.
    available_usdc_micro: Mapped[int] = mapped_column("usdc_micro", BigInteger, default=0)
    locked_usdc_micro: Mapped[int] = mapped_column(BigInteger, default=0)

    user: Mapped[User] = relationship(back_populates="balance")

    @property
    def usdc_micro(self) -> int:
        """Back-compat alias for available balance."""
        return int(self.available_usdc_micro or 0)

    @usdc_micro.setter
    def usdc_micro(self, value: int) -> None:
        self.available_usdc_micro = int(value)

    @property
    def total_usdc_micro(self) -> int:
        return int(self.available_usdc_micro or 0) + int(self.locked_usdc_micro or 0)


class CoachCredits(Base):
    __tablename__ = "coach_credits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    credits: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="coach_credits")


class FairPlayScore(Base):
    __tablename__ = "fair_play_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    score: Mapped[float] = mapped_column(Float, default=100.0)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped[User] = relationship(back_populates="fair_play")


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    max_players: Mapped[int] = mapped_column(Integer, default=6)
    entry_fee_usdc_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    reward_pool_usdc_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    reward_type: Mapped[RewardType] = mapped_column(Enum(RewardType), default=RewardType.USDC)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    challenge_types: Mapped[list] = mapped_column(JSON, default=lambda: ["FOOTBALL", "MEMORY"])
    difficulty: Mapped[str] = mapped_column(String(32), default="medium")
    questions_per_round: Mapped[int] = mapped_column(Integer, default=5)
    coach_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    platform_fee_bps: Mapped[int] = mapped_column(Integer, default=500)  # 5%
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility), default=Visibility.PUBLIC)
    invite_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[TournamentStatus] = mapped_column(Enum(TournamentStatus), default=TournamentStatus.UPCOMING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entries: Mapped[list["TournamentEntry"]] = relationship(back_populates="tournament")
    groups: Mapped[list["TournamentGroup"]] = relationship(back_populates="tournament")
    matches: Mapped[list["Match"]] = relationship(back_populates="tournament")


class TournamentEntry(Base):
    __tablename__ = "tournament_entries"
    __table_args__ = (UniqueConstraint("tournament_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    eliminated: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    entry_fee_locked_usdc_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    fee_status: Mapped[str] = mapped_column(String(16), default=EntryFeeStatus.NONE.value)

    tournament: Mapped[Tournament] = relationship(back_populates="entries")


class TournamentGroup(Base):
    __tablename__ = "tournament_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    name: Mapped[str] = mapped_column(String(8))  # A..H
    member_user_ids: Mapped[list] = mapped_column(JSON, default=list)

    tournament: Mapped[Tournament] = relationship(back_populates="groups")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    stage: Mapped[str] = mapped_column(String(32))  # GROUP, R16, QF, SF, FINAL
    group_name: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    player_a_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    player_b_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    score_a: Mapped[int] = mapped_column(Integer, default=0)
    score_b: Mapped[int] = mapped_column(Integer, default=0)
    winner_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[MatchStatus] = mapped_column(Enum(MatchStatus), default=MatchStatus.PENDING)
    bracket_slot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    tournament: Mapped[Tournament] = relationship(back_populates="matches")
    rounds: Mapped[list["Round"]] = relationship(back_populates="match")


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    challenge_type: Mapped[ChallengeType] = mapped_column(Enum(ChallengeType), default=ChallengeType.FOOTBALL)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    active_question_index: Mapped[int] = mapped_column(Integer, default=0)

    match: Mapped[Match] = relationship(back_populates="rounds")


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|running|completed|failed
    topic: Mapped[str] = mapped_column(String(128), default="world-cup")
    urls: Mapped[list] = mapped_column(JSON, default=list)
    pages_scraped: Mapped[int] = mapped_column(Integer, default=0)
    facts_stored: Mapped[int] = mapped_column(Integer, default=0)
    questions_created: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scrape_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("scrape_jobs.id"), nullable=True, index=True)
    source_url: Mapped[str] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(String(512), default="")
    category: Mapped[str] = mapped_column(String(64), default="world-cup")
    fact: Mapped[str] = mapped_column(Text)
    raw_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entities: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    challenge_type: Mapped[ChallengeType] = mapped_column(Enum(ChallengeType), default=ChallengeType.FOOTBALL)
    prompt: Mapped[str] = mapped_column(Text)
    memory_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    media_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(32), default="medium")
    source: Mapped[str] = mapped_column(String(64), default="seed")
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    knowledge_entry_id: Mapped[Optional[str]] = mapped_column(ForeignKey("knowledge_entries.id"), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)

    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question")


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    label: Mapped[str] = mapped_column(String(256))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped[Question] = relationship(back_populates="options")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("round_id", "question_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    option_id: Mapped[Optional[str]] = mapped_column(ForeignKey("question_options.id"), nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    points: Mapped[int] = mapped_column(Integer, default=0)
    remaining_seconds: Mapped[float] = mapped_column(Float, default=0)
    nonce: Mapped[str] = mapped_column(String(64))
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LeaderboardEntry(Base):
    __tablename__ = "leaderboards"
    __table_args__ = (UniqueConstraint("tournament_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    placement: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class Reward(Base):
    __tablename__ = "rewards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    placement: Mapped[int] = mapped_column(Integer)
    amount_usdc_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tx_type: Mapped[TxType] = mapped_column(Enum(TxType))
    amount_usdc_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    external_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PremiumTransaction(Base):
    __tablename__ = "premium_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    service_name: Mapped[str] = mapped_column(String(64), default="premium_insight")
    cost_usdc_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    tournament_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TournamentHistory(Base):
    __tablename__ = "tournament_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    placement: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Agent(Base):
    """Persistent AI competitor owned by exactly one wallet/user."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    arena_rating: Mapped[float] = mapped_column(Float, default=1000.0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="agent")
    strategy: Mapped[Optional["StrategyProfile"]] = relationship(back_populates="agent", uselist=False)
    memory: Mapped[Optional["AgentMemory"]] = relationship(back_populates="agent", uselist=False)
    career: Mapped[Optional["AgentCareer"]] = relationship(back_populates="agent", uselist=False)


class StrategyProfile(Base):
    __tablename__ = "strategy_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), unique=True, index=True)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.55)
    thinking_time_ms: Mapped[int] = mapped_column(Integer, default=1200)
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high
    max_mcp_calls: Mapped[int] = mapped_column(Integer, default=3)
    premium_insight_budget: Mapped[float] = mapped_column(Float, default=2.0)  # USDC per tournament
    resource_conservation: Mapped[float] = mapped_column(Float, default=0.5)  # 0 spend-eager → 1 conserve
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_tournament_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped[Agent] = relationship(back_populates="strategy")


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), unique=True, index=True)
    summary: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "strengths": [],
            "weaknesses": [],
            "avg_confidence": 0.0,
            "mcp_usage": 0,
            "premium_usage": 0,
            "coach_credit_efficiency": None,
            "recommendation": "Configure strategy and join a 6-agent cup.",
        },
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped[Agent] = relationship(back_populates="memory")


class AgentCareer(Base):
    __tablename__ = "agent_careers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), unique=True, index=True)
    tournaments_played: Mapped[int] = mapped_column(Integer, default=0)
    matches_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    championships: Mapped[int] = mapped_column(Integer, default=0)
    average_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    average_response_ms: Mapped[float] = mapped_column(Float, default=0.0)
    resource_efficiency: Mapped[float] = mapped_column(Float, default=0.0)
    category_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped[Agent] = relationship(back_populates="career")


class AgentDecisionLog(Base):
    __tablename__ = "agent_decision_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    round_id: Mapped[Optional[str]] = mapped_column(ForeignKey("rounds.id"), nullable=True, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    option_id: Mapped[Optional[str]] = mapped_column(ForeignKey("question_options.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    used_mcp: Mapped[bool] = mapped_column(Boolean, default=False)
    used_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    used_coach_credit: Mapped[bool] = mapped_column(Boolean, default=False)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    accelerated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)