"""Tests for taskqueue.api.servicer (gRPC service)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from taskqueue.api.servicer import TaskQueueServicer
from taskqueue.proto.gen import taskqueue_pb2


@pytest.fixture
def servicer():
    return TaskQueueServicer()


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.set_code = MagicMock()
    ctx.set_details = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_submit_task_success(servicer, mock_context):
    request = taskqueue_pb2.SubmitTaskRequest(  # type: ignore[attr-defined]
        queue="test-queue",
        payload='{"x": 1}',
        priority=5,
        max_retries=3,
    )
    with (
        patch("taskqueue.api.servicer.insert_task", new_callable=AsyncMock, return_value="tid-123"),
        patch("taskqueue.api.servicer.update_task_status", new_callable=AsyncMock),
        patch("taskqueue.api.servicer.enqueue_task", new_callable=AsyncMock),
        patch("taskqueue.api.servicer.metrics") as metrics,
    ):
        metrics.__getitem__ = lambda self, k: MagicMock(labels=MagicMock(return_value=MagicMock(inc=MagicMock())))
        response = await servicer.SubmitTask(request, mock_context)
    assert response.task_id == "tid-123"
    assert response.status == "QUEUED"


@pytest.mark.asyncio
async def test_health_check_returns_response(servicer, mock_context):
    request = taskqueue_pb2.HealthCheckRequest()  # type: ignore[attr-defined]
    with (
        patch(
            "taskqueue.api.servicer._health",
            new_callable=AsyncMock,
            return_value={"db": "ok", "redis": "ok", "kafka": "ok"},
        ),
    ):
        response = await servicer.HealthCheck(request, mock_context)
    assert response.status in ("SERVING", "NOT_SERVING")
    assert "db" in response.checks or "error" in response.checks
