"""Tests for AppTicket/ETicket registry operations."""

from __future__ import annotations

from pathlib import Path

from opensteamtool_gui.models.database import connect
from opensteamtool_gui.services import registry


def test_write_ticket_backs_up_old_value_and_writes_new_hex(tmp_path: Path) -> None:
    conn = connect(tmp_path / "lib.db")
    backend = registry.MemoryRegistryBackend()
    backend.write_value(730, "AppTicket", bytes.fromhex("0102"))

    registry.write_ticket(conn, backend, 730, "AppTicket", "deadbeef")

    assert backend.read_value(730, "AppTicket") == bytes.fromhex("deadbeef")
    row = conn.execute("SELECT value_hex FROM registry_backups").fetchone()
    assert row["value_hex"] == "0102"


def test_clear_and_restore_ticket_uses_latest_backup(tmp_path: Path) -> None:
    conn = connect(tmp_path / "lib.db")
    backend = registry.MemoryRegistryBackend()
    backend.write_value(730, "ETicket", bytes.fromhex("cafe"))
    registry.clear_ticket(conn, backend, 730, "ETicket")

    assert backend.read_value(730, "ETicket") is None

    restored = registry.restore_latest_backup(conn, backend, 730, "ETicket")

    assert restored is True
    assert backend.read_value(730, "ETicket") == bytes.fromhex("cafe")


def test_invalid_ticket_hex_is_rejected(tmp_path: Path) -> None:
    conn = connect(tmp_path / "lib.db")
    backend = registry.MemoryRegistryBackend()

    try:
        registry.write_ticket(conn, backend, 730, "AppTicket", "not-hex")
    except registry.RegistryError as exc:
        assert "hex" in str(exc)
    else:
        raise AssertionError("expected RegistryError")
