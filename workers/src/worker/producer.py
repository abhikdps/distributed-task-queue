from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from .config import config
import json

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(bootstrap_servers=config.kafka_bootstrap_servers.split(","))
        await _producer.start()
    return _producer


async def enqueue_task(task_id: str, queue: str, payload: str, priority: int) -> None:
    p = await get_producer()
    value = json.dumps({"task_id": task_id, "queue": queue, "payload": payload, "priority": priority}).encode("utf-8")
    await p.send_and_wait(config.kafka_topic_tasks, value=value, key=queue.encode("utf-8"))
