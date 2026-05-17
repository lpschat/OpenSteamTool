"""Add-game dialog with M3 fetch options."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from opensteamtool_gui.services.fetcher.pipeline import FetchOptions


class AddGameDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加游戏")
        self.setModal(True)
        self.resize(520, 420)

        self._appid_edit = QLineEdit()
        self._appid_edit.setPlaceholderText("如 730")
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("可留空；自动获取成功时会覆盖")
        self.auto_fetch_check = QCheckBox("自动拉取元信息 / DLC / depot / token")
        self.auto_fetch_check.setChecked(True)
        self.include_dlcs_check = QCheckBox("自动包含 DLC")
        self.include_dlcs_check.setChecked(True)
        self.include_token_check = QCheckBox("获取 Access Token")
        self.include_token_check.setChecked(True)
        self.include_depots_check = QCheckBox("获取 depot key / manifest GID")
        self.include_depots_check.setChecked(True)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText("1 输入 AppID\n2 拉取元信息\n3 调整 DLC/Depot\n4 预览并添加到库")

        form = QFormLayout()
        form.addRow("AppID *", self._appid_edit)
        form.addRow("名称", self._name_edit)
        form.addRow("", self.auto_fetch_check)
        form.addRow("", self.include_dlcs_check)
        form.addRow("", self.include_token_check)
        form.addRow("", self.include_depots_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview, 1)
        layout.addWidget(buttons)

        self._appid: int | None = None
        self._name: str = ""
        self._appid_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_accept(self) -> None:
        text = self._appid_edit.text().strip()
        if not text.isdigit():
            QMessageBox.warning(self, "AppID 无效", "AppID 必须是正整数")
            return
        appid = int(text)
        if appid <= 0 or appid > 0xFFFFFFFF:
            QMessageBox.warning(self, "AppID 无效", "AppID 超出范围")
            return
        self._appid = appid
        self._name = self._name_edit.text().strip()
        self.accept()

    @property
    def appid(self) -> int | None:
        return self._appid

    @property
    def name(self) -> str:
        return self._name

    @property
    def auto_fetch(self) -> bool:
        return self.auto_fetch_check.isChecked()

    @property
    def options(self) -> FetchOptions:
        include_depots = self.include_depots_check.isChecked()
        return FetchOptions(
            include_dlcs=self.include_dlcs_check.isChecked(),
            include_depot_keys=include_depots,
            include_manifest_gids=include_depots,
            include_access_token=self.include_token_check.isChecked(),
        )
