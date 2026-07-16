"""SkillsRegistry — load packages/agent-skills/*/SKILL.md (SlackClaw pattern)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    content: str


def _default_skills_dirs() -> list[Path]:
    """Resolve skills paths for monorepo checkout and Docker (/runtime/skills/…)."""
    here = Path(__file__).resolve()
    dirs: list[Path] = [
        Path("/agent-skills"),  # baked into backend / AI-runtime images
    ]
    # Walk up looking for packages/agent-skills (local: …/arena64/packages/…)
    for parent in here.parents:
        candidate = parent / "packages" / "agent-skills"
        if candidate.is_dir():
            dirs.append(candidate)
            break
    return dirs


class SkillsRegistry:
    def __init__(self, skills_dir: Path | None = None) -> None:
        candidates = [skills_dir, *_default_skills_dirs()]
        self.skills_dir = next(
            (p for p in candidates if p and p.exists()),
            Path("/agent-skills"),
        )
        self._skills: dict[str, Skill] = {}
        self._load()

    def _load(self) -> None:
        if not self.skills_dir.exists():
            return
        for skill_path in self.skills_dir.glob("*/SKILL.md"):
            content = skill_path.read_text(encoding="utf-8")
            name = skill_path.parent.name
            description = ""
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    content = parts[2].strip()
                    for line in frontmatter.splitlines():
                        if line.startswith("description:"):
                            description = line.split(":", 1)[1].strip()
            self._skills[name] = Skill(name=name, description=description, content=content)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def prompt_for(self, name: str) -> str:
        skill = self.get(name)
        return skill.content if skill else ""

    def competitor_prompt(self) -> str:
        return self.prompt_for("arena64-competitor") or self.prompt_for("arena64-player-research")

    def all_names(self) -> list[str]:
        return list(self._skills.keys())


skills_registry = SkillsRegistry()
