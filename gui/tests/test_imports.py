"""Smoke test: every module under opensteamtool_gui imports cleanly.

Note: importing PySide6-backed views requires the Qt platform plugin to be
loadable. We set QT_QPA_PLATFORM=offscreen so the test passes headlessly.
"""

from __future__ import annotations

import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

MODULES = [
    "opensteamtool_gui",
    "opensteamtool_gui.utils.paths",
    "opensteamtool_gui.utils.atomic_write",
    "opensteamtool_gui.utils.hex_validate",
    "opensteamtool_gui.utils.cache",
    "opensteamtool_gui.utils.http_client",
    "opensteamtool_gui.utils.cn_detect",
    "opensteamtool_gui.services.steam_path",
    "opensteamtool_gui.services.lua_generator",
    "opensteamtool_gui.services.installer",
    "opensteamtool_gui.services.upstream_dll_release",
    "opensteamtool_gui.services.log_reader",
    "opensteamtool_gui.services.lua_parser",
    "opensteamtool_gui.services.registry",
    "opensteamtool_gui.services.fetcher.base",
    "opensteamtool_gui.services.fetcher.steam_api",
    "opensteamtool_gui.services.fetcher.caigames",
    "opensteamtool_gui.services.fetcher.steamcmd",
    "opensteamtool_gui.services.fetcher.github_repos",
    "opensteamtool_gui.services.fetcher.sudama",
    "opensteamtool_gui.services.fetcher.pipeline",
    "opensteamtool_gui.models.database",
    "opensteamtool_gui.models.settings",
    "opensteamtool_gui.models.game",
    "opensteamtool_gui.views.installer_view",
    "opensteamtool_gui.views.log_viewer",
    "opensteamtool_gui.views.batch_import_dialog",
    "opensteamtool_gui.views.settings_view",
    "opensteamtool_gui.views.theme",
]


def test_core_modules_import():
    for name in MODULES:
        importlib.import_module(name)
