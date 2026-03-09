import json
import uuid
import time
from enum import Enum
from typing import Optional, List, Any
import asyncpg  # type: ignore[import-untyped]

from .pool import get_pool


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id UUID PRIMARY KEY,
    queue TEXT NOT NULL,
    payload TEXT NOT NULL,
    priority INT NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempt INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    result TEXT,
    error TEXT,
    metadata JSONB DEFAULT '{}',
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    started_at BIGINT,
    completed_at BIGINT
);
CREATE INDEX IF NOT EXISTS idx_tasks_queue_status ON tasks(queue, status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(queue, priority DESC) WHERE status IN ('PENDING', 'QUEUED');
"""


async def create_tables() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TASKS_TABLE)


async def insert_task(
    queue: str,
    payload: str,
    priority: int = 5,
    max_retries: int = 3,
    metadata: Optional[dict] = None,
) -> str:
    task_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tasks (task_id, queue, payload, priority, status, max_retries, metadata, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 'PENDING', $5, $6, $7, $8)
            """,
            task_id,
            queue,
            payload,
            priority,
            max_retries,
            json.dumps(metadata or {}),
            now,
            now,
        )
    return task_id


async def get_task(task_id: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tasks WHERE task_id = $1", uuid.UUID(task_id))
    if row is None:
        return None
    return _row_to_task(row)


async def update_task_status(
    task_id: str,
    status: TaskStatus,
    *,
    attempt: Optional[int] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
    started_at: Optional[int] = None,
    completed_at: Optional[int] = None,
) -> None:
    now = int(time.time() * 1000)
    pool = get_pool()
    updates = ["status = $2", "updated_at = $3"]
    args: List[Any] = [task_id, status.value, now]
    n = 3
    if attempt is not None:
        n += 1
        updates.append(f"attempt = ${n}")
        args.append(attempt)
    if result is not None:
        n += 1
        updates.append(f"result = ${n}")
        args.append(result)
    if error is not None:
        n += 1
        updates.append(f"error = ${n}")
        args.append(error)
    if started_at is not None:
        n += 1
        updates.append(f"started_at = ${n}")
        args.append(started_at)
    if completed_at is not None:
        n += 1
        updates.append(f"completed_at = ${n}")
        args.append(completed_at)
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = $1",
            *args,
        )


async def list_tasks(
    queue: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[dict], int]:
    pool = get_pool()
    conditions = []
    args: List[Any] = []
    n = 0
    if queue:
        n += 1
        conditions.append(f"queue = ${n}")
        args.append(queue)
    if status:
        n += 1
        conditions.append(f"status = ${n}")
        args.append(status)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with pool.acquire() as conn:
        count_row = await conn.fetchrow(f"SELECT COUNT(*) AS c FROM tasks {where}", *args)
        total = count_row["c"] if count_row else 0
        args.extend([limit, offset])
        rows = await conn.fetch(
            f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ${n+1} OFFSET ${n+2}",
            *args,
        )
    tasks = [_row_to_task(r) for r in rows]
    return tasks, total


async def get_queue_stats(queue: str = "") -> dict:
    pool = get_pool()
    w = "WHERE queue = $1 AND " if queue else "WHERE "
    args: List[Any] = [queue] if queue else []
    today_start = int(time.time()) // 86400 * 86400 * 1000
    async with pool.acquire() as conn:
        pending = await conn.fetchval(
            f"SELECT COUNT(*) FROM tasks {w} status IN ('PENDING', 'QUEUED')",
            *args,
        )
        running = await conn.fetchval(
            f"SELECT COUNT(*) FROM tasks {w} status = 'RUNNING'",
            *args,
        )
        a1 = args + [today_start] if queue else [today_start]
        a2 = 2 if queue else 1
        completed = await conn.fetchval(
            f"SELECT COUNT(*) FROM tasks {w} status = 'SUCCESS' AND completed_at >= ${a2}",
            *a1,
        )
        failed = await conn.fetchval(
            f"SELECT COUNT(*) FROM tasks {w} status = 'FAILED' AND completed_at >= ${a2}",
            *a1,
        )
        p99_args: List[Any] = [today_start]
        p99_extra = " AND queue = $2" if queue else ""
        if queue:
            p99_args.append(queue)
        p99_row = await conn.fetchrow(
            f"""
            SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY (completed_at - started_at)) AS p99
            FROM tasks WHERE status = 'SUCCESS' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND completed_at >= $1{p99_extra}
            """,
            *p99_args,
        )
    p99_ms = float(p99_row["p99"] or 0)
    now_ms = int(time.time() * 1000)
    elapsed_sec = max(1.0, (now_ms - today_start) / 1000.0)
    throughput_per_sec = (completed or 0) / elapsed_sec
    return {
        "pending_count": pending or 0,
        "running_count": running or 0,
        "completed_today": completed or 0,
        "failed_today": failed or 0,
        "p99_latency_ms": round(p99_ms, 2),
        "throughput_per_sec": round(throughput_per_sec, 2),
        "by_priority": {},
    }


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


def _row_to_task(row: asyncpg.Record) -> dict:
    md = _normalize_metadata(row.get("metadata"))
    return {
        "task_id": str(row["task_id"]),
        "queue": row["queue"],
        "payload": row["payload"],
        "priority": row["priority"],
        "status": row["status"],
        "attempt": row["attempt"],
        "max_retries": row["max_retries"],
        "result": row["result"],
        "error": row["error"],
        "metadata": md or {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }
