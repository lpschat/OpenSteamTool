"""Settings page for Steam path, theme, language, and cache/data actions."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from opensteamtool_gui.models.settings import Settings
from opensteamtool_gui.services import steam_path as steam_path_svc
from opensteamtool_gui.utils.paths import cache_dir, data_dir


class SettingsView(QWidget):
    theme_changed = Signal(str)

    def __init__(
        self,
        conn: sqlite3.Connection,
        steam_path: Path | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = Settings(conn)
        self.steam_path = steam_path
        self.path_edit = QLineEdit(str(steam_path or ""))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["system", "light", "dark"])
        self.language_combo = QComboBox()
        self.language_combo.addItems(["system", "zh_CN", "en_US"])
        self.cache_label = QLabel()
        self._build_layout()
        self._load()
        self._refresh_cache_size()

    def _build_layout(self) -> None:
        form = QFormLayout()
        browse = QPushButton("浏览")
        browse.clicked.connect(self._browse_steam)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        form.addRow("Steam 路径", path_row)
        form.addRow("主题", self.theme_combo)
        form.addRow("语言", self.language_combo)
        form.addRow("缓存大小", self.cache_label)
        save = QPushButton("保存设置")
        save.clicked.connect(self._save)
        clear_cache = QPushButton("清空缓存")
        clear_cache.clicked.connect(self._clear_cache)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.addLayout(form)
        root.addWidget(save)
        root.addWidget(clear_cache)
        root.addWidget(QLabel(f"数据目录：{data_dir()}"))
        root.addStretch(1)

    def _load(self) -> None:
        self.theme_combo.setCurrentText(self.settings.get(Settings.KEY_THEME, "system"))
        self.language_combo.setCurrentText(self.settings.get(Settings.KEY_LANGUAGE, "system"))

    def _save(self) -> None:
        raw_path = self.path_edit.text().strip()
        path = Path(raw_path) if raw_path else None
        if path is not None and not steam_path_svc.is_valid_steam_dir(path):
            QMessageBox.warning(self, "Steam 路径无效", "目录中必须包含 steam.exe")
            return
        theme = self.theme_combo.currentText()
        if path is not None:
            self.settings.set(Settings.KEY_STEAM_PATH, str(path))
        self.settings.set(Settings.KEY_THEME, theme)
        self.settings.set(Settings.KEY_LANGUAGE, self.language_combo.currentText())
        self.theme_changed.emit(theme)
        QMessageBox.information(self, "已保存", "设置已保存")

    def _browse_steam(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 Steam 目录")
        if path:
            self.path_edit.setText(path)

    def _clear_cache(self) -> None:
        root = cache_dir()
        for path in root.rglob("*"):
            if path.is_file():
                path.unlink()
        self._refresh_cache_size()

    def _refresh_cache_size(self) -> None:
        size = sum(path.stat().st_size for path in cache_dir().rglob("*") if path.is_file())
        self.cache_label.setText(f"{size / 1024:.1f} KB")
