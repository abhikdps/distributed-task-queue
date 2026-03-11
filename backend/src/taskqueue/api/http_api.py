"""
Minimal HTTP JSON API for the dashboard. Primary API remains gRPC.
"""

import time
from aiohttp import web
from ..db.models import (
    get_task,
    list_tasks as db_list_tasks,
    get_queue_stats,
    insert_task,
    update_task_status,
    TaskStatus,
)
from ..broker import enqueue_task
from ..cache import get_cached_task
from ..observability.metrics import metrics


async def _get_stats(queue: str = ""):
    return await get_queue_stats(queue)


async def _list_tasks(queue: str = "", status: str = "", limit: int = 50, offset: int = 0):
    return await db_list_tasks(queue=queue, status=status, limit=limit, offset=offset)


async def _get_task(task_id: str):
    c = await get_cached_task(task_id)
    if c:
        return c
    return await get_task(task_id)


def _task_to_dict(t: dict) -> dict:
    return {
        "task_id": t["task_id"],
        "status": t["status"],
        "payload": t["payload"],
        "priority": t["priority"],
        "attempt": t["attempt"],
        "max_retries": t["max_retries"],
        "result": t.get("result") or "",
        "error": t.get("error") or "",
        "created_at": t["created_at"],
        "updated_at": t["updated_at"],
        "started_at": t.get("started_at") or 0,
        "completed_at": t.get("completed_at") or 0,
        "queue": t.get("queue", "default"),
    }


async def handle_stats(_: web.Request) -> web.Response:
    try:
        data = await _get_stats("")
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_tasks(request: web.Request) -> web.Response:
    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))
        queue = request.query.get("queue", "")
        status = request.query.get("status", "")
        tasks, total = await _list_tasks(queue=queue, status=status, limit=limit, offset=offset)
        return web.json_response({"tasks": [_task_to_dict(t) for t in tasks], "total": total})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_submit(request: web.Request) -> web.Response:
    start = time.perf_counter()
    try:
        body = await request.json()
        queue = body.get("queue", "default")
        payload = body.get("payload", "{}")
        priority = int(body.get("priority", 5))
        max_retries = int(body.get("max_retries", 3))
        task_id = await insert_task(queue=queue, payload=payload, priority=priority, max_retries=max_retries)
        await update_task_status(task_id, TaskStatus.QUEUED)
        await enqueue_task(task_id, queue, payload, priority)
        metrics["tasks_submitted_total"].labels(queue=queue).inc()
        metrics["queue_depth"].labels(queue=queue).inc()
        metrics["api_request_duration_seconds"].labels(method="SubmitTask").observe(time.perf_counter() - start)
        return web.json_response({"task_id": task_id, "status": "QUEUED"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_get("/api/tasks", handle_tasks)
    app.router.add_post("/api/submit", handle_submit)
    return app
