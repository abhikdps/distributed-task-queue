import json
import uuid
import time
import asyncpg  # type: ignore[import-untyped]
from typing import Optional, Any

from .config import config

_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            config.postgres_dsn,
            min_size=2,
            max_size=config.worker_concurrency + 2,
            command_timeout=10,
        )
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _normalize_metadata(md: Any) -> dict:
    """Ensure metadata from JSONB is a dict. asyncpg may return dict or JSON str."""
    if md is None:
        return {}
    if isinstance(md, dict):
        return md
    if isinstance(md, str):
        try:
            out = json.loads(md)
            return out if isinstance(out, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


async def get_task(task_id: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tasks WHERE task_id = $1", uuid.UUID(task_id))
    if row is None:
        return None
    md = _normalize_metadata(row.get("metadata"))
    return {
        "task_id": str(row["task_id"]),
        "queue": row["queue"],
        "payload": row["payload"],
        "priority": row["priority"],
        "status": row["status"],
        "attempt": row["attempt"],
        "max_retries": row["max_retries"],
        "metadata": md,
    }


async def set_running(task_id: str) -> None:
    now = int(time.time() * 1000)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET status = 'RUNNING', updated_at = $2, started_at = $2, attempt = attempt + 1 WHERE task_id = $1",
            uuid.UUID(task_id),
            now,
        )


async def set_success(task_id: str, result: str = "") -> None:
    now = int(time.time() * 1000)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET status = 'SUCCESS', result = $2, updated_at = $3, completed_at = $3 WHERE task_id = $1",
            uuid.UUID(task_id),
            result,
            now,
        )


async def set_failed(task_id: str, error: str) -> None:
    now = int(time.time() * 1000)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET status = 'FAILED', error = $2, updated_at = $3, completed_at = $3 WHERE task_id = $1",
            uuid.UUID(task_id),
            error,
            now,
        )


async def set_queued_retry(task_id: str) -> None:
    now = int(time.time() * 1000)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET status = 'QUEUED', updated_at = $2 WHERE task_id = $1",
            uuid.UUID(task_id),
            now,
        )
