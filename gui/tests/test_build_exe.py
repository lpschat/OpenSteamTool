"""Tests for PyInstaller build script configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_build_exe():
    path = Path(__file__).resolve().parent.parent / "build_exe.py"
    spec = importlib.util.spec_from_file_location("build_exe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pyinstaller_args_use_onedir_and_gui_entry() -> None:
    build_exe = _load_build_exe()

    args = build_exe.build_pyinstaller_args()

    assert "--onedir" in args
    assert "--name=OpenSteamTool-GUI" in args
    assert "src/opensteamtool_gui/main.py" in args
    assert any("resources" in arg for arg in args)
