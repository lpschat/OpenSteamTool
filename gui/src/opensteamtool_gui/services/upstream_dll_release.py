"""GitHub Release helpers for staging upstream OpenSteamTool DLL zips."""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx

from opensteamtool_gui.services import installer

REPO = "OpenSteam001/OpenSteamTool"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"


class ReleaseError(RuntimeError):
    """Raised when upstream release metadata or artifacts are invalid."""


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    version: str
    asset_name: str
    asset_url: str
    html_url: str


@dataclass(frozen=True)
class StagedRelease:
    tag: str
    version: str
    path: Path
    manifest_path: Path


def expected_asset_name(tag: str) -> str:
    return f"OpenSteamTool-{tag}-Release.zip"


def parse_latest_release(payload: dict[str, Any]) -> ReleaseInfo:
    tag = str(payload.get("tag_name") or "")
    if not tag:
        raise ReleaseError("Release payload is missing tag_name")
    expected = expected_asset_name(tag)
    for asset in payload.get("assets") or []:
        if asset.get("name") == expected and asset.get("browser_download_url"):
            return ReleaseInfo(
                tag=tag,
                version=tag.removeprefix("v"),
                asset_name=expected,
                asset_url=str(asset["browser_download_url"]),
                html_url=str(payload.get("html_url") or ""),
            )
    raise ReleaseError(f"Release asset not found: {expected}")


def fetch_latest_release(token: str | None = None) -> ReleaseInfo:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        response = client.get(LATEST_RELEASE_API, headers=headers)
        response.raise_for_status()
        return parse_latest_release(response.json())


def download_asset(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as response:
        response.raise_for_status()
        with temp.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)
    temp.replace(target)
    return target


def stage_release_zip(zip_path: Path, cache_dir: Path, tag: str) -> StagedRelease:
    version = tag.removeprefix("v")
    stage_dir = cache_dir / "upstream_dlls" / tag
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = {Path(name).name: name for name in zf.namelist()}
        _require_members(members)
        for name in installer.DLL_FILES:
            with zf.open(members[name]) as source, (stage_dir / name).open("wb") as target:
                shutil.copyfileobj(source, target)
    manifest_path = _write_staged_manifest(stage_dir, version)
    return StagedRelease(tag, version, stage_dir, manifest_path)


def write_active_source(cache_dir: Path, staged: StagedRelease) -> Path:
    path = cache_dir / "active_dll_source.json"
    payload = {"type": "upstream", "tag": staged.tag, "path": str(staged.path)}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def cleanup_staged_releases(cache_dir: Path, keep: int = 3) -> None:
    root = cache_dir / "upstream_dlls"
    if not root.exists():
        return
    releases = [
        path for path in sorted(root.iterdir(), key=lambda item: item.name) if path.is_dir()
    ]
    for old in releases[:-keep]:
        shutil.rmtree(old, ignore_errors=True)


def _require_members(members: dict[str, str]) -> None:
    missing = [name for name in installer.DLL_FILES if name not in members]
    if missing:
        raise ReleaseError(f"Release zip is missing: {', '.join(missing)}")


def _write_staged_manifest(stage_dir: Path, version: str) -> Path:
    files = {}
    for name in installer.DLL_FILES:
        files[name] = sha256((stage_dir / name).read_bytes()).hexdigest()
    manifest = {"version": version, "files": files}
    return installer.write_manifest(stage_dir, manifest)
