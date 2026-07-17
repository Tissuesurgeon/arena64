from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None
_redis_failed = False


async def get_redis() -> Redis:
    """Lazy Redis client with short timeouts so auth never hangs on a bad REDIS_URL."""
    global _redis, _redis_failed
    if _redis_failed:
        raise RuntimeError("redis unavailable")
    if _redis is None:
        _redis = Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
            retry_on_timeout=False,
        )
    return _redis


def _mark_failed() -> None:
    global _redis, _redis_failed
    _redis_failed = True
    _redis = None


async def cache_set(key: str, value: str, ttl: int = 60) -> None:
    try:
        r = await get_redis()
        await r.set(key, value, ex=ttl)
    except Exception:
        _mark_failed()


async def cache_get(key: str) -> str | None:
    if _redis_failed:
        return None
    try:
        r = await get_redis()
        return await r.get(key)
    except Exception:
        _mark_failed()
        return None
