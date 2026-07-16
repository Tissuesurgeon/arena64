from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def cache_set(key: str, value: str, ttl: int = 60) -> None:
    try:
        r = await get_redis()
        await r.set(key, value, ex=ttl)
    except Exception:
        pass


async def cache_get(key: str) -> str | None:
    try:
        r = await get_redis()
        return await r.get(key)
    except Exception:
        return None