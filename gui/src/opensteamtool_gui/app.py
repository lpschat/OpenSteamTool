"""Top-level App class — wires together window, DB, and Steam path."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from opensteamtool_gui.models.database import connect
from opensteamtool_gui.models.settings import Settings
from opensteamtool_gui.services import steam_path as steam_path_svc
from opensteamtool_gui.utils.atomic_write import cleanup_stale_tmp
from opensteamtool_gui.views.main_window import MainWindow
from opensteamtool_gui.views.theme import apply_theme


class App:
    def __init__(self, qt_app: QApplication) -> None:
        self.qt_app = qt_app
        self.conn = connect()
        self.settings = Settings(self.conn)
        apply_theme(qt_app, self.settings.get(Settings.KEY_THEME, "system"))
        self.steam_path = self._resolve_steam_path()
        if self.steam_path is not None:
            cleanup_stale_tmp(steam_path_svc.lua_managed_dir(self.steam_path))
        self.window = MainWindow(self.conn, self.steam_path)

    def _resolve_steam_path(self):
        saved = self.settings.get(Settings.KEY_STEAM_PATH)
        if saved:
            from pathlib import Path
            p = Path(saved)
            if steam_path_svc.is_valid_steam_dir(p):
                return p
        detected = steam_path_svc.detect()
        if detected is not None:
            self.settings.set(Settings.KEY_STEAM_PATH, str(detected))
            return detected
        return self._prompt_steam_path()

    def _prompt_steam_path(self):
        from pathlib import Path
        QMessageBox.information(
            None,
            "选择 Steam 目录",
            "未自动检测到 Steam 安装目录，请手动选择包含 steam.exe 的目录。",
        )
        chosen = QFileDialog.getExistingDirectory(None, "选择 Steam 目录")
        if not chosen:
            return None
        p = Path(chosen)
        if steam_path_svc.is_valid_steam_dir(p):
            self.settings.set(Settings.KEY_STEAM_PATH, str(p))
            return p
        QMessageBox.warning(
            None, "目录无效", "所选目录中未找到 steam.exe，将以未配置状态启动。"
        )
        return None

    def show(self) -> None:
        self.window.show()
