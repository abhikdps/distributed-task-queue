import json
from typing import Optional
from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from ..config import config

_producer: Optional[AIOKafkaProducer] = None


async def init_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=config.kafka_bootstrap_servers.split(","),
        )
        await _producer.start()
    return _producer


def get_producer() -> AIOKafkaProducer:
    if _producer is None:
        raise RuntimeError("Kafka producer not initialized")
    return _producer


async def close_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


async def enqueue_task(task_id: str, queue: str, payload: str, priority: int) -> None:
    """Send task to Kafka. Partition key by queue for ordering; priority in payload for consumer."""
    p = get_producer()
    value = json.dumps(
        {
            "task_id": task_id,
            "queue": queue,
            "payload": payload,
            "priority": priority,
        }
    ).encode("utf-8")
    await p.send_and_wait(
        config.kafka_topic_tasks,
        value=value,
        key=queue.encode("utf-8"),
    )
