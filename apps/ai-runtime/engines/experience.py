"""Experience Recorder — write decision logs for spectator explainability."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("arena64-ai-runtime.experience")


class ExperienceRecorder:
    def __init__(self, api_url: str, service_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.service_key = service_key

    async def record(
        self,
        client: httpx.AsyncClient,
        *,
        agent_id: str,
        match_id: str,
        round_id: str,
        question_id: str,
        decision: dict[str, Any],
        latency_ms: int,
        accelerated: bool,
        is_correct: bool | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "agent_id": agent_id,
            "match_id": match_id,
            "round_id": round_id,
            "question_id": question_id,
            "option_id": decision.get("option_id"),
            "confidence": float(decision.get("confidence") or 0),
            "used_mcp": bool(decision.get("want_mcp") or "researchKnowledge" in (decision.get("skills_used") or []) or "researchByCategory" in (decision.get("skills_used") or [])),
            "used_premium": bool(decision.get("want_premium") or "buyPremiumInsight" in (decision.get("skills_used") or [])),
            "used_coach_credit": bool(decision.get("want_coach") or "coachRemoveTwo" in (decision.get("skills_used") or [])),
            "reasoning": str(decision.get("reasoning") or "")[:2000],
            "latency_ms": latency_ms,
            "accelerated": accelerated,
        }
        if is_correct is not None:
            body["is_correct"] = is_correct
        try:
            await client.post(
                f"{self.api_url}/api/agents/decisions",
                headers={
                    "Content-Type": "application/json",
                    "X-Service-Key": self.service_key,
                },
                json=body,
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("experience record failed: %s", exc)
