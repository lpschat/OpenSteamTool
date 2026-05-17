"""Batch appid import dialog."""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from opensteamtool_gui.services.fetcher.pipeline import FetchOptions

APPID_RE = re.compile(r"(?:/app/)?(\d{2,10})")


class BatchImportDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("批量导入")
        self.resize(520, 420)
        self.text = QTextEdit()
        self.text.setPlaceholderText("每行一个 appid，也可粘贴 Steam 商店 URL")
        self.include_dlcs = QCheckBox("自动包含 DLC")
        self.include_dlcs.setChecked(True)
        self.include_tokens = QCheckBox("获取 Access Token")
        self.include_tokens.setChecked(True)
        self.include_depots = QCheckBox("获取 depot key / manifest GID")
        self.include_depots.setChecked(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("输入列表"))
        layout.addWidget(self.text, 1)
        layout.addWidget(self.include_dlcs)
        layout.addWidget(self.include_tokens)
        layout.addWidget(self.include_depots)
        layout.addWidget(buttons)
        self._appids: list[int] = []

    @property
    def appids(self) -> list[int]:
        return self._appids

    @property
    def options(self) -> FetchOptions:
        return FetchOptions(
            include_dlcs=self.include_dlcs.isChecked(),
            include_depot_keys=self.include_depots.isChecked(),
            include_manifest_gids=self.include_depots.isChecked(),
            include_access_token=self.include_tokens.isChecked(),
        )

    def _accept(self) -> None:
        self._appids = parse_appids(self.text.toPlainText())
        if not self._appids:
            QMessageBox.warning(self, "没有 AppID", "请输入至少一个有效 AppID")
            return
        self.accept()


def parse_appids(text: str) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for match in APPID_RE.finditer(text):
        appid = int(match.group(1))
        if appid not in seen:
            seen.add(appid)
            result.append(appid)
    return result
