"""
Task execution handler. Replace with your business logic (e.g. call external APIs, run jobs).
"""

import json
import asyncio


async def execute_task(task_id: str, _queue: str, payload: str, _metadata: dict) -> str:
    try:
        data = json.loads(payload) if payload.strip().startswith("{") else {"raw": payload}
        delay_ms = data.get("delay_ms", 0)
        if delay_ms:
            await asyncio.sleep(delay_ms / 1000.0)
        return json.dumps({"ok": True, "task_id": task_id})
    except Exception as e:
        raise RuntimeError(str(e))
