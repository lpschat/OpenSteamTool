"""Atomic file write helpers (tmp + os.replace)."""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding=encoding, newline="\n")
    os.replace(tmp, path)


def cleanup_stale_tmp(directory: Path) -> int:
    """Remove residual *.tmp files in directory (crash recovery). Returns count."""
    if not directory.exists():
        return 0
    removed = 0
    for entry in directory.iterdir():
        if entry.is_file() and entry.suffix == ".tmp":
            try:
                entry.unlink()
                removed += 1
            except OSError:
                pass
    return removed
