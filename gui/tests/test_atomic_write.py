"""Smoke tests for atomic_write."""

from __future__ import annotations

from pathlib import Path

from opensteamtool_gui.utils.atomic_write import atomic_write_text, cleanup_stale_tmp


def test_atomic_write_creates_file(tmp_path: Path):
    target = tmp_path / "sub" / "file.lua"
    atomic_write_text(target, "addappid(730)\n")
    assert target.read_text(encoding="utf-8") == "addappid(730)\n"


def test_atomic_write_overwrites(tmp_path: Path):
    target = tmp_path / "f.lua"
    atomic_write_text(target, "v1")
    atomic_write_text(target, "v2")
    assert target.read_text(encoding="utf-8") == "v2"


def test_atomic_write_no_lingering_tmp(tmp_path: Path):
    target = tmp_path / "f.lua"
    atomic_write_text(target, "x")
    assert not (tmp_path / "f.lua.tmp").exists()


def test_cleanup_stale_tmp(tmp_path: Path):
    (tmp_path / "a.lua.tmp").write_text("partial")
    (tmp_path / "b.lua").write_text("ok")
    (tmp_path / "c.lua.tmp").write_text("partial")
    removed = cleanup_stale_tmp(tmp_path)
    assert removed == 2
    assert not (tmp_path / "a.lua.tmp").exists()
    assert not (tmp_path / "c.lua.tmp").exists()
    assert (tmp_path / "b.lua").exists()
