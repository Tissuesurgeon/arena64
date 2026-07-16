"""Tool registry — named football tools over Arena64 API (shared knowledge only)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from engines.strategy import ActionPolicy, strategy_engine

logger = logging.getLogger("arena64-ai-runtime.tools")

API_URL = os.getenv("ARENA64_API_URL", "http://127.0.0.1:8000")
SERVICE_KEY = os.getenv("SERVICE_API_KEY", "arena64-dev-service-key")


def _svc() -> dict[str, str]:
    return {"Content-Type": "application/json", "X-Service-Key": SERVICE_KEY}


def _auth(token: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


class ToolRegistry:
    async def research_knowledge(
        self, client: httpx.AsyncClient, *, q: str, limit: int = 5
    ) -> dict[str, Any]:
        r = await client.get(
            f"{API_URL}/api/runtime/research",
            params={"q": q[:120], "limit": limit},
            headers=_svc(),
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return {"tool": "researchKnowledge", "results": data.get("results") or []}

    async def research_by_category(
        self, client: httpx.AsyncClient, *, q: str, category: str, limit: int = 5
    ) -> dict[str, Any]:
        r = await client.get(
            f"{API_URL}/api/runtime/research",
            params={"q": q[:120], "category": category, "limit": limit},
            headers=_svc(),
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "tool": "researchByCategory",
            "category": category,
            "results": data.get("results") or [],
        }

    async def buy_premium_insight(self, client: httpx.AsyncClient, *, token: str) -> dict[str, Any]:
        r = await client.get(
            f"{API_URL}/api/player/analysis",
            headers=_auth(token),
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return {"tool": "buyPremiumInsight", "insight": data.get("insight"), "x402": data.get("x402")}

    async def coach_remove_two(
        self, client: httpx.AsyncClient, *, token: str, question_id: str
    ) -> dict[str, Any]:
        r = await client.post(
            f"{API_URL}/api/coach/ability",
            headers=_auth(token),
            json={"ability": "remove_two", "question_id": question_id},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "tool": "coachRemoveTwo",
            "remove_option_ids": data.get("remove_option_ids") or [],
        }

    async def get_standings(
        self, client: httpx.AsyncClient, *, tournament_id: str, token: str
    ) -> dict[str, Any]:
        r = await client.get(
            f"{API_URL}/api/tournaments/{tournament_id}/leaderboard",
            headers=_auth(token),
            timeout=20,
        )
        if r.status_code >= 400:
            return {"tool": "getStandings", "results": []}
        return {"tool": "getStandings", "results": r.json()}

    async def get_bracket(
        self, client: httpx.AsyncClient, *, tournament_id: str, token: str
    ) -> dict[str, Any]:
        r = await client.get(
            f"{API_URL}/api/tournaments/{tournament_id}/bracket",
            headers=_auth(token),
            timeout=20,
        )
        if r.status_code >= 400:
            return {"tool": "getBracket", "results": {}}
        return {"tool": "getBracket", "results": r.json()}

    async def run_skill_plan(
        self,
        client: httpx.AsyncClient,
        *,
        question: dict,
        token: str,
        agent_id: str,
        tournament_id: str | None,
        policy: ActionPolicy,
        prefer_research: bool,
        budget: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Execute ≤2 tools based on strategy style. Returns tool result payloads."""
        results: list[dict[str, Any]] = []
        qtext = (question.get("prompt") or "")[:120]
        category = str(question.get("challenge_type") or "FOOTBALL")
        budget = budget or {}
        wallet_ok = float(budget.get("wallet_balance") or 0) > 0
        premium_ok = int(budget.get("max_premium_requests") or 0) > 0 and wallet_ok

        want_research = policy.allow_mcp and (prefer_research or policy.skill_style != "aggressive")
        if policy.skill_style == "aggressive" and not prefer_research:
            want_research = policy.allow_mcp

        if want_research and policy.mcp_remaining > 0:
            try:
                if category in ("STADIUM", "PLAYER_ID", "FLAG", "FORMATION", "MEMORY", "FOOTBALL"):
                    res = await self.research_by_category(
                        client, q=qtext, category=category, limit=5
                    )
                else:
                    res = await self.research_knowledge(client, q=qtext)
                results.append(res)
                strategy_engine.consume_mcp(agent_id, tournament_id)
            except Exception as exc:  # noqa: BLE001
                logger.debug("research failed: %s", exc)

        can_premium = (
            policy.allow_premium and policy.premium_remaining > 0 and premium_ok
        )
        if can_premium and policy.skill_style == "analyst":
            try:
                results.append(await self.buy_premium_insight(client, token=token))
                strategy_engine.consume_premium(agent_id, tournament_id, 1.0)
            except Exception as exc:  # noqa: BLE001
                logger.debug("premium failed: %s", exc)
        elif can_premium and policy.skill_style == "balanced" and prefer_research:
            try:
                results.append(await self.buy_premium_insight(client, token=token))
                strategy_engine.consume_premium(agent_id, tournament_id, 1.0)
            except Exception as exc:  # noqa: BLE001
                logger.debug("premium failed: %s", exc)

        if policy.allow_coach and len(results) < 2:
            try:
                res = await self.coach_remove_two(
                    client, token=token, question_id=question.get("id") or ""
                )
                results.append(res)
            except Exception as exc:  # noqa: BLE001
                logger.debug("coach failed: %s", exc)

        return results[:2]


tool_registry = ToolRegistry()
