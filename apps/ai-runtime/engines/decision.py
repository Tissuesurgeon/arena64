"""Decision Engine — confidence + option selection; re-decide after skills."""

from __future__ import annotations

import json
import logging
import os
import random
import re
from typing import Any

import httpx

from engines.strategy import ActionPolicy

logger = logging.getLogger("arena64-ai-runtime.decision")

LLM_ENABLED = os.getenv("RUNTIME_LLM_ENABLED", "true").lower() in ("1", "true", "yes")

_DEFAULT_SYSTEM = """You are an Arena64 football intelligence agent.
Reply with STRICT JSON only:
{"confidence":0.0-1.0,"option_id":"<id or null>","reasoning":"short","want_mcp":false,"want_premium":false}
"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        raise


def accelerated_pick(question: dict, strategy: dict) -> dict:
    options = question.get("options") or []
    if not options:
        return {
            "confidence": 0.2,
            "option_id": None,
            "reasoning": "no options",
            "skills_used": [],
        }
    risk = strategy.get("risk_level", "medium")
    if risk == "high":
        idx = random.randrange(len(options))
    elif risk == "low":
        idx = 0
    else:
        idx = random.choice([0, 0, min(1, len(options) - 1)])
    conf = {"low": 0.72, "medium": 0.55, "high": 0.4}.get(risk, 0.55)
    return {
        "confidence": conf,
        "option_id": options[idx]["id"],
        "reasoning": f"Accelerated {risk} pick",
        "skills_used": [],
    }


class DecisionEngine:
    def __init__(self, system_prompt: str | None = None) -> None:
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM

    async def llm_decide(self, prompt: str) -> dict:
        if not LLM_ENABLED:
            return {}
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
        model = os.getenv("OLLAMA_MODEL", "qwen2.5")
        try:
            async with httpx.AsyncClient(timeout=40) as c:
                r = await c.post(
                    f"{base}/chat/completions",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.2,
                    },
                )
                if r.status_code >= 400:
                    return {}
                content = r.json()["choices"][0]["message"]["content"]
                return _parse_json(content)
        except Exception as exc:  # noqa: BLE001
            logger.debug("LLM unavailable: %s", exc)
            return {}

    async def initial(
        self,
        *,
        question: dict,
        strategy: dict,
        memory_ctx: dict,
        policy: ActionPolicy,
        skill_prompt: str = "",
    ) -> dict:
        if policy.accelerated:
            return accelerated_pick(question, strategy)

        payload = {
            "strategy": strategy,
            "memory": memory_ctx,
            "challenge_type": question.get("challenge_type"),
            "prompt": question.get("prompt"),
            "options": question.get("options"),
            "skill_guidance": skill_prompt[:1500] if skill_prompt else None,
        }
        decision = await self.llm_decide(json.dumps(payload))
        if not decision:
            decision = accelerated_pick(question, strategy)
        decision["skills_used"] = list(decision.get("skills_used") or [])
        return self._validate(decision, question, strategy)

    async def redecide(
        self,
        *,
        question: dict,
        strategy: dict,
        memory_ctx: dict,
        prior: dict,
        tool_results: list[dict],
        policy: ActionPolicy,
    ) -> dict:
        """Re-run decision with tool outputs — research must influence option choice."""
        if policy.accelerated or not tool_results:
            return prior

        payload = {
            "strategy": strategy,
            "memory": memory_ctx,
            "challenge_type": question.get("challenge_type"),
            "prompt": question.get("prompt"),
            "options": question.get("options"),
            "prior_decision": {
                "option_id": prior.get("option_id"),
                "confidence": prior.get("confidence"),
                "reasoning": prior.get("reasoning"),
            },
            "tool_results": tool_results,
            "instruction": "Revise option_id using tool_results when helpful. Reply JSON only.",
        }
        revised = await self.llm_decide(json.dumps(payload))
        if not revised:
            # Heuristic: if research snippets mention an option label, boost that option
            revised = dict(prior)
            labels = {o["id"]: o.get("label", "").lower() for o in (question.get("options") or [])}
            blob = json.dumps(tool_results).lower()
            for oid, label in labels.items():
                if label and len(label) > 2 and label in blob:
                    revised["option_id"] = oid
                    revised["confidence"] = min(0.95, float(prior.get("confidence") or 0.5) + 0.18)
                    revised["reasoning"] = (str(prior.get("reasoning") or "") + " | tool-informed")[:500]
                    break
            else:
                revised["confidence"] = min(0.95, float(prior.get("confidence") or 0.5) + 0.08)
                revised["reasoning"] = (str(prior.get("reasoning") or "") + " | tools consulted")[:500]
        skills = list(prior.get("skills_used") or [])
        for t in tool_results:
            name = t.get("tool")
            if name and name not in skills:
                skills.append(name)
        revised["skills_used"] = skills
        return self._validate(revised, question, strategy)

    def needs_help(self, decision: dict, policy: ActionPolicy) -> bool:
        conf = float(decision.get("confidence") or 0.5)
        gap = policy.confidence_threshold - conf
        if policy.skill_style == "aggressive":
            return gap > 0.2  # only when far below threshold
        if policy.skill_style == "analyst":
            return gap > -0.05 or conf < 0.75
        return conf < policy.confidence_threshold

    def _validate(self, decision: dict, question: dict, strategy: dict) -> dict:
        opt_ids = {o["id"] for o in (question.get("options") or [])}
        if decision.get("option_id") not in opt_ids:
            fallback = accelerated_pick(question, strategy)
            decision["option_id"] = fallback["option_id"]
            decision["confidence"] = float(decision.get("confidence") or fallback["confidence"])
        decision.setdefault("reasoning", "")
        decision.setdefault("skills_used", [])
        return decision


decision_engine = DecisionEngine()
