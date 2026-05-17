"""Tests for small JSON cache helpers used by fetchers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from opensteamtool_gui.utils.cache import JsonCache


def test_json_cache_returns_fresh_value(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path, now=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc))
    cache.write("appdetails/730.json", {"name": "CS2"})

    value = cache.read("appdetails/730.json", ttl=timedelta(days=7))

    assert value == {"name": "CS2"}


def test_json_cache_treats_expired_value_as_missing(tmp_path: Path) -> None:
    current = datetime(2026, 1, 2, tzinfo=timezone.utc)
    cache = JsonCache(tmp_path, now=lambda: current)
    cache.write("sudama_keys.json", {"730": {}})
    later = current + timedelta(days=2)
    expired_cache = JsonCache(tmp_path, now=lambda: later)

    value = expired_cache.read("sudama_keys.json", ttl=timedelta(hours=24))

    assert value is None


def test_json_cache_reports_size_and_clears_prefix(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    cache.write("headers/730.jpg.json", {"path": "x"})
    cache.write("appdetails/730.json", {"name": "CS2"})

    removed = cache.clear_prefix("headers")

    assert removed == 1
    assert cache.size_bytes() > 0
    assert cache.read("headers/730.jpg.json") is None
    assert cache.read("appdetails/730.json") == {"name": "CS2"}
