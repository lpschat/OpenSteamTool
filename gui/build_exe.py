"""Build OpenSteamTool GUI with PyInstaller in onedir mode."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "OpenSteamTool-GUI"


def build_pyinstaller_args() -> list[str]:
    resources = ROOT / "src" / "opensteamtool_gui" / "resources"
    entry = ROOT / "src" / "opensteamtool_gui" / "main.py"
    args = [
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        f"--name={APP_NAME}",
        f"--paths={(ROOT / 'src').as_posix()}",
        f"--add-data={resources.as_posix()}{os.pathsep}opensteamtool_gui/resources",
    ]
    icon = resources / "app_icon.ico"
    if icon.exists():
        args.append(f"--icon={icon.as_posix()}")
    args.append(entry.relative_to(ROOT).as_posix())
    return args


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parsed = parser.parse_args(argv)
    args = build_pyinstaller_args()
    if parsed.dry_run:
        print("\n".join(args))
        return 0
    import PyInstaller.__main__

    PyInstaller.__main__.run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
