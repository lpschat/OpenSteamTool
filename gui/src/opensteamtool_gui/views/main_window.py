"""Main window — three-pane skeleton with left navigation and stacked content."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from opensteamtool_gui.views.installer_view import InstallerView
from opensteamtool_gui.views.library_view import LibraryView
from opensteamtool_gui.views.log_viewer import LogViewer
from opensteamtool_gui.views.settings_view import SettingsView
from opensteamtool_gui.views.theme import apply_theme


class MainWindow(QMainWindow):
    NAV_ITEMS = ["库", "安装器", "日志", "设置"]

    def __init__(
        self,
        conn: sqlite3.Connection,
        steam_path: Path | None,
    ) -> None:
        super().__init__()
        self.conn = conn
        self.steam_path = steam_path
        self.setWindowTitle("OpenSteamTool GUI")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav = self._build_nav()
        layout.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.library_view = LibraryView(conn, steam_path)
        self.stack.addWidget(self.library_view)
        self.installer_view = InstallerView(steam_path)
        self.stack.addWidget(self.installer_view)
        self.log_viewer = LogViewer(steam_path)
        self.stack.addWidget(self.log_viewer)
        self.settings_view = SettingsView(conn, steam_path)
        self.settings_view.theme_changed.connect(self._apply_theme)
        self.stack.addWidget(self.settings_view)
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self.setStatusBar(self._build_status_bar())

    def _build_nav(self) -> QListWidget:
        nav = QListWidget()
        nav.setFixedWidth(160)
        nav.setIconSize(QSize(20, 20))
        nav.setSpacing(2)
        for label in self.NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item.setSizeHint(QSize(0, 36))
            nav.addItem(item)
        return nav

    def _placeholder(self, text: str) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return w

    def _apply_theme(self, value: str) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, value)

    def _build_status_bar(self) -> QStatusBar:
        bar = QStatusBar()
        steam_text = (
            f"Steam: {self.steam_path}" if self.steam_path else "Steam: 未配置"
        )
        bar.addWidget(QLabel(steam_text))
        bar.addPermanentWidget(QLabel("DLL: 未检测"))
        bar.addPermanentWidget(QLabel("库: 0"))
        return bar
