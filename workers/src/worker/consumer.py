import json
import time
import asyncio
from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]

from .config import config
from .db import init_pool, close_pool, get_task, set_running, set_success, set_failed, set_queued_retry
from .execute import execute_task
from .metrics import metrics
from .retry import next_delay_seconds
from .logging import get_logger

logger = get_logger("worker.consumer")


async def process_message(msg) -> None:
    try:
        body = json.loads(msg.value.decode("utf-8"))
    except Exception as e:
        logger.warning("Invalid message", error=str(e))
        return
    task_id = body.get("task_id")
    queue = body.get("queue", "default")
    payload = body.get("payload", "")
    priority = body.get("priority", 5)
    if not task_id:
        logger.warning("Missing task_id in message")
        return

    t = await get_task(task_id)
    if t is None:
        logger.warning("Task not found", task_id=task_id)
        return
    if t["status"] not in ("QUEUED", "PENDING"):
        logger.info("Task already processed", task_id=task_id, status=t["status"])
        return

    await set_running(task_id)
    start = time.perf_counter()
    try:
        result = await execute_task(task_id, queue, payload, t.get("metadata") or {})
        await set_success(task_id, result)
        latency = time.perf_counter() - start
        metrics["task_latency_seconds"].labels(queue=queue).observe(latency)  # type: ignore[attr-defined]
        metrics["tasks_completed_total"].labels(queue=queue, status="success").inc()  # type: ignore[attr-defined]
        metrics["queue_depth"].labels(queue=queue).dec()  # type: ignore[attr-defined]
        logger.info("Task completed", task_id=task_id, queue=queue, latency_ms=latency * 1000)
    except Exception as e:
        attempt = t["attempt"] + 1
        max_retries = t.get("max_retries") or config.worker_max_retries
        if attempt < max_retries:
            await set_queued_retry(task_id)
            delay = next_delay_seconds(attempt - 1)
            logger.warning("Task failed, will retry", task_id=task_id, queue=queue, attempt=attempt, delay_sec=delay)
            await asyncio.sleep(delay)
            from .producer import enqueue_task as re_enqueue

            await re_enqueue(task_id, queue, payload, priority)
            return
        await set_failed(task_id, str(e))
        metrics["tasks_completed_total"].labels(queue=queue, status="failed").inc()  # type: ignore[attr-defined]
        metrics["queue_depth"].labels(queue=queue).dec()  # type: ignore[attr-defined]
        logger.exception("Task failed (max retries)", task_id=task_id, queue=queue)


def _kafka_hint() -> str:
    return (
        "Start Kafka first: from project root run  podman compose up -d  (or  ./compose.sh up -d).\n"
        "Wait 30–60 seconds for Kafka to be ready, then run the worker again."
    )


async def run_consumer() -> None:
    await init_pool()
    bootstrap = config.kafka_bootstrap_servers.split(",")
    max_attempts = 12
    consumer = None
    for attempt in range(1, max_attempts + 1):
        consumer = AIOKafkaConsumer(
            config.kafka_topic_tasks,
            bootstrap_servers=bootstrap,
            group_id=config.kafka_consumer_group,
            auto_offset_reset="earliest",
        )
        try:
            await asyncio.wait_for(consumer.start(), timeout=15.0)
            logger.info("Consumer started", topic=config.kafka_topic_tasks)
            break
        except (asyncio.TimeoutError, OSError, Exception) as e:
            try:
                await consumer.stop()
            except Exception:
                pass
            consumer = None
            if attempt == max_attempts:
                await close_pool()
                raise SystemExit(
                    f"Kafka not reachable at {config.kafka_bootstrap_servers} after {max_attempts} attempts.\n"
                    f"Last error: {e}\n{_kafka_hint()}"
                ) from e
            logger.warning(
                "Kafka not ready, retrying",
                attempt=attempt,
                max_attempts=max_attempts,
                hint="Ensure 'podman compose up -d' is running and Kafka is up (wait ~30s).",
            )
            await asyncio.sleep(5.0)
    if consumer is None:
        await close_pool()
        raise SystemExit(f"Kafka connection failed.\n{_kafka_hint()}")

    try:
        async for msg in consumer:
            await process_message(msg)
    finally:
        await consumer.stop()
        await close_pool()
