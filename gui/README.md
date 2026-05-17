# OpenSteamTool GUI

PySide6 management tool for OpenSteamTool DLL.

## Development

```powershell
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run python -m opensteamtool_gui
```

## Build

```powershell
uv run pyside6-lrelease i18n/*.ts
uv run python build_exe.py
```

The build output is `dist/OpenSteamTool-GUI/`. Release DLLs are expected in
`src/opensteamtool_gui/resources/dlls/` with `manifest.json`.

## Features

- Library CRUD with SQLite and generated Lua files under `<Steam>/config/lua/managed/`
- DLL installer, uninstaller, backup, rollback, and upstream release staging
- Log viewer for `<Steam>/opensteamtool/*.log`
- Steam/CaiGames/SteamCMD/GitHub/Sudama data fetching pipeline
- Batch import, legacy Lua import, ticket registry helpers, theme and settings page
