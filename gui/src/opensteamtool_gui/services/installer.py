"""Install, uninstall, and inspect OpenSteamTool DLL files in Steam."""

from __future__ import annotations

import ctypes
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any

import psutil

DLL_FILES = ("OpenSteamTool.dll", "dwmapi.dll", "xinput1_4.dll")
MANIFEST_NAME = "manifest.json"
BACKUP_ROOT = Path("opensteamtool-gui") / "backup"


class InstallerError(RuntimeError):
    """Raised when an installer operation cannot be completed safely."""


class InstallState(Enum):
    NOT_INSTALLED = "not_installed"
    MATCHED = "matched"
    DIFFERENT = "different"
    PARTIAL = "partial"


@dataclass(frozen=True)
class FileStatus:
    name: str
    target_exists: bool
    hash_matches: bool
    expected_sha256: str | None
    actual_sha256: str | None


@dataclass(frozen=True)
class InstallStatus:
    state: InstallState
    version: str
    files: list[FileStatus]


@dataclass(frozen=True)
class InstallResult:
    installed: list[str]
    backup_dir: Path | None


@dataclass(frozen=True)
class BackupEntry:
    path: Path
    files: list[str]


def sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(source_dir: Path, manifest: dict[str, Any]) -> Path:
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_manifest(source_dir: Path) -> dict[str, Any]:
    path = source_dir / MANIFEST_NAME
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"version": "unknown", "files": _hash_existing_source_files(source_dir)}


def inspect_status(steam_path: Path, source_dir: Path) -> InstallStatus:
    _assert_source_ready(source_dir)
    manifest = read_manifest(source_dir)
    expected = _expected_hashes(source_dir, manifest)
    statuses = [_file_status(steam_path, name, expected[name]) for name in DLL_FILES]
    exists_count = sum(1 for item in statuses if item.target_exists)
    if exists_count == 0:
        state = InstallState.NOT_INSTALLED
    elif exists_count < len(DLL_FILES):
        state = InstallState.PARTIAL
    elif all(item.hash_matches for item in statuses):
        state = InstallState.MATCHED
    else:
        state = InstallState.DIFFERENT
    return InstallStatus(state, str(manifest.get("version", "unknown")), statuses)


def install(source_dir: Path, steam_path: Path, *, timestamp: str | None = None) -> InstallResult:
    _assert_valid_steam_dir(steam_path)
    _assert_source_ready(source_dir)
    backup_dir = _backup_existing(steam_path, timestamp or _timestamp())
    installed: list[str] = []
    for name in DLL_FILES:
        shutil.copy2(source_dir / name, steam_path / name)
        installed.append(name)
    _cleanup_old_backups(steam_path, keep=5)
    return InstallResult(installed, backup_dir)


def uninstall(
    steam_path: Path,
    *,
    remove_logs: bool = False,
    remove_managed_lua: bool = False,
    remove_config: bool = False,
) -> list[str]:
    removed: list[str] = []
    for name in DLL_FILES:
        target = steam_path / name
        if target.exists():
            target.unlink()
            removed.append(name)
    if remove_logs:
        shutil.rmtree(steam_path / "opensteamtool", ignore_errors=True)
    if remove_managed_lua:
        shutil.rmtree(steam_path / "config" / "lua" / "managed", ignore_errors=True)
    if remove_config:
        (steam_path / "opensteamtool.toml").unlink(missing_ok=True)
    return removed


def list_backups(steam_path: Path) -> list[BackupEntry]:
    root = steam_path / BACKUP_ROOT
    if not root.exists():
        return []
    backups = []
    for path in sorted(root.iterdir(), key=lambda item: item.name, reverse=True):
        if path.is_dir():
            files = [name for name in DLL_FILES if (path / name).exists()]
            backups.append(BackupEntry(path, files))
    return backups


def rollback(steam_path: Path, backup_dir: Path) -> list[str]:
    if not backup_dir.is_dir():
        raise InstallerError(f"Backup not found: {backup_dir}")
    restored: list[str] = []
    for name in DLL_FILES:
        source = backup_dir / name
        if source.exists():
            shutil.copy2(source, steam_path / name)
            restored.append(name)
    if not restored:
        raise InstallerError(f"Backup contains no DLL files: {backup_dir}")
    return restored


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_steam_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == "steam.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _file_status(steam_path: Path, name: str, expected_hash: str) -> FileStatus:
    target = steam_path / name
    if not target.exists():
        return FileStatus(name, False, False, expected_hash, None)
    actual = sha256_file(target)
    return FileStatus(name, True, actual == expected_hash, expected_hash, actual)


def _expected_hashes(source_dir: Path, manifest: dict[str, Any]) -> dict[str, str]:
    manifest_files = manifest.get("files") or {}
    result: dict[str, str] = {}
    for name in DLL_FILES:
        result[name] = str(manifest_files.get(name) or sha256_file(source_dir / name))
    return result


def _hash_existing_source_files(source_dir: Path) -> dict[str, str]:
    return {
        name: sha256_file(source_dir / name)
        for name in DLL_FILES
        if (source_dir / name).exists()
    }


def _assert_source_ready(source_dir: Path) -> None:
    missing = [name for name in DLL_FILES if not (source_dir / name).is_file()]
    if missing:
        raise InstallerError(f"DLL source is incomplete: {', '.join(missing)}")


def _assert_valid_steam_dir(steam_path: Path) -> None:
    if not (steam_path / "steam.exe").is_file():
        raise InstallerError(f"Steam path is invalid: {steam_path}")


def _backup_existing(steam_path: Path, timestamp: str) -> Path | None:
    existing = [name for name in DLL_FILES if (steam_path / name).exists()]
    if not existing:
        return None
    backup_dir = steam_path / BACKUP_ROOT / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in existing:
        shutil.copy2(steam_path / name, backup_dir / name)
    return backup_dir


def _cleanup_old_backups(steam_path: Path, keep: int) -> None:
    root = steam_path / BACKUP_ROOT
    if not root.exists():
        return
    backups = [path for path in sorted(root.iterdir(), key=lambda item: item.name) if path.is_dir()]
    for old in backups[:-keep]:
        shutil.rmtree(old, ignore_errors=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
