"""GUI data directory resolution."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "OpenSteamTool-GUI"


def data_dir() -> Path:
    """Return %APPDATA%\\OpenSteamTool-GUI on Windows, ~/.local/share/... elsewhere."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home() / ".local" / "share"
    path = base / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "library.db"


def cache_dir() -> Path:
    path = data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
