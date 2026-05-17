"""AppTicket / ETicket registry IO with SQLite backups."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from opensteamtool_gui.utils.hex_validate import is_hex

VALID_VALUES = {"AppTicket", "ETicket"}


class RegistryError(RuntimeError):
    """Raised for invalid ticket registry operations."""


class RegistryBackend(Protocol):
    def read_value(self, appid: int, value_name: str) -> bytes | None: ...
    def write_value(self, appid: int, value_name: str, value: bytes) -> None: ...
    def delete_value(self, appid: int, value_name: str) -> None: ...


@dataclass
class MemoryRegistryBackend:
    values: dict[tuple[int, str], bytes] = field(default_factory=dict)

    def read_value(self, appid: int, value_name: str) -> bytes | None:
        return self.values.get((appid, value_name))

    def write_value(self, appid: int, value_name: str, value: bytes) -> None:
        self.values[(appid, value_name)] = value

    def delete_value(self, appid: int, value_name: str) -> None:
        self.values.pop((appid, value_name), None)


class WinRegistryBackend:
    def read_value(self, appid: int, value_name: str) -> bytes | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _key(appid)) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return bytes(value)
        except FileNotFoundError:
            return None

    def write_value(self, appid: int, value_name: str, value: bytes) -> None:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _key(appid)) as key:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_BINARY, value)

    def delete_value(self, appid: int, value_name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                _key(appid),
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, value_name)
        except FileNotFoundError:
            return


def write_ticket(
    conn: sqlite3.Connection,
    backend: RegistryBackend,
    appid: int,
    value_name: str,
    ticket_hex: str,
) -> None:
    _validate(value_name, ticket_hex)
    _backup(conn, backend, appid, value_name)
    backend.write_value(appid, value_name, bytes.fromhex(ticket_hex))
    _mark_written(conn, appid, value_name)


def clear_ticket(
    conn: sqlite3.Connection,
    backend: RegistryBackend,
    appid: int,
    value_name: str,
) -> None:
    _ensure_value_name(value_name)
    _backup(conn, backend, appid, value_name)
    backend.delete_value(appid, value_name)


def restore_latest_backup(
    conn: sqlite3.Connection,
    backend: RegistryBackend,
    appid: int,
    value_name: str,
) -> bool:
    _ensure_value_name(value_name)
    row = conn.execute(
        """
        SELECT value_hex FROM registry_backups
        WHERE appid=? AND value_name=? ORDER BY id DESC LIMIT 1
        """,
        (appid, value_name),
    ).fetchone()
    if row is None:
        return False
    if row["value_hex"] is None:
        backend.delete_value(appid, value_name)
    else:
        backend.write_value(appid, value_name, bytes.fromhex(row["value_hex"]))
    return True


def _backup(
    conn: sqlite3.Connection,
    backend: RegistryBackend,
    appid: int,
    value_name: str,
) -> None:
    old = backend.read_value(appid, value_name)
    conn.execute(
        """
        INSERT INTO registry_backups(appid, value_name, value_hex, backed_up_at)
        VALUES(?,?,?,?)
        """,
        (appid, value_name, old.hex() if old is not None else None, _now()),
    )


def _mark_written(conn: sqlite3.Connection, appid: int, value_name: str) -> None:
    table = "app_tickets" if value_name == "AppTicket" else "e_tickets"
    conn.execute(
        f"UPDATE {table} SET written_to_registry_at=? WHERE appid=?",
        (_now(), appid),
    )


def _validate(value_name: str, ticket_hex: str) -> None:
    _ensure_value_name(value_name)
    if len(ticket_hex) % 2 != 0 or not is_hex(ticket_hex):
        raise RegistryError("ticket_hex must be an even-length hex string")


def _ensure_value_name(value_name: str) -> None:
    if value_name not in VALID_VALUES:
        raise RegistryError(f"Unsupported registry value: {value_name}")


def _key(appid: int) -> str:
    return rf"Software\Valve\Steam\Apps\{appid}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
