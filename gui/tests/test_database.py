"""Smoke tests for SQLite schema + migration."""

from __future__ import annotations

from pathlib import Path

from opensteamtool_gui.models.database import connect, migrate
from opensteamtool_gui.models.game import Depot, Game, GameRepository
from opensteamtool_gui.models.settings import Settings


def test_migrate_creates_tables(tmp_path: Path):
    conn = connect(tmp_path / "lib.db")
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {r["name"] for r in rows}
    expected = {
        "games", "depots", "access_tokens", "app_tickets",
        "e_tickets", "stat_overrides", "registry_backups", "settings",
    }
    assert expected <= names


def test_migrate_idempotent(tmp_path: Path):
    conn = connect(tmp_path / "lib.db")
    before = conn.execute("PRAGMA user_version").fetchone()[0]
    migrate(conn)
    after = conn.execute("PRAGMA user_version").fetchone()[0]
    assert before == after


def test_settings_get_set(tmp_path: Path):
    conn = connect(tmp_path / "lib.db")
    s = Settings(conn)
    assert s.get(Settings.KEY_STEAM_PATH) is None
    s.set(Settings.KEY_STEAM_PATH, "C:/Steam")
    assert s.get(Settings.KEY_STEAM_PATH) == "C:/Steam"
    s.set(Settings.KEY_STEAM_PATH, "D:/Steam")
    assert s.get(Settings.KEY_STEAM_PATH) == "D:/Steam"


def test_game_repository_roundtrip(tmp_path: Path):
    conn = connect(tmp_path / "lib.db")
    repo = GameRepository(conn)
    game = Game(
        appid=730,
        name="CS2",
        depots=[
            Depot(depot_id=731, owner_appid=730, decryption_key="a" * 64,
                  manifest_gid="123"),
        ],
        access_token="42",
        stat_steam_id="76561198000000000",
    )
    repo.upsert_game(game)
    loaded = repo.get(730)
    assert loaded is not None
    assert loaded.name == "CS2"
    assert len(loaded.depots) == 1
    assert loaded.depots[0].decryption_key == "a" * 64
    assert loaded.access_token == "42"
    assert loaded.stat_steam_id == "76561198000000000"


def test_game_repository_delete_cascades(tmp_path: Path):
    conn = connect(tmp_path / "lib.db")
    repo = GameRepository(conn)
    repo.upsert_game(Game(
        appid=730, name="CS2",
        depots=[Depot(depot_id=731, owner_appid=730)],
        access_token="42",
    ))
    repo.delete_game(730)
    assert repo.get(730) is None
    assert conn.execute("SELECT COUNT(*) FROM depots").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM access_tokens").fetchone()[0] == 0


def test_list_main_games_excludes_dlcs(tmp_path: Path):
    conn = connect(tmp_path / "lib.db")
    repo = GameRepository(conn)
    repo.upsert_game(Game(appid=730, name="CS2"))
    repo.upsert_game(Game(appid=731, name="DLC", parent_appid=730))
    main = repo.list_main_games()
    assert [g.appid for g in main] == [730]
    dlcs = repo.list_dlcs(730)
    assert [g.appid for g in dlcs] == [731]


def test_set_enabled_many_updates_games(tmp_path: Path):
    conn = connect(tmp_path / "lib.db")
    repo = GameRepository(conn)
    repo.upsert_game(Game(appid=730, name="CS2"))
    repo.upsert_game(Game(appid=440, name="TF2"))

    repo.set_enabled_many([730, 440], False)

    assert repo.get(730).enabled is False  # type: ignore[union-attr]
    assert repo.get(440).enabled is False  # type: ignore[union-attr]
