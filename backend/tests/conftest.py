"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _env_for_tests(monkeypatch):
    """Avoid loading real .env in tests; set minimal env so config doesn't fail."""
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
