"""Shared chat-LLM router (Voya pattern): Ollama → Qwen → None."""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def chat_with_fallback(
    *,
    system: str,
    user: str,
    json_mode: bool = False,
    temperature: float = 0.4,
    max_tokens: int = 512,
) -> tuple[str, str] | None:
    """Return ``(text, provider)`` from the first available LLM, or ``None``.

    Provider selection follows ``settings.cloud_ai_provider``:
    - ``rules``: skip LLMs entirely (heuristics only).
    - otherwise: try Ollama (local) when enabled, then Qwen (cloud) when configured.
    """
    settings = get_settings()
    provider = settings.cloud_ai_provider
    if provider == "rules":
        return None

    if settings.ollama_enabled and provider in ("auto", "ollama"):
        try:
            from app.integrations.ollama.client import OllamaClient

            client = OllamaClient()
            if await client.is_available():
                text = await client.chat(
                    system=system,
                    user=user,
                    temperature=temperature,
                    json_mode=json_mode,
                    max_tokens=max_tokens,
                )
                if text and text.strip():
                    return text.strip(), "ollama"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ollama chat failed, falling back: %s", exc)

    if settings.qwen_configured and provider in ("auto", "ollama", "qwen"):
        try:
            from app.integrations.qwen.client import QwenClient

            client = QwenClient()
            text = await client.chat(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )
            if text and text.strip():
                return text.strip(), "qwen"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qwen chat failed, falling back: %s", exc)

    return None
