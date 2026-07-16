from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    """Load ``{name}.system.md`` from the prompts directory (Voya pattern)."""
    path = _PROMPT_DIR / f"{name}.system.md"
    return path.read_text(encoding="utf-8").strip()
