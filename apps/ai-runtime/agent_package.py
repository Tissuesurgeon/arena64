"""Normalize live-work agent payload into a competition Agent package view."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentPackage:
    id: str
    name: str
    user_id: str
    arena_rating: float
    is_system_agent: bool
    strategy: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    career: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    token: str = ""
    tournament_id: str | None = None

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "is_system_agent": self.is_system_agent,
        }

    @property
    def rating(self) -> float:
        return self.arena_rating


def from_live_work_player(player: dict, match: dict | None = None) -> AgentPackage | None:
    agent = player.get("agent") or {}
    if not agent.get("id"):
        return None
    mem = agent.get("memory") or {}
    summary = mem.get("summary") if isinstance(mem, dict) else {}
    return AgentPackage(
        id=agent["id"],
        name=agent.get("name") or "Agent",
        user_id=player.get("user_id") or agent.get("user_id") or "",
        arena_rating=float(agent.get("arena_rating") or 1000.0),
        is_system_agent=bool(player.get("is_system_agent") or agent.get("is_system_agent")),
        strategy=dict(agent.get("strategy") or {}),
        memory=dict(summary or {}),
        career=dict(agent.get("career") or {}),
        budget=dict(agent.get("budget") or {}),
        token=player.get("token") or "",
        tournament_id=(match or {}).get("tournament_id"),
    )
