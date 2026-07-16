"""Category-aware research helpers for competitor skills."""

from __future__ import annotations

CATEGORY_SKILL = {
    "PLAYER_ID": "arena64-player-research",
    "FOOTBALL": "arena64-team-history",
    "STADIUM": "arena64-stadium",
    "FLAG": "arena64-team-history",
    "FORMATION": "arena64-tournament-rules",
    "MEMORY": "arena64-tournament-rules",
}


def skill_name_for_category(challenge_type: str) -> str:
    return CATEGORY_SKILL.get(str(challenge_type or "").upper(), "arena64-competitor")
