"""Small JSON cache with TTL metadata."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


class JsonCache:
    def __init__(
        self,
        root: Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))

    def read(self, key: str, ttl: timedelta | None = None) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        cached_at = _parse_time(payload.get("cached_at"))
        if ttl is not None and cached_at is not None:
            if self._now() - cached_at > ttl:
                return None
        return payload.get("value")

    def write(self, key: str, value: Any) -> Path:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cached_at": self._now().isoformat(), "value": value}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def clear_prefix(self, prefix: str) -> int:
        target = self.root / prefix
        if target.is_file():
            target.unlink()
            return 1
        if not target.exists():
            return 0
        count = sum(1 for path in target.rglob("*") if path.is_file())
        shutil.rmtree(target)
        return count

    def size_bytes(self) -> int:
        return sum(path.stat().st_size for path in self.root.rglob("*") if path.is_file())

    def _path(self, key: str) -> Path:
        return self.root / key


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
