"""Tests for taskqueue.db.models (pure helpers and row conversion)."""

import json
from unittest.mock import MagicMock


from taskqueue.db.models import TaskStatus, _normalize_metadata, _row_to_task


class TestNormalizeMetadata:
    def test_none_returns_empty_dict(self):
        assert _normalize_metadata(None) == {}

    def test_dict_passthrough(self):
        d = {"a": 1, "b": "x"}
        assert _normalize_metadata(d) is d
        assert _normalize_metadata(d) == d

    def test_valid_json_string(self):
        d = {"k": "v"}
        assert _normalize_metadata(json.dumps(d)) == d

    def test_invalid_json_string_returns_empty(self):
        assert _normalize_metadata("not json") == {}
        assert _normalize_metadata("{") == {}

    def test_json_string_array_returns_empty(self):
        assert _normalize_metadata("[1,2,3]") == {}

    def test_non_dict_non_string_returns_empty(self):
        assert _normalize_metadata(42) == {}
        assert _normalize_metadata([]) == {}


class TestRowToTask:
    def test_row_to_task_normalizes_metadata_dict(self):
        row = MagicMock()
        row.__getitem__ = lambda s, k: {
            "task_id": "550e8400-e29b-41d4-a716-446655440000",
            "queue": "q1",
            "payload": "{}",
            "priority": 5,
            "status": "QUEUED",
            "attempt": 0,
            "max_retries": 3,
            "result": None,
            "error": None,
            "metadata": {"x": 1},
            "created_at": 1000,
            "updated_at": 1001,
            "started_at": None,
            "completed_at": None,
        }[k]
        row.get = row.__getitem__
        out = _row_to_task(row)
        assert out["metadata"] == {"x": 1}
        assert out["task_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert out["queue"] == "q1"

    def test_row_to_task_normalizes_metadata_json_string(self):
        row = MagicMock()
        row.get = (
            lambda k: json.dumps({"a": 1})
            if k == "metadata"
            else {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "queue": "q1",
                "payload": "{}",
                "priority": 5,
                "status": "SUCCESS",
                "attempt": 1,
                "max_retries": 3,
                "result": "ok",
                "error": None,
                "created_at": 1000,
                "updated_at": 2000,
                "started_at": 1500,
                "completed_at": 2000,
            }.get(k)
        )
        row.__getitem__ = lambda s, k: row.get(k) or (1000 if "at" in str(k) else None)
        out = _row_to_task(row)
        assert out["metadata"] == {"a": 1}


class TestTaskStatus:
    def test_status_values(self):
        assert TaskStatus.PENDING.value == "PENDING"
        assert TaskStatus.QUEUED.value == "QUEUED"
        assert TaskStatus.SUCCESS.value == "SUCCESS"
        assert TaskStatus.CANCELLED.value == "CANCELLED"
