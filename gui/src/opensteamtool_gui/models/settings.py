"""GUI settings stored in the SQLite settings table."""

from __future__ import annotations

import sqlite3


class Settings:
    KEY_STEAM_PATH = "steam_path"
    KEY_THEME = "theme"
    KEY_LANGUAGE = "language"

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
