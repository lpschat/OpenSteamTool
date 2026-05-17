"""Installer page for OpenSteamTool DLL deployment."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from opensteamtool_gui.services import installer, upstream_dll_release
from opensteamtool_gui.utils.paths import cache_dir


class InstallerView(QWidget):
    def __init__(self, steam_path: Path | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.steam_path = steam_path
        self._latest_release: upstream_dll_release.ReleaseInfo | None = None
        self._local_source: Path | None = None

        self.status_label = QLabel()
        self.source_combo = QComboBox()
        self.source_label = QLabel()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["文件", "目标", "哈希", "期望"])
        self.table.horizontalHeader().setStretchLastSection(True)

        self._build_layout()
        self._load_sources()
        self.refresh_status()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addLayout(self._source_row())
        root.addWidget(self.status_label)
        root.addWidget(self.table, 1)
        root.addLayout(self._action_row())

    def _source_row(self) -> QHBoxLayout:
        self.source_combo.currentIndexChanged.connect(self.refresh_status)
        choose_local = QPushButton("选择本地 DLL 目录")
        choose_local.clicked.connect(self._choose_local_source)
        check = QPushButton("检查上游")
        check.clicked.connect(self._check_upstream)
        download = QPushButton("下载上游")
        download.clicked.connect(self._download_upstream)
        row = QHBoxLayout()
        row.addWidget(QLabel("DLL 来源"))
        row.addWidget(self.source_combo)
        row.addWidget(choose_local)
        row.addWidget(check)
        row.addWidget(download)
        row.addWidget(self.source_label, 1)
        return row

    def _action_row(self) -> QHBoxLayout:
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh_status)
        install_btn = QPushButton("安装/覆盖")
        install_btn.clicked.connect(self._install)
        uninstall_btn = QPushButton("卸载")
        uninstall_btn.clicked.connect(self._uninstall)
        rollback_btn = QPushButton("回滚")
        rollback_btn.clicked.connect(self._rollback)
        row = QHBoxLayout()
        for button in (refresh, install_btn, uninstall_btn, rollback_btn):
            row.addWidget(button)
        row.addStretch(1)
        return row

    def _load_sources(self) -> None:
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItem("内置 DLL", self._builtin_source())
        active = self._active_upstream_source()
        if active is not None:
            self.source_combo.addItem(f"在线更新 {active.name}", active)
        if self._local_source is not None:
            self.source_combo.addItem("本地文件", self._local_source)
        self.source_combo.blockSignals(False)

    def refresh_status(self) -> None:
        source = self._selected_source()
        if self.steam_path is None:
            self._set_error("Steam 路径未配置")
            return
        try:
            status = installer.inspect_status(self.steam_path, source)
        except installer.InstallerError as exc:
            self._set_error(str(exc))
            return
        label = f"状态：{_state_label(status.state)} · 来源版本：{status.version}"
        self.status_label.setText(label)
        self.source_label.setText(str(source))
        self._render_status(status)

    def _render_status(self, status: installer.InstallStatus) -> None:
        self.table.setRowCount(len(status.files))
        for row, item in enumerate(status.files):
            self.table.setItem(row, 0, QTableWidgetItem(item.name))
            target = "存在" if item.target_exists else "缺失"
            self.table.setItem(row, 1, QTableWidgetItem(target))
            match = "匹配" if item.hash_matches else "不匹配"
            self.table.setItem(row, 2, QTableWidgetItem(match))
            expected = (item.expected_sha256 or "")[:12]
            self.table.setItem(row, 3, QTableWidgetItem(expected))

    def _install(self) -> None:
        if not self._can_touch_steam():
            return
        try:
            result = installer.install(self._selected_source(), self.steam_path)
        except installer.InstallerError as exc:
            QMessageBox.warning(self, "安装失败", str(exc))
            return
        QMessageBox.information(self, "安装完成", "已安装：" + ", ".join(result.installed))
        self.refresh_status()

    def _uninstall(self) -> None:
        if self.steam_path is None or not self._can_touch_steam():
            return
        options = _UninstallOptionsDialog(self)
        if options.exec() != QDialog.DialogCode.Accepted:
            return
        removed = installer.uninstall(self.steam_path, **options.values())
        QMessageBox.information(self, "卸载完成", "已删除：" + ", ".join(removed or ["无"]))
        self.refresh_status()

    def _rollback(self) -> None:
        if self.steam_path is None or not self._can_touch_steam():
            return
        backups = installer.list_backups(self.steam_path)
        labels = [entry.path.name for entry in backups]
        if not labels:
            QMessageBox.information(self, "无备份", "未找到可回滚的备份")
            return
        label, ok = QInputDialog.getItem(self, "选择备份", "备份时间", labels, 0, False)
        if ok:
            entry = backups[labels.index(label)]
            restored = installer.rollback(self.steam_path, entry.path)
            QMessageBox.information(self, "回滚完成", "已还原：" + ", ".join(restored))
            self.refresh_status()

    def _check_upstream(self) -> None:
        try:
            self._latest_release = upstream_dll_release.fetch_latest_release()
        except Exception as exc:
            QMessageBox.warning(self, "检查失败", str(exc))
            return
        info = self._latest_release
        self.source_label.setText(f"上游最新版：{info.tag}")

    def _download_upstream(self) -> None:
        try:
            info = self._latest_release or upstream_dll_release.fetch_latest_release()
            zip_path = cache_dir() / "upstream_dlls" / f"{info.tag}.zip"
            upstream_dll_release.download_asset(info.asset_url, zip_path)
            staged = upstream_dll_release.stage_release_zip(zip_path, cache_dir(), info.tag)
            upstream_dll_release.write_active_source(cache_dir(), staged)
            upstream_dll_release.cleanup_staged_releases(cache_dir())
        except Exception as exc:
            QMessageBox.warning(self, "下载失败", str(exc))
            return
        self._load_sources()
        self.source_combo.setCurrentText(f"在线更新 {info.tag}")
        self.refresh_status()

    def _choose_local_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择包含三个 DLL 的目录")
        if not path:
            return
        self._local_source = Path(path)
        self._load_sources()
        self.source_combo.setCurrentText("本地文件")
        self.refresh_status()

    def _selected_source(self) -> Path:
        return Path(self.source_combo.currentData())

    def _builtin_source(self) -> Path:
        return Path(__file__).resolve().parents[1] / "resources" / "dlls"

    def _active_upstream_source(self) -> Path | None:
        path = cache_dir() / "active_dll_source.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        source = Path(str(data.get("path") or ""))
        return source if source.exists() else None

    def _can_touch_steam(self) -> bool:
        if self.steam_path is None:
            QMessageBox.warning(self, "Steam 路径未配置", "请先配置 Steam 路径")
            return False
        if installer.is_steam_running():
            QMessageBox.warning(self, "Steam 正在运行", "请先关闭 Steam 再安装或卸载 DLL")
            return False
        if not installer.is_admin():
            QMessageBox.warning(self, "需要管理员权限", "请以管理员身份运行 GUI 后重试")
            return False
        return True

    def _set_error(self, message: str) -> None:
        self.status_label.setText(f"状态：{message}")
        self.source_label.setText(str(self._selected_source()))
        self.table.setRowCount(0)


class _UninstallOptionsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("卸载选项")
        self.logs = QCheckBox("删除日志目录 opensteamtool/")
        self.managed = QCheckBox("删除 GUI 生成目录 config/lua/managed/")
        self.config = QCheckBox("删除 opensteamtool.toml")
        form = QFormLayout()
        form.addRow(self.logs)
        form.addRow(self.managed)
        form.addRow(self.config)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, bool]:
        return {
            "remove_logs": self.logs.isChecked(),
            "remove_managed_lua": self.managed.isChecked(),
            "remove_config": self.config.isChecked(),
        }


def _state_label(state: installer.InstallState) -> str:
    labels = {
        installer.InstallState.NOT_INSTALLED: "未安装",
        installer.InstallState.MATCHED: "已安装且版本匹配",
        installer.InstallState.DIFFERENT: "已安装但版本不同",
        installer.InstallState.PARTIAL: "部分安装",
    }
    return labels[state]
