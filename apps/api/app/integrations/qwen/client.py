"""Qwen models via Alibaba Cloud Model Studio (OpenAI-compatible API). Pattern from Voya."""

from __future__ import annotations

import time

from openai import AsyncOpenAI

from app.core.config import get_settings


class QwenError(Exception):
    pass


class QwenClient:
    """Chat through Model Studio / DashScope compatible-mode endpoints."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.qwen_api_key:
            raise QwenError(
                "Model Studio API key not configured (set QWEN_API_KEY or DASHSCOPE_API_KEY)"
            )
        self.settings = settings
        self.base_url = settings.qwen_base_url.rstrip("/")
        self.client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=self.base_url,
        )
        self.chat_model = settings.qwen_chat_model

    @staticmethod
    def is_configured() -> bool:
        return bool(get_settings().qwen_api_key)

    async def chat(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> str:
        kwargs: dict = {
            "model": model or self.chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = await self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise QwenError(self._format_error(exc)) from exc

        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise QwenError("Empty response from Model Studio")
        return content

    async def health_check(self) -> dict:
        started = time.perf_counter()
        reply = await self.chat(
            system="You are a health check. Reply with exactly: ok",
            user="ping",
            temperature=0,
            max_tokens=16,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "model": self.chat_model,
            "base_url": self.base_url,
            "reply_preview": reply[:80],
        }

    def _format_error(self, exc: Exception) -> str:
        message = str(exc).strip() or "Model Studio request failed"
        hints: list[str] = []
        lower = message.lower()
        if "401" in lower or ("invalid" in lower and "key" in lower):
            hints.append("Check QWEN_API_KEY / DASHSCOPE_API_KEY")
        if "404" in lower or "model" in lower:
            hints.append(f"Confirm {self.chat_model} is enabled in your Model Studio workspace")
        if hints:
            return f"{message} — {'; '.join(hints)}"
        return message
