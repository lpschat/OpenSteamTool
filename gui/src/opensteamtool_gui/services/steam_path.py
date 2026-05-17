"""Steam install path detection.

Priority (per doc 5):
  1. HKCU\\Software\\Valve\\Steam → SteamPath
  2. HKLM\\Software\\WOW6432Node\\Valve\\Steam\\InstallPath
  3. C:\\Program Files (x86)\\Steam
  4. User-supplied (must contain steam.exe)
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_PATH = Path(r"C:\Program Files (x86)\Steam")


def _read_registry(hive: str, subkey: str, value_name: str) -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None
    hive_const = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
    }[hive]
    access = winreg.KEY_READ
    if hive == "HKLM" and "WOW6432Node" in subkey:
        access |= winreg.KEY_WOW64_32KEY
    try:
        with winreg.OpenKey(hive_const, subkey, 0, access) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value) if value else None
    except OSError:
        return None


def is_valid_steam_dir(path: Path | None) -> bool:
    if path is None:
        return False
    return path.is_dir() and (path / "steam.exe").is_file()


def detect() -> Path | None:
    """Try registry → default; return first valid path or None."""
    candidates: list[Path] = []
    hkcu = _read_registry("HKCU", r"Software\Valve\Steam", "SteamPath")
    if hkcu:
        candidates.append(Path(hkcu))
    hklm = _read_registry("HKLM", r"Software\WOW6432Node\Valve\Steam", "InstallPath")
    if hklm:
        candidates.append(Path(hklm))
    candidates.append(DEFAULT_PATH)
    for c in candidates:
        if is_valid_steam_dir(c):
            return c
    return None


def lua_managed_dir(steam_path: Path) -> Path:
    """<Steam>/config/lua/managed/"""
    return steam_path / "config" / "lua" / "managed"


def lua_dir(steam_path: Path) -> Path:
    """<Steam>/config/lua/"""
    return steam_path / "config" / "lua"


def opensteamtool_log_dir(steam_path: Path) -> Path:
    """<Steam>/opensteamtool/"""
    return steam_path / "opensteamtool"
