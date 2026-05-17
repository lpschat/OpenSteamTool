"""SQLite connection + schema migrations (WAL mode)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from opensteamtool_gui.utils.paths import db_path

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS games (
    appid        INTEGER PRIMARY KEY,
    name         TEXT NOT NULL DEFAULT '',
    type         TEXT NOT NULL DEFAULT 'game',
    parent_appid INTEGER REFERENCES games(appid),
    header_image TEXT,
    source       TEXT,
    fetched_at   TEXT,
    enabled      INTEGER NOT NULL DEFAULT 1,
    incomplete   INTEGER NOT NULL DEFAULT 0,
    managed      INTEGER NOT NULL DEFAULT 1,
    note         TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_parent ON games(parent_appid);
CREATE INDEX IF NOT EXISTS idx_games_type   ON games(type);

CREATE TABLE IF NOT EXISTS depots (
    depot_id        INTEGER PRIMARY KEY,
    owner_appid     INTEGER NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    decryption_key  TEXT,
    manifest_gid    TEXT,
    key_source      TEXT,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_depots_owner ON depots(owner_appid);

CREATE TABLE IF NOT EXISTS access_tokens (
    appid INTEGER PRIMARY KEY REFERENCES games(appid) ON DELETE CASCADE,
    token TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_tickets (
    appid INTEGER PRIMARY KEY REFERENCES games(appid) ON DELETE CASCADE,
    ticket_hex TEXT NOT NULL,
    written_to_registry_at TEXT
);

CREATE TABLE IF NOT EXISTS e_tickets (
    appid INTEGER PRIMARY KEY REFERENCES games(appid) ON DELETE CASCADE,
    ticket_hex TEXT NOT NULL,
    written_to_registry_at TEXT
);

CREATE TABLE IF NOT EXISTS stat_overrides (
    appid INTEGER PRIMARY KEY REFERENCES games(appid) ON DELETE CASCADE,
    steam_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registry_backups (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    appid        INTEGER NOT NULL,
    value_name   TEXT NOT NULL,
    value_hex    TEXT,
    backed_up_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

MIGRATIONS: list[str] = [SCHEMA_V1]


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations. Returns the new user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    target = len(MIGRATIONS)
    if current >= target:
        return current
    for i in range(current, target):
        conn.executescript(MIGRATIONS[i])
        conn.execute(f"PRAGMA user_version = {i + 1}")
    return target


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
