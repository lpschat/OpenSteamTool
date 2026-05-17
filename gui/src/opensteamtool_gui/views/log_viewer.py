"""OpenSteamTool log viewer with tailing and light level filtering."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from opensteamtool_gui.services import log_reader

LEVELS = {"trace": 0, "debug": 1, "info": 2, "warn": 3, "error": 4}


class LogHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
        self.formats = {
            "trace": _format("#8A8A93"),
            "debug": _format("#9BA0AA"),
            "warn": _format("#D89B2D"),
            "error": _format("#E05268"),
        }

    def highlightBlock(self, text: str) -> None:
        level = _line_level(text)
        fmt = self.formats.get(level or "")
        if fmt is not None:
            self.setFormat(0, len(text), fmt)


class LogViewer(QWidget):
    def __init__(self, steam_path: Path | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.steam_path = steam_path
        self._logs: list[log_reader.LogFile] = []
        self._current: log_reader.LogFile | None = None
        self._raw_lines: list[str] = []
        self._offset = 0

        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._file_changed)
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._load_current_log)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索")
        self.search_edit.textChanged.connect(self._render)
        self.level_combo = QComboBox()
        self.level_combo.addItems(["全部", "Info+", "Warn+", "Error only"])
        self.level_combo.currentIndexChanged.connect(self._render)
        self.follow_btn = QToolButton()
        self.follow_btn.setText("锁定到底部")
        self.follow_btn.setCheckable(True)
        self.follow_btn.setChecked(True)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Consolas", 10))
        self.highlighter = LogHighlighter(self.text.document())

        self._build_layout()
        QShortcut(QKeySequence.StandardKey.Find, self, activated=self.search_edit.setFocus)
        self.refresh_logs()

    def _build_layout(self) -> None:
        left = QWidget()
        left_layout = QVBoxLayout(left)
        refresh = QPushButton("刷新日志")
        refresh.clicked.connect(self.refresh_logs)
        left_layout.addWidget(refresh)
        left_layout.addWidget(self.list_widget)

        top = QHBoxLayout()
        top.addWidget(QLabel("级别"))
        top.addWidget(self.level_combo)
        top.addWidget(self.search_edit, 1)
        top.addWidget(self.follow_btn)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addLayout(top)
        right_layout.addWidget(self.text, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(splitter)

    def refresh_logs(self) -> None:
        self.list_widget.clear()
        self._logs = [] if self.steam_path is None else log_reader.discover_logs(self.steam_path)
        if not self._logs:
            self.text.setPlainText(
                "未检测到日志目录。请确认 OpenSteamTool DLL 已安装且使用 Debug 构建。"
            )
            return
        for item in self._logs:
            QListWidgetItem(f"{item.display_name} ({item.filename})", self.list_widget)
        self.list_widget.setCurrentRow(0)

    def _load_current_log(self, row: int) -> None:
        if not (0 <= row < len(self._logs)):
            return
        self._current = self._logs[row]
        self._raw_lines = log_reader.tail_lines(self._current.path)
        self._offset = self._current.path.stat().st_size if self._current.path.exists() else 0
        self._watch_only(self._current.path)
        self._render()

    def _file_changed(self, path: str) -> None:
        if self._current is None or Path(path) != self._current.path:
            return
        result = log_reader.read_new_lines(self._current.path, self._offset)
        self._offset = result.next_offset
        self._raw_lines.extend(result.lines)
        self._raw_lines = self._raw_lines[-10000:]
        self._watch_only(self._current.path)
        self._render()

    def _render(self) -> None:
        query = self.search_edit.text().strip().lower()
        lines = [line for line in self._raw_lines if self._passes_filter(line, query)]
        self.text.setPlainText("\n".join(lines))
        if self.follow_btn.isChecked():
            self.text.moveCursor(self.text.textCursor().MoveOperation.End)

    def _passes_filter(self, line: str, query: str) -> bool:
        if query and query not in line.lower():
            return False
        selected = self.level_combo.currentText()
        if selected == "全部":
            return True
        rank = LEVELS.get(_line_level(line) or "info", LEVELS["info"])
        if selected == "Info+":
            return rank >= LEVELS["info"]
        if selected == "Warn+":
            return rank >= LEVELS["warn"]
        return rank >= LEVELS["error"]

    def _watch_only(self, path: Path) -> None:
        for watched in self.watcher.files():
            self.watcher.removePath(watched)
        if path.exists():
            self.watcher.addPath(str(path))


def _line_level(text: str) -> str | None:
    stripped = text.lstrip().lower()
    for level in LEVELS:
        if stripped.startswith(f"[{level}]"):
            return level
    return None


def _format(color: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    return fmt
