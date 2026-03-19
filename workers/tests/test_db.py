"""Tests for worker.db (metadata normalization and helpers)."""

import json
from worker.db import _normalize_metadata


class TestNormalizeMetadata:
    def test_none_returns_empty_dict(self):
        assert _normalize_metadata(None) == {}

    def test_dict_passthrough(self):
        d = {"a": 1}
        assert _normalize_metadata(d) is d

    def test_valid_json_string(self):
        assert _normalize_metadata(json.dumps({"k": "v"})) == {"k": "v"}

    def test_invalid_json_returns_empty(self):
        assert _normalize_metadata("not json") == {}

    def test_non_dict_non_string_returns_empty(self):
        assert _normalize_metadata(42) == {}
