"""Strategy Engine — policy gate before any skill runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# In-process remaining budgets: (agent_id, tournament_id) → counters
_BUDGETS: dict[tuple[str, str], dict[str, float]] = {}


@dataclass
class ActionPolicy:
    accelerated: bool
    thinking_ms: int
    confidence_threshold: float
    risk_level: str
    conservation: float
    allow_mcp: bool
    allow_premium: bool
    allow_coach: bool
    mcp_remaining: int
    premium_remaining: float
    skill_style: str  # aggressive | balanced | analyst


def _budget_key(agent_id: str, tournament_id: str | None) -> tuple[str, str]:
    return (agent_id, tournament_id or "none")


def _ensure_budget(agent_id: str, tournament_id: str | None, strategy: dict[str, Any]) -> dict[str, float]:
    key = _budget_key(agent_id, tournament_id)
    if key not in _BUDGETS:
        _BUDGETS[key] = {
            "mcp_remaining": float(int(strategy.get("max_mcp_calls") or 0)),
            "premium_remaining": float(strategy.get("premium_insight_budget") or 0),
        }
    return _BUDGETS[key]


def skill_style_for(strategy: dict[str, Any]) -> str:
    risk = str(strategy.get("risk_level") or "medium").lower()
    conservation = float(strategy.get("resource_conservation") or 0.5)
    if risk == "high" or conservation >= 0.75:
        return "aggressive"
    if risk == "low" or conservation <= 0.35:
        return "analyst"
    return "balanced"


class StrategyEngine:
    """Policy-driven gate: equal tools, different spend decisions."""

    def evaluate(
        self,
        *,
        agent_id: str,
        tournament_id: str | None,
        strategy: dict[str, Any],
        is_system_agent: bool,
    ) -> ActionPolicy:
        strategy = strategy or {}
        budgets = _ensure_budget(agent_id, tournament_id, strategy)
        conservation = float(strategy.get("resource_conservation") or 0.5)
        threshold = float(strategy.get("confidence_threshold") or 0.55)
        risk = str(strategy.get("risk_level") or "medium")
        think = int(strategy.get("thinking_time_ms") or 800)
        style = skill_style_for(strategy)

        if is_system_agent:
            return ActionPolicy(
                accelerated=True,
                thinking_ms=min(think, 120),
                confidence_threshold=threshold,
                risk_level=risk,
                conservation=conservation,
                allow_mcp=False,
                allow_premium=False,
                allow_coach=False,
                mcp_remaining=0,
                premium_remaining=0.0,
                skill_style="aggressive",
            )

        mcp_left = int(budgets["mcp_remaining"])
        prem_left = float(budgets["premium_remaining"])

        # Aggressive: tools only when far below threshold (handled by DecisionEngine gap)
        allow_mcp = mcp_left > 0 and conservation < 0.85
        allow_premium = prem_left > 0 and conservation < 0.7
        allow_coach = conservation < 0.55

        if style == "aggressive":
            allow_premium = allow_premium and conservation < 0.5
            allow_coach = False

        return ActionPolicy(
            accelerated=False,
            thinking_ms=think,
            confidence_threshold=threshold,
            risk_level=risk,
            conservation=conservation,
            allow_mcp=allow_mcp,
            allow_premium=allow_premium,
            allow_coach=allow_coach,
            mcp_remaining=mcp_left,
            premium_remaining=prem_left,
            skill_style=style,
        )

    def consume_mcp(self, agent_id: str, tournament_id: str | None) -> None:
        key = _budget_key(agent_id, tournament_id)
        if key in _BUDGETS:
            _BUDGETS[key]["mcp_remaining"] = max(0, _BUDGETS[key]["mcp_remaining"] - 1)

    def consume_premium(self, agent_id: str, tournament_id: str | None, amount: float = 1.0) -> None:
        key = _budget_key(agent_id, tournament_id)
        if key in _BUDGETS:
            _BUDGETS[key]["premium_remaining"] = max(0.0, _BUDGETS[key]["premium_remaining"] - amount)


strategy_engine = StrategyEngine()
