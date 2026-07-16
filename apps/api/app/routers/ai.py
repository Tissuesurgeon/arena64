from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
async def ai_status(test: bool = False):
    """Check which LLM providers are reachable (Voya-style)."""
    settings = get_settings()
    ollama_up = False
    if settings.ollama_enabled:
        try:
            from app.integrations.ollama.client import OllamaClient

            ollama_up = await OllamaClient().is_available()
        except Exception:
            ollama_up = False

    payload: dict = {
        "ai_provider": settings.cloud_ai_provider,
        "fallback_chain": "ollama → qwen → heuristics",
        "qwen_configured": settings.qwen_configured,
        "qwen_model": settings.qwen_chat_model,
        "qwen_base_url": settings.qwen_base_url,
        "ollama_enabled": settings.ollama_enabled,
        "ollama_reachable": ollama_up,
        "ollama_model": settings.ollama_model,
        "ollama_base_url": settings.ollama_base_url,
    }

    if test and settings.qwen_configured:
        try:
            from app.integrations.qwen.client import QwenClient

            payload["qwen_health"] = await QwenClient().health_check()
        except Exception as exc:  # noqa: BLE001
            payload["qwen_health"] = {"ok": False, "error": str(exc)}

    return payload
