"""Read and discover OpenSteamTool log files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LOG_NAMES = {
    "main.log": "主程序",
    "ipc.log": "IPC 调度",
    "netpacket.log": "网络包",
    "manifest.log": "Manifest 下载",
    "decryptionkey.log": "解密密钥",
    "keyvalue.log": "KeyValues 补丁",
    "misc.log": "杂项",
    "winhttp.log": "HTTP 请求",
    "achievement.log": "成就",
    "pics.log": "PICS Token",
    "package.log": "包加载",
    "onlinefix.log": "Online Fix",
}


@dataclass(frozen=True)
class LogFile:
    path: Path
    filename: str
    display_name: str


@dataclass(frozen=True)
class NewLines:
    lines: list[str]
    next_offset: int


def discover_logs(steam_path: Path) -> list[LogFile]:
    log_dir = steam_path / "opensteamtool"
    if not log_dir.exists():
        return []
    files = {path.name: path for path in log_dir.glob("*.log") if path.is_file()}
    ordered = [name for name in LOG_NAMES if name in files]
    ordered.extend(sorted(name for name in files if name not in LOG_NAMES))
    return [LogFile(files[name], name, LOG_NAMES.get(name, name)) for name in ordered]


def tail_lines(path: Path, *, max_lines: int = 10000, max_bytes: int = 1024 * 1024) -> list[str]:
    if not path.exists():
        return []
    size = path.stat().st_size
    start = max(0, size - max_bytes)
    with path.open("rb") as fh:
        fh.seek(start)
        data = fh.read()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if start > 0 and lines:
        lines = lines[1:]
    return lines[-max_lines:]


def read_new_lines(path: Path, offset: int, *, max_lines: int = 500) -> NewLines:
    if not path.exists():
        return NewLines([], 0)
    size = path.stat().st_size
    start = offset if 0 <= offset <= size else 0
    with path.open("rb") as fh:
        fh.seek(start)
        data = fh.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    return NewLines(lines[:max_lines], size)
