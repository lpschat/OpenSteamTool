"""Game / Depot / Token data classes + repository over SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from opensteamtool_gui.models.database import transaction
from opensteamtool_gui.services.lua_generator import AppEntry, DepotEntry, GameBundle


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Depot:
    depot_id: int
    owner_appid: int
    decryption_key: str | None = None
    manifest_gid: str | None = None
    key_source: str | None = None


@dataclass
class Game:
    appid: int
    name: str = ""
    type: str = "game"
    parent_appid: int | None = None
    header_image: str | None = None
    source: str | None = None
    fetched_at: str | None = None
    enabled: bool = True
    incomplete: bool = False
    managed: bool = True
    note: str | None = None
    depots: list[Depot] = field(default_factory=list)
    access_token: str | None = None
    app_ticket_hex: str | None = None
    e_ticket_hex: str | None = None
    stat_steam_id: str | None = None


def _row_to_game(row: sqlite3.Row) -> Game:
    return Game(
        appid=row["appid"],
        name=row["name"] or "",
        type=row["type"] or "game",
        parent_appid=row["parent_appid"],
        header_image=row["header_image"],
        source=row["source"],
        fetched_at=row["fetched_at"],
        enabled=bool(row["enabled"]),
        incomplete=bool(row["incomplete"]),
        managed=bool(row["managed"]),
        note=row["note"],
    )


def _row_to_depot(row: sqlite3.Row) -> Depot:
    return Depot(
        depot_id=row["depot_id"],
        owner_appid=row["owner_appid"],
        decryption_key=row["decryption_key"],
        manifest_gid=row["manifest_gid"],
        key_source=row["key_source"],
    )


class GameRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_game(self, g: Game) -> None:
        existing = self.conn.execute(
            "SELECT created_at FROM games WHERE appid=?", (g.appid,)
        ).fetchone()
        now = _now()
        with transaction(self.conn):
            if existing:
                self.conn.execute(
                    """
                    UPDATE games SET name=?, type=?, parent_appid=?, header_image=?,
                        source=?, fetched_at=?, enabled=?, incomplete=?, managed=?,
                        note=?, updated_at=?
                    WHERE appid=?
                    """,
                    (
                        g.name, g.type, g.parent_appid, g.header_image,
                        g.source, g.fetched_at, int(g.enabled), int(g.incomplete),
                        int(g.managed), g.note, now, g.appid,
                    ),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO games(appid, name, type, parent_appid, header_image,
                        source, fetched_at, enabled, incomplete, managed, note,
                        created_at, updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        g.appid, g.name, g.type, g.parent_appid, g.header_image,
                        g.source, g.fetched_at, int(g.enabled), int(g.incomplete),
                        int(g.managed), g.note, now, now,
                    ),
                )
            self.conn.execute("DELETE FROM depots WHERE owner_appid=?", (g.appid,))
            for d in g.depots:
                self.conn.execute(
                    """
                    INSERT INTO depots(depot_id, owner_appid, decryption_key,
                        manifest_gid, key_source, updated_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (d.depot_id, g.appid, d.decryption_key, d.manifest_gid,
                     d.key_source, now),
                )
            self._upsert_single(
                "access_tokens", "token", g.appid, g.access_token,
            )
            self._upsert_single(
                "app_tickets", "ticket_hex", g.appid, g.app_ticket_hex,
            )
            self._upsert_single(
                "e_tickets", "ticket_hex", g.appid, g.e_ticket_hex,
            )
            self._upsert_single(
                "stat_overrides", "steam_id", g.appid, g.stat_steam_id,
            )

    def _upsert_single(
        self, table: str, value_col: str, appid: int, value: str | None
    ) -> None:
        self.conn.execute(f"DELETE FROM {table} WHERE appid=?", (appid,))
        if value:
            self.conn.execute(
                f"INSERT INTO {table}(appid, {value_col}) VALUES(?,?)",
                (appid, value),
            )

    def delete_game(self, appid: int) -> None:
        with transaction(self.conn):
            self.conn.execute("DELETE FROM games WHERE appid=?", (appid,))

    def set_enabled_many(self, appids: list[int], enabled: bool) -> None:
        if not appids:
            return
        placeholders = ",".join("?" for _ in appids)
        now = _now()
        with transaction(self.conn):
            self.conn.execute(
                f"UPDATE games SET enabled=?, updated_at=? WHERE appid IN ({placeholders})",
                (int(enabled), now, *appids),
            )

    def delete_many(self, appids: list[int]) -> None:
        if not appids:
            return
        placeholders = ",".join("?" for _ in appids)
        with transaction(self.conn):
            self.conn.execute(f"DELETE FROM games WHERE appid IN ({placeholders})", appids)

    def get(self, appid: int) -> Game | None:
        row = self.conn.execute(
            "SELECT * FROM games WHERE appid=?", (appid,)
        ).fetchone()
        if not row:
            return None
        g = _row_to_game(row)
        g.depots = self._load_depots(appid)
        g.access_token = self._load_single("access_tokens", "token", appid)
        g.app_ticket_hex = self._load_single("app_tickets", "ticket_hex", appid)
        g.e_ticket_hex = self._load_single("e_tickets", "ticket_hex", appid)
        g.stat_steam_id = self._load_single("stat_overrides", "steam_id", appid)
        return g

    def _load_depots(self, owner_appid: int) -> list[Depot]:
        rows = self.conn.execute(
            "SELECT * FROM depots WHERE owner_appid=? ORDER BY depot_id", (owner_appid,)
        ).fetchall()
        return [_row_to_depot(r) for r in rows]

    def _load_single(self, table: str, value_col: str, appid: int) -> str | None:
        row = self.conn.execute(
            f"SELECT {value_col} FROM {table} WHERE appid=?", (appid,)
        ).fetchone()
        return row[value_col] if row else None

    def list_main_games(self) -> list[Game]:
        rows = self.conn.execute(
            "SELECT * FROM games WHERE parent_appid IS NULL ORDER BY name COLLATE NOCASE, appid"
        ).fetchall()
        result = []
        for r in rows:
            g = _row_to_game(r)
            g.depots = self._load_depots(g.appid)
            g.access_token = self._load_single("access_tokens", "token", g.appid)
            g.app_ticket_hex = self._load_single("app_tickets", "ticket_hex", g.appid)
            g.e_ticket_hex = self._load_single("e_tickets", "ticket_hex", g.appid)
            g.stat_steam_id = self._load_single("stat_overrides", "steam_id", g.appid)
            result.append(g)
        return result

    def list_dlcs(self, parent_appid: int) -> list[Game]:
        rows = self.conn.execute(
            "SELECT * FROM games WHERE parent_appid=? ORDER BY appid", (parent_appid,)
        ).fetchall()
        result = []
        for r in rows:
            g = _row_to_game(r)
            g.depots = self._load_depots(g.appid)
            g.access_token = self._load_single("access_tokens", "token", g.appid)
            g.app_ticket_hex = self._load_single("app_tickets", "ticket_hex", g.appid)
            g.e_ticket_hex = self._load_single("e_tickets", "ticket_hex", g.appid)
            g.stat_steam_id = self._load_single("stat_overrides", "steam_id", g.appid)
            result.append(g)
        return result


def to_bundle(main: Game, dlcs: list[Game]) -> GameBundle:
    """Build a lua_generator bundle from DB records."""
    return GameBundle(
        main=_to_app_entry(main),
        dlcs=[_to_app_entry(d) for d in dlcs],
    )


def _to_app_entry(g: Game) -> AppEntry:
    return AppEntry(
        appid=g.appid,
        name=g.name,
        enabled=g.enabled,
        depots=[
            DepotEntry(
                depot_id=d.depot_id,
                decryption_key=d.decryption_key,
                manifest_gid=d.manifest_gid,
            )
            for d in g.depots
        ],
        access_token=g.access_token,
        app_ticket_hex=g.app_ticket_hex,
        e_ticket_hex=g.e_ticket_hex,
        stat_steam_id=g.stat_steam_id,
    )
