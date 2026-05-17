"""Tests for upstream DLL release parsing and staging."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from opensteamtool_gui.services import installer, upstream_dll_release


def _zip_release(path: Path, missing: str | None = None) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name in installer.DLL_FILES:
            if name == missing:
                continue
            zf.writestr(name, f"payload:{name}".encode("ascii"))


def test_parse_latest_release_picks_expected_release_asset() -> None:
    payload = {
        "tag_name": "v1.4.3",
        "html_url": "https://github.com/OpenSteam001/OpenSteamTool/releases/tag/v1.4.3",
        "assets": [
            {"name": "notes.txt", "browser_download_url": "https://example.invalid/notes.txt"},
            {
                "name": "OpenSteamTool-v1.4.3-Release.zip",
                "browser_download_url": "https://example.invalid/OpenSteamTool.zip",
            },
        ],
    }

    info = upstream_dll_release.parse_latest_release(payload)

    assert info.tag == "v1.4.3"
    assert info.version == "1.4.3"
    assert info.asset_url == "https://example.invalid/OpenSteamTool.zip"


def test_stage_release_zip_extracts_dlls_and_writes_manifest(tmp_path: Path) -> None:
    zip_path = tmp_path / "release.zip"
    _zip_release(zip_path)

    staged = upstream_dll_release.stage_release_zip(zip_path, tmp_path / "cache", "v1.4.3")
    manifest = installer.read_manifest(staged.path)

    assert staged.version == "1.4.3"
    assert set(manifest["files"]) == set(installer.DLL_FILES)
    assert all((staged.path / name).exists() for name in installer.DLL_FILES)


def test_stage_release_zip_rejects_missing_dll(tmp_path: Path) -> None:
    zip_path = tmp_path / "release.zip"
    _zip_release(zip_path, missing="xinput1_4.dll")

    with pytest.raises(upstream_dll_release.ReleaseError, match="xinput1_4.dll"):
        upstream_dll_release.stage_release_zip(zip_path, tmp_path / "cache", "v1.4.3")
