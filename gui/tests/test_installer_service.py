"""Tests for DLL installer service behavior."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from opensteamtool_gui.services import installer


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _source(root: Path, seed: bytes = b"source") -> Path:
    source = root / "source"
    manifest = {"version": "1.2.3", "files": {}}
    for name in installer.DLL_FILES:
        data = seed + name.encode("ascii")
        _write(source / name, data)
        manifest["files"][name] = sha256(data).hexdigest()
    installer.write_manifest(source, manifest)
    return source


def _steam(root: Path) -> Path:
    steam = root / "Steam"
    _write(steam / "steam.exe", b"steam")
    return steam


def test_status_reports_not_installed_when_targets_are_missing(tmp_path: Path) -> None:
    source = _source(tmp_path)
    steam = _steam(tmp_path)

    status = installer.inspect_status(steam, source)

    assert status.state is installer.InstallState.NOT_INSTALLED
    assert {f.name for f in status.files if not f.target_exists} == set(installer.DLL_FILES)


def test_install_backs_up_existing_files_and_matches_source(tmp_path: Path) -> None:
    source = _source(tmp_path)
    steam = _steam(tmp_path)
    _write(steam / "OpenSteamTool.dll", b"old")

    result = installer.install(source, steam, timestamp="20260102T030405Z")
    status = installer.inspect_status(steam, source)

    assert result.installed == list(installer.DLL_FILES)
    assert status.state is installer.InstallState.MATCHED
    backup = steam / "opensteamtool-gui" / "backup" / "20260102T030405Z"
    assert (backup / "OpenSteamTool.dll").read_bytes() == b"old"


def test_uninstall_removes_only_loader_files_by_default(tmp_path: Path) -> None:
    source = _source(tmp_path)
    steam = _steam(tmp_path)
    installer.install(source, steam, timestamp="20260102T030405Z")
    _write(steam / "opensteamtool" / "main.log", b"log")
    _write(steam / "config" / "lua" / "managed" / "app_1.lua", b"lua")

    removed = installer.uninstall(steam)

    assert removed == list(installer.DLL_FILES)
    assert not any((steam / name).exists() for name in installer.DLL_FILES)
    assert (steam / "opensteamtool" / "main.log").exists()
    assert (steam / "config" / "lua" / "managed" / "app_1.lua").exists()


def test_rollback_restores_selected_backup(tmp_path: Path) -> None:
    source = _source(tmp_path)
    steam = _steam(tmp_path)
    _write(steam / "OpenSteamTool.dll", b"old")
    installer.install(source, steam, timestamp="20260102T030405Z")
    backup = installer.list_backups(steam)[0]

    installer.rollback(steam, backup.path)

    assert (steam / "OpenSteamTool.dll").read_bytes() == b"old"


def test_missing_source_file_raises_clear_error(tmp_path: Path) -> None:
    source = _source(tmp_path)
    (source / "dwmapi.dll").unlink()
    steam = _steam(tmp_path)

    with pytest.raises(installer.InstallerError, match="dwmapi.dll"):
        installer.install(source, steam, timestamp="20260102T030405Z")
