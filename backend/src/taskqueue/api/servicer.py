import time
from typing import Any

import grpc  # type: ignore[import-untyped]
from taskqueue.proto.gen import taskqueue_pb2, taskqueue_pb2_grpc  # type: ignore[import-untyped]

from ..db import (
    insert_task,
    get_task,
    update_task_status,
    list_tasks as db_list_tasks,
    get_queue_stats as db_get_queue_stats,
    TaskStatus,
)
from ..db.pool import get_pool
from ..cache import get_cached_task, cache_task, invalidate_task, get_redis
from ..broker import enqueue_task, get_producer
from ..observability.metrics import metrics
from ..observability.logging import get_logger

logger = get_logger("api.servicer")
TASK_NOT_FOUND_MSG = "Task not found"


def _task_to_proto(t: dict) -> Any:
    r = taskqueue_pb2.GetTaskResponse(  # type: ignore[attr-defined]
        task_id=t["task_id"],
        status=t["status"],
        payload=t["payload"],
        priority=t["priority"],
        attempt=t["attempt"],
        max_retries=t["max_retries"],
        result=t["result"] or "",
        error=t["error"] or "",
        created_at=t["created_at"],
        updated_at=t["updated_at"],
        started_at=t["started_at"] or 0,
        completed_at=t["completed_at"] or 0,
    )
    for k, v in (t.get("metadata") or {}).items():
        r.metadata[k] = str(v)
    return r


class TaskQueueServicer(taskqueue_pb2_grpc.TaskQueueServiceServicer):  # type: ignore[override]
    async def SubmitTask(self, request, context):
        start = time.perf_counter()
        try:
            task_id, status = await _submit_task(request)
            metrics["api_request_duration_seconds"].labels(method="SubmitTask").observe(time.perf_counter() - start)
            return taskqueue_pb2.SubmitTaskResponse(task_id=task_id, status=status)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("SubmitTask failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise

    async def GetTask(self, request, context):
        start = time.perf_counter()
        try:
            t = await _get_task(request.task_id)
            metrics["api_request_duration_seconds"].labels(method="GetTask").observe(time.perf_counter() - start)
            if t is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(TASK_NOT_FOUND_MSG)
                raise ValueError(TASK_NOT_FOUND_MSG)
            return _task_to_proto(t)
        except Exception as e:
            if "not found" in str(e).lower():
                raise
            logger.exception("GetTask failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise

    async def ListTasks(self, request, context):
        start = time.perf_counter()
        try:
            tasks, total = await _list_tasks(request)
            metrics["api_request_duration_seconds"].labels(method="ListTasks").observe(time.perf_counter() - start)
            return taskqueue_pb2.ListTasksResponse(  # type: ignore[attr-defined]
                tasks=[_task_to_proto(t) for t in tasks],
                total=total,
            )
        except Exception as e:
            logger.exception("ListTasks failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise

    async def CancelTask(self, request, context):
        start = time.perf_counter()
        try:
            cancelled, msg = await _cancel_task(request.task_id)
            metrics["api_request_duration_seconds"].labels(method="CancelTask").observe(time.perf_counter() - start)
            return taskqueue_pb2.CancelTaskResponse(cancelled=cancelled, message=msg)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("CancelTask failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise

    async def GetQueueStats(self, request, context):
        start = time.perf_counter()
        try:
            s = await _get_queue_stats(request.queue or "")
            metrics["api_request_duration_seconds"].labels(method="GetQueueStats").observe(time.perf_counter() - start)
            r = taskqueue_pb2.GetQueueStatsResponse(  # type: ignore[attr-defined]
                pending_count=s["pending_count"],
                running_count=s["running_count"],
                completed_today=s["completed_today"],
                failed_today=s["failed_today"],
                p99_latency_ms=s["p99_latency_ms"],
                throughput_per_sec=s["throughput_per_sec"],
            )
            for k, v in (s.get("by_priority") or {}).items():
                r.by_priority[k] = v
            return r
        except Exception as e:
            logger.exception("GetQueueStats failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise

    async def HealthCheck(self, request, context):
        try:
            checks = await _health()
            status = "SERVING" if all(c == "ok" for c in checks.values()) else "NOT_SERVING"
            r = taskqueue_pb2.HealthCheckResponse(status=status)  # type: ignore[attr-defined]
            for k, v in checks.items():
                r.checks[k] = v
            return r
        except Exception:
            return taskqueue_pb2.HealthCheckResponse(status="NOT_SERVING", checks={"error": "check failed"})  # type: ignore[attr-defined]


async def _submit_task(request) -> tuple[str, str]:
    queue = request.queue or "default"
    priority = request.priority if request.priority else 5
    max_retries = request.max_retries if request.max_retries else 3
    metadata = dict(request.metadata) if request.metadata else None
    task_id = await insert_task(
        queue=queue,
        payload=request.payload,
        priority=priority,
        max_retries=max_retries,
        metadata=metadata,
    )
    await update_task_status(task_id, TaskStatus.QUEUED)
    await enqueue_task(task_id, queue, request.payload, priority)
    metrics["tasks_submitted_total"].labels(queue=queue).inc()  # type: ignore[union-attr]
    metrics["queue_depth"].labels(queue=queue).inc()  # type: ignore[union-attr]
    return task_id, "QUEUED"


async def _get_task(task_id: str) -> dict | None:
    cached = await get_cached_task(task_id)
    if cached is not None:
        return cached
    t = await get_task(task_id)
    if t is not None:
        await cache_task(task_id, t)
    return t


async def _list_tasks(request) -> tuple[list, int]:
    return await db_list_tasks(
        queue=request.queue or "",
        status=request.status or "",
        limit=request.limit or 50,
        offset=request.offset or 0,
    )


async def _cancel_task(task_id: str) -> tuple[bool, str]:
    t = await get_task(task_id)
    if t is None:
        return False, TASK_NOT_FOUND_MSG
    if t["status"] not in ("PENDING", "QUEUED", "RUNNING"):
        return False, f"Task already {t['status']}"
    await update_task_status(task_id, TaskStatus.CANCELLED)
    await invalidate_task(task_id)
    return True, "Cancelled"


async def _get_queue_stats(queue: str) -> dict:
    return await db_get_queue_stats(queue)


async def _health() -> dict:
    checks = {}
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = str(e)
    try:
        r = get_redis()
        await r.ping()  # type: ignore[misc]
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)
    try:
        get_producer()
        checks["kafka"] = "ok"
    except Exception as e:
        checks["kafka"] = str(e)
    return checks
