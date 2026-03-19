"""Pytest configuration for workers."""

import pytest


@pytest.fixture(autouse=True)
def _env_for_tests(monkeypatch):
    """Minimal env so config doesn't fail when tests import worker modules."""
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monkeypatch.setenv("TASK_QUEUE_TOPIC", "tasks")
