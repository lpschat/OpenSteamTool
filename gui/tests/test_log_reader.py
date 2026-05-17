"""Tests for OpenSteamTool log discovery and tail reading."""

from __future__ import annotations

from pathlib import Path

from opensteamtool_gui.services import log_reader


def test_discover_logs_uses_friendly_names_for_known_files(tmp_path: Path) -> None:
    steam = tmp_path / "Steam"
    log_dir = steam / "opensteamtool"
    log_dir.mkdir(parents=True)
    (log_dir / "main.log").write_text("[info] hello\n", encoding="utf-8")
    (log_dir / "future.log").write_text("[warn] later\n", encoding="utf-8")

    logs = log_reader.discover_logs(steam)

    assert [(log.filename, log.display_name) for log in logs] == [
        ("main.log", "主程序"),
        ("future.log", "future.log"),
    ]


def test_tail_lines_reads_only_recent_lines(tmp_path: Path) -> None:
    path = tmp_path / "main.log"
    path.write_text("".join(f"line {i}\n" for i in range(20)), encoding="utf-8")

    lines = log_reader.tail_lines(path, max_lines=3, max_bytes=64)

    assert lines == ["line 17", "line 18", "line 19"]


def test_read_new_lines_limits_appended_lines(tmp_path: Path) -> None:
    path = tmp_path / "main.log"
    path.write_text("a\n", encoding="utf-8")
    offset = path.stat().st_size
    with path.open("ab") as fh:
        fh.write(b"b\nc\nd\n")

    result = log_reader.read_new_lines(path, offset, max_lines=2)

    assert result.lines == ["b", "c"]
    assert result.next_offset == path.stat().st_size
