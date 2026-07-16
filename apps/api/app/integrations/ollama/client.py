"""Local LLM via Ollama (https://ollama.com). Pattern from Voya."""

from __future__ import annotations

import httpx

from app.core.config import get_settings


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout_seconds = settings.ollama_timeout_seconds

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.4,
        json_mode: bool = False,
        max_tokens: int = 512,
    ) -> str:
        payload: dict = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise OllamaError(
                f"Ollama timed out after {self.timeout_seconds:.0f}s "
                f"(model={payload['model']}). Try a smaller model or increase OLLAMA_TIMEOUT_SECONDS."
            ) from exc
        except httpx.ConnectError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.base_url}. Is `ollama serve` running?"
            ) from exc

        if response.status_code == 404:
            raise OllamaError(
                f"Model '{payload['model']}' not found. Run: ollama pull {payload['model']}"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:200] if response.text else exc.response.status_code
            raise OllamaError(f"Ollama HTTP error: {detail}") from exc

        data = response.json()
        message = data.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            content = (message.get("thinking") or "").strip()
        if not content:
            raise OllamaError("Empty response from Ollama")
        return content
