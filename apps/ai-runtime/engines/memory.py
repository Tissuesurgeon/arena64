"""Memory Engine — inject career memory into decision context (not factual knowledge)."""

from __future__ import annotations

from typing import Any


class MemoryEngine:
    def context_for_decision(self, memory_summary: dict[str, Any] | None) -> dict[str, Any]:
        summary = memory_summary or {}
        return {
            "strengths": list(summary.get("strengths") or [])[-5:],
            "weaknesses": list(summary.get("weaknesses") or [])[-5:],
            "avg_confidence": summary.get("avg_confidence"),
            "category_hints": summary.get("category_stats") or summary.get("categories") or {},
            "recommendation": summary.get("recommendation"),
            "mcp_usage": summary.get("mcp_usage"),
            "premium_usage": summary.get("premium_usage"),
        }

    def should_prefer_research(self, memory_summary: dict[str, Any] | None, challenge_type: str) -> bool:
        """If memory marks a category as weak, prefer research when policy allows."""
        summary = memory_summary or {}
        weaknesses = [str(w).lower() for w in (summary.get("weaknesses") or [])]
        ct = (challenge_type or "").lower()
        if any(ct in w or w in ct for w in weaknesses):
            return True
        cats = summary.get("category_stats") or summary.get("categories") or {}
        if isinstance(cats, dict) and ct in cats:
            acc = cats[ct].get("accuracy") if isinstance(cats[ct], dict) else None
            if acc is not None and float(acc) < 0.5:
                return True
        return False


memory_engine = MemoryEngine()
