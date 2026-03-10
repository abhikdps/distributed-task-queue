import json
from typing import Optional
import redis.asyncio as redis
from ..config import config

_client: Optional[redis.Redis] = None
TTL_TASK_CACHE = 60  # seconds


async def init_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(config.redis_url, decode_responses=True)
    return _client


def get_redis() -> redis.Redis:
    if _client is None:
        raise RuntimeError("Redis not initialized; call init_redis() first")
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _task_key(task_id: str) -> str:
    return f"taskqueue:task:{task_id}"


async def cache_task(task_id: str, task_data: dict) -> None:
    r = get_redis()
    await r.setex(
        _task_key(task_id),
        TTL_TASK_CACHE,
        json.dumps(task_data),
    )


async def get_cached_task(task_id: str) -> Optional[dict]:
    r = get_redis()
    raw = await r.get(_task_key(task_id))
    if raw is None:
        return None
    return json.loads(raw)


async def invalidate_task(task_id: str) -> None:
    r = get_redis()
    await r.delete(_task_key(task_id))
