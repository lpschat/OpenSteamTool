"""Library view — game list on the left, editable detail panel on the right."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from opensteamtool_gui.models.game import Depot, Game, GameRepository, to_bundle
from opensteamtool_gui.services import lua_generator, lua_parser, registry
from opensteamtool_gui.services.fetcher import caigames
from opensteamtool_gui.services.fetcher.base import FetchedGame
from opensteamtool_gui.services.fetcher.pipeline import create_default_pipeline, save_to_repository
from opensteamtool_gui.utils.hex_validate import is_decimal, is_depot_key, is_hex
from opensteamtool_gui.utils.http_client import create_async_client
from opensteamtool_gui.utils.paths import cache_dir
from opensteamtool_gui.views.add_game_dialog import AddGameDialog
from opensteamtool_gui.views.batch_import_dialog import BatchImportDialog
from opensteamtool_gui.views.widgets.collapsible_group import CollapsibleGroup


class DepotRow(QWidget):
    removed = Signal(QWidget)

    def __init__(self, depot: Depot | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.depot_id_edit = QLineEdit()
        self.depot_id_edit.setPlaceholderText("Depot ID")
        self.depot_id_edit.setValidator(QIntValidator(0, 0x7FFFFFFF, self))
        self.depot_id_edit.setMaximumWidth(120)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("64 字符 hex（可空）")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.eye_btn = QToolButton()
        self.eye_btn.setText("👁")
        self.eye_btn.setCheckable(True)
        self.eye_btn.toggled.connect(self._toggle_key_visible)

        self.manifest_edit = QLineEdit()
        self.manifest_edit.setPlaceholderText("Manifest GID（十进制，可空）")
        self.manifest_edit.setMaximumWidth(220)

        self.del_btn = QToolButton()
        self.del_btn.setText("✕")
        self.del_btn.clicked.connect(lambda: self.removed.emit(self))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.depot_id_edit)
        layout.addWidget(self.key_edit, 1)
        layout.addWidget(self.eye_btn)
        layout.addWidget(self.manifest_edit)
        layout.addWidget(self.del_btn)

        if depot is not None:
            self.depot_id_edit.setText(str(depot.depot_id))
            self.key_edit.setText(depot.decryption_key or "")
            self.manifest_edit.setText(depot.manifest_gid or "")

    def _toggle_key_visible(self, checked: bool) -> None:
        self.key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def to_depot(self, owner_appid: int) -> Depot | None:
        depot_text = self.depot_id_edit.text().strip()
        if not depot_text or not depot_text.isdigit():
            return None
        depot_id = int(depot_text)
        key = self.key_edit.text().strip() or None
        manifest = self.manifest_edit.text().strip() or None
        return Depot(
            depot_id=depot_id,
            owner_appid=owner_appid,
            decryption_key=key,
            manifest_gid=manifest,
        )


class DetailPanel(QWidget):
    saved = Signal(int)

    def __init__(
        self,
        repo: GameRepository,
        steam_path: Path | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.steam_path = steam_path
        self._game: Game | None = None
        self._depot_rows: list[DepotRow] = []

        self.name_edit = QLineEdit()
        self.appid_label = QLabel("—")
        self.enabled_check = QCheckBox("启用")

        self.access_token_edit = QLineEdit()
        self.access_token_edit.setPlaceholderText("uint64 十进制")
        self.app_ticket_edit = QLineEdit()
        self.app_ticket_edit.setPlaceholderText("hex 字符串")
        self.e_ticket_edit = QLineEdit()
        self.e_ticket_edit.setPlaceholderText("hex 字符串")
        self.stat_edit = QLineEdit()
        self.stat_edit.setPlaceholderText("SteamID（十进制）")
        self.note_edit = QLineEdit()

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self._on_save)
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self._on_delete)

        self._depots_container = QWidget()
        self._depots_layout = QVBoxLayout(self._depots_container)
        self._depots_layout.setContentsMargins(0, 0, 0, 0)
        self._depots_layout.setSpacing(4)
        self._add_depot_btn = QPushButton("+ 添加 Depot")
        self._add_depot_btn.clicked.connect(lambda: self._add_depot_row(None))

        self._build_layout()
        self.set_game(None)

    def _build_layout(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QFormLayout()
        header.addRow("名称", self.name_edit)
        header.addRow("AppID", self.appid_label)
        header.addRow("", self.enabled_check)
        layout.addLayout(header)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        depots_group = CollapsibleGroup("Depots", expanded=True)
        depots_inner = QVBoxLayout()
        depots_inner.setContentsMargins(8, 4, 0, 4)
        depots_inner.addWidget(self._depots_container)
        depots_inner.addWidget(self._add_depot_btn)
        depots_group.set_content_layout(depots_inner)
        layout.addWidget(depots_group)

        token_group = CollapsibleGroup("Access Token", expanded=False)
        token_form = QFormLayout()
        token_form.addRow("Token", self.access_token_edit)
        token_group.set_content_layout(token_form)
        layout.addWidget(token_group)

        ticket_group = CollapsibleGroup("App Ticket / E-Ticket", expanded=False)
        ticket_form = QFormLayout()
        ticket_form.addRow("AppTicket", self.app_ticket_edit)
        ticket_form.addRow("ETicket", self.e_ticket_edit)
        ticket_buttons = QHBoxLayout()
        write_app = QPushButton("写入 AppTicket")
        write_app.clicked.connect(lambda: self._write_registry_ticket("AppTicket"))
        clear_app = QPushButton("清除 AppTicket")
        clear_app.clicked.connect(lambda: self._clear_registry_ticket("AppTicket"))
        write_e = QPushButton("写入 ETicket")
        write_e.clicked.connect(lambda: self._write_registry_ticket("ETicket"))
        clear_e = QPushButton("清除 ETicket")
        clear_e.clicked.connect(lambda: self._clear_registry_ticket("ETicket"))
        restore = QPushButton("恢复上次备份")
        restore.clicked.connect(self._restore_registry_ticket)
        for button in (write_app, clear_app, write_e, clear_e, restore):
            ticket_buttons.addWidget(button)
        ticket_form.addRow(ticket_buttons)
        ticket_group.set_content_layout(ticket_form)
        layout.addWidget(ticket_group)

        stat_group = CollapsibleGroup("Stat Override", expanded=False)
        stat_form = QFormLayout()
        stat_form.addRow("SteamID", self.stat_edit)
        stat_group.set_content_layout(stat_form)
        layout.addWidget(stat_group)

        meta_group = CollapsibleGroup("备注", expanded=False)
        meta_form = QFormLayout()
        meta_form.addRow("备注", self.note_edit)
        meta_group.set_content_layout(meta_form)
        layout.addWidget(meta_group)

        layout.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _clear_depot_rows(self) -> None:
        for row in self._depot_rows:
            self._depots_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._depot_rows.clear()

    def _add_depot_row(self, depot: Depot | None) -> None:
        row = DepotRow(depot)
        row.removed.connect(self._on_depot_removed)
        self._depots_layout.addWidget(row)
        self._depot_rows.append(row)

    def _on_depot_removed(self, row: DepotRow) -> None:
        if row in self._depot_rows:
            self._depot_rows.remove(row)
        self._depots_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()

    def set_game(self, game: Game | None) -> None:
        self._game = game
        editable = game is not None
        self.name_edit.setEnabled(editable)
        self.enabled_check.setEnabled(editable)
        self.access_token_edit.setEnabled(editable)
        self.app_ticket_edit.setEnabled(editable)
        self.e_ticket_edit.setEnabled(editable)
        self.stat_edit.setEnabled(editable)
        self.note_edit.setEnabled(editable)
        self.save_btn.setEnabled(editable)
        self.delete_btn.setEnabled(editable)
        self._add_depot_btn.setEnabled(editable)

        self._clear_depot_rows()
        if game is None:
            self.name_edit.clear()
            self.appid_label.setText("—")
            self.enabled_check.setChecked(False)
            self.access_token_edit.clear()
            self.app_ticket_edit.clear()
            self.e_ticket_edit.clear()
            self.stat_edit.clear()
            self.note_edit.clear()
            return

        self.name_edit.setText(game.name)
        self.appid_label.setText(str(game.appid))
        self.enabled_check.setChecked(game.enabled)
        self.access_token_edit.setText(game.access_token or "")
        self.app_ticket_edit.setText(game.app_ticket_hex or "")
        self.e_ticket_edit.setText(game.e_ticket_hex or "")
        self.stat_edit.setText(game.stat_steam_id or "")
        self.note_edit.setText(game.note or "")
        for depot in game.depots:
            self._add_depot_row(depot)

    def _collect(self) -> Game | None:
        if self._game is None:
            return None
        appid = self._game.appid
        depots: list[Depot] = []
        for row in self._depot_rows:
            depot = row.to_depot(appid)
            if depot is None:
                continue
            if depot.decryption_key and not is_depot_key(depot.decryption_key):
                QMessageBox.warning(
                    self, "Depot Key 无效",
                    f"Depot {depot.depot_id} 的密钥必须是 64 字符 hex"
                )
                return None
            if depot.manifest_gid and not is_decimal(depot.manifest_gid):
                QMessageBox.warning(
                    self, "Manifest GID 无效",
                    f"Depot {depot.depot_id} 的 Manifest GID 必须是十进制数字"
                )
                return None
            depots.append(depot)

        access_token = self.access_token_edit.text().strip() or None
        if access_token and not is_decimal(access_token):
            QMessageBox.warning(self, "Access Token 无效", "必须是十进制数字")
            return None

        app_ticket = self.app_ticket_edit.text().strip() or None
        if app_ticket and not is_hex(app_ticket):
            QMessageBox.warning(self, "AppTicket 无效", "必须是 hex 字符串")
            return None

        e_ticket = self.e_ticket_edit.text().strip() or None
        if e_ticket and not is_hex(e_ticket):
            QMessageBox.warning(self, "ETicket 无效", "必须是 hex 字符串")
            return None

        stat_id = self.stat_edit.text().strip() or None
        if stat_id and not is_decimal(stat_id):
            QMessageBox.warning(self, "Stat SteamID 无效", "必须是十进制数字")
            return None

        seen_ids = set()
        for d in depots:
            if d.depot_id in seen_ids:
                QMessageBox.warning(self, "Depot 重复", f"Depot {d.depot_id} 出现多次")
                return None
            seen_ids.add(d.depot_id)

        return Game(
            appid=appid,
            name=self.name_edit.text().strip(),
            type=self._game.type,
            parent_appid=self._game.parent_appid,
            header_image=self._game.header_image,
            source=self._game.source or "Manual",
            fetched_at=self._game.fetched_at,
            enabled=self.enabled_check.isChecked(),
            incomplete=self._game.incomplete,
            managed=self._game.managed,
            note=self.note_edit.text().strip() or None,
            depots=depots,
            access_token=access_token,
            app_ticket_hex=app_ticket,
            e_ticket_hex=e_ticket,
            stat_steam_id=stat_id,
        )

    def _on_save(self) -> None:
        game = self._collect()
        if game is None:
            return
        self.repo.upsert_game(game)
        self._sync_lua(game)
        self._game = self.repo.get(game.appid)
        self.saved.emit(game.appid)

    def _sync_lua(self, game: Game) -> None:
        if self.steam_path is None:
            return
        if not game.enabled or game.parent_appid is not None:
            lua_generator.remove(self.steam_path, game.appid)
            return
        dlcs = self.repo.list_dlcs(game.appid)
        bundle = to_bundle(game, dlcs)
        try:
            lua_generator.write(self.steam_path, bundle)
        except OSError as e:
            QMessageBox.warning(self, "Lua 写入失败", str(e))

    def _on_delete(self) -> None:
        if self._game is None:
            return
        appid = self._game.appid
        confirm = QMessageBox.question(
            self,
            "删除游戏",
            f"确定删除 AppID {appid} 及其所有 DLC / Depot 配置？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.repo.delete_game(appid)
        if self.steam_path is not None:
            lua_generator.remove(self.steam_path, appid)
        self.set_game(None)
        self.saved.emit(appid)

    def _write_registry_ticket(self, value_name: str) -> None:
        if self._game is None:
            return
        edit = self.app_ticket_edit if value_name == "AppTicket" else self.e_ticket_edit
        try:
            registry.write_ticket(
                self.repo.conn,
                registry.WinRegistryBackend(),
                self._game.appid,
                value_name,
                edit.text().strip(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "注册表写入失败", str(exc))
            return
        QMessageBox.information(self, "写入完成", f"{value_name} 已写入注册表")

    def _clear_registry_ticket(self, value_name: str) -> None:
        if self._game is None:
            return
        try:
            registry.clear_ticket(
                self.repo.conn,
                registry.WinRegistryBackend(),
                self._game.appid,
                value_name,
            )
        except Exception as exc:
            QMessageBox.warning(self, "注册表清除失败", str(exc))
            return
        QMessageBox.information(self, "清除完成", f"{value_name} 已清除")

    def _restore_registry_ticket(self) -> None:
        if self._game is None:
            return
        backend = registry.WinRegistryBackend()
        restored = False
        for value_name in ("AppTicket", "ETicket"):
            restored = (
                registry.restore_latest_backup(
                    self.repo.conn,
                    backend,
                    self._game.appid,
                    value_name,
                )
                or restored
            )
        QMessageBox.information(self, "恢复结果", "已恢复" if restored else "没有备份")


class LibraryView(QWidget):
    COLUMNS = ["启用", "名称", "AppID", "DLC", "Depot"]

    def __init__(
        self,
        conn: sqlite3.Connection,
        steam_path: Path | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repo = GameRepository(conn)
        self.steam_path = steam_path

        self.add_btn = QPushButton("+ 添加游戏")
        self.add_btn.clicked.connect(self._on_add)
        self.batch_btn = QPushButton("批量导入")
        self.batch_btn.clicked.connect(self._on_batch_import)
        self.import_lua_btn = QPushButton("从 Lua 导入")
        self.import_lua_btn.clicked.connect(self._on_import_lua)
        self.enable_btn = QPushButton("启用选中")
        self.enable_btn.clicked.connect(lambda: self._set_selected_enabled(True))
        self.disable_btn = QPushButton("禁用选中")
        self.disable_btn.clicked.connect(lambda: self._set_selected_enabled(False))
        self.delete_selected_btn = QPushButton("删除选中")
        self.delete_selected_btn.clicked.connect(self._delete_selected)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索名称或 AppID")
        self.search_edit.textChanged.connect(self.refresh)
        self.online_search_btn = QPushButton("在线搜索")
        self.online_search_btn.clicked.connect(self._on_online_search)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in (0, 2, 3, 4):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        self.detail = DetailPanel(self.repo, steam_path)
        self.detail.saved.connect(lambda _aid: self.refresh())

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.batch_btn)
        toolbar.addWidget(self.import_lua_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.search_edit, 1)
        toolbar.addWidget(self.online_search_btn)
        toolbar.addStretch(1)

        batch_bar = QHBoxLayout()
        batch_bar.addWidget(self.enable_btn)
        batch_bar.addWidget(self.disable_btn)
        batch_bar.addWidget(self.delete_selected_btn)
        batch_bar.addStretch(1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addLayout(toolbar)
        left_layout.addLayout(batch_bar)
        left_layout.addWidget(self.table)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)

        self._games: list[Game] = []
        self.refresh()

    def refresh(self) -> None:
        selected_appid = None
        if self.detail._game is not None:
            selected_appid = self.detail._game.appid

        self._games = self._filter_games(self.repo.list_main_games())
        self.table.setRowCount(len(self._games))
        for row, game in enumerate(self._games):
            enabled_item = QTableWidgetItem("✓" if game.enabled else "")
            enabled_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, enabled_item)
            self.table.setItem(row, 1, QTableWidgetItem(game.name or "(未命名)"))
            self.table.setItem(row, 2, QTableWidgetItem(str(game.appid)))
            dlc_count = len(self.repo.list_dlcs(game.appid))
            self.table.setItem(row, 3, QTableWidgetItem(str(dlc_count)))
            self.table.setItem(row, 4, QTableWidgetItem(str(len(game.depots))))

        if selected_appid is not None:
            for row, game in enumerate(self._games):
                if game.appid == selected_appid:
                    self.table.selectRow(row)
                    return
        self.detail.set_game(None)

    def _on_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail.set_game(None)
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._games):
            game = self.repo.get(self._games[idx].appid)
            self.detail.set_game(game)

    def _on_add(self) -> None:
        dialog = AddGameDialog(self)
        if dialog.exec() != AddGameDialog.DialogCode.Accepted:
            return
        appid = dialog.appid
        if appid is None:
            return
        if self.repo.get(appid) is not None:
            QMessageBox.information(self, "重复 AppID", f"AppID {appid} 已存在")
            return
        if dialog.auto_fetch:
            fetched = self._fetch_one(appid, dialog.options)
            if fetched is not None:
                self._save_fetched(fetched)
                return
        game = Game(appid=appid, name=dialog.name, source="Manual")
        self.repo.upsert_game(game)
        self.refresh()
        for row, g in enumerate(self._games):
            if g.appid == appid:
                self.table.selectRow(row)
                break

    def _on_batch_import(self) -> None:
        dialog = BatchImportDialog(self)
        if dialog.exec() != BatchImportDialog.DialogCode.Accepted:
            return
        try:
            fetched = self._fetch_many(dialog.appids, dialog.options)
        except Exception as exc:
            QMessageBox.warning(self, "批量导入失败", str(exc))
            return
        saved = 0
        for item in fetched:
            if self.repo.get(item.appid) is None:
                self._save_fetched(item, refresh=False)
                saved += 1
        self.refresh()
        QMessageBox.information(self, "批量导入完成", f"已添加 {saved} 个主游戏")

    def _on_online_search(self) -> None:
        query = self.search_edit.text().strip()
        if not query:
            QMessageBox.information(self, "请输入关键词", "请先在搜索框输入游戏名")
            return
        try:
            results = self._search_online(query)
        except Exception as exc:
            QMessageBox.warning(self, "搜索失败", str(exc))
            return
        labels = [f"{item.name} ({item.appid})" for item in results[:20]]
        if not labels:
            QMessageBox.information(self, "无结果", "CaiGames 未返回候选结果")
            return
        label, ok = QInputDialog.getItem(self, "在线搜索结果", "选择游戏", labels, 0, False)
        if ok:
            appid = results[labels.index(label)].appid
            fetched = self._fetch_one(appid, None)
            if fetched is not None:
                self._save_fetched(fetched)

    def _filter_games(self, games: list[Game]) -> list[Game]:
        query = self.search_edit.text().strip().lower()
        if not query:
            return games
        return [
            game for game in games
            if query in game.name.lower() or query in str(game.appid)
        ]

    def _save_fetched(
        self,
        fetched: FetchedGame,
        *,
        refresh: bool = True,
    ) -> None:
        save_to_repository(self.repo, fetched)
        game = self.repo.get(fetched.appid)
        if game is not None:
            self._sync_lua(game)
        if refresh:
            self.refresh()
            self._select_appid(fetched.appid)

    def _select_appid(self, appid: int) -> None:
        for row, game in enumerate(self._games):
            if game.appid == appid:
                self.table.selectRow(row)
                break

    def _sync_lua(self, game: Game) -> None:
        if self.steam_path is None or game.parent_appid is not None:
            return
        if not game.enabled:
            lua_generator.remove(self.steam_path, game.appid)
            return
        try:
            lua_generator.write(self.steam_path, to_bundle(game, self.repo.list_dlcs(game.appid)))
        except OSError as exc:
            QMessageBox.warning(self, "Lua 写入失败", str(exc))

    def _selected_appids(self) -> list[int]:
        rows = self.table.selectionModel().selectedRows()
        return [
            self._games[index.row()].appid
            for index in rows
            if 0 <= index.row() < len(self._games)
        ]

    def _set_selected_enabled(self, enabled: bool) -> None:
        appids = self._selected_appids()
        if not appids:
            return
        self.repo.set_enabled_many(appids, enabled)
        for appid in appids:
            game = self.repo.get(appid)
            if game is not None:
                self._sync_lua(game)
        self.refresh()

    def _delete_selected(self) -> None:
        appids = self._selected_appids()
        if not appids:
            return
        confirm = QMessageBox.question(
            self,
            "删除选中游戏",
            f"确定删除 {len(appids)} 个游戏及其配置？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self.steam_path is not None:
            for appid in appids:
                lua_generator.remove(self.steam_path, appid)
        self.repo.delete_many(appids)
        self.refresh()

    def _on_import_lua(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "导入 Lua", "", "Lua Files (*.lua)")
        imported = 0
        for raw_path in paths:
            try:
                game = lua_parser.parse_lua(Path(raw_path).read_text(encoding="utf-8"))
            except Exception as exc:
                QMessageBox.warning(self, "Lua 导入失败", f"{raw_path}\n{exc}")
                continue
            self.repo.upsert_game(game)
            imported += 1
        self.refresh()
        if imported:
            QMessageBox.information(self, "导入完成", f"已导入 {imported} 个外部 Lua 条目")

    def _fetch_one(self, appid: int, options) -> FetchedGame | None:
        try:
            return asyncio.run(_fetch_one_async(appid, options))
        except Exception as exc:
            QMessageBox.warning(self, "获取失败", str(exc))
            return None

    def _fetch_many(self, appids: list[int], options) -> list[FetchedGame]:
        return asyncio.run(_fetch_many_async(appids, options))

    def _search_online(self, query: str):
        return asyncio.run(_search_online_async(query))


async def _fetch_one_async(appid: int, options) -> FetchedGame:
    async with create_async_client() as client:
        pipeline = create_default_pipeline(client, cache_dir())
        return await pipeline.fetch_game(appid, options)


async def _fetch_many_async(appids: list[int], options) -> list[FetchedGame]:
    async with create_async_client() as client:
        pipeline = create_default_pipeline(client, cache_dir())
        return await pipeline.fetch_many(appids, options, concurrency=5)


async def _search_online_async(query: str):
    async with create_async_client() as client:
        return await caigames.CaiGamesFetcher(client).search(query)
