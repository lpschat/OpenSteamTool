# OpenSteamTool GUI FAQ

## Why does installation require administrator rights?

Steam is commonly installed under `Program Files (x86)`, so writing loader DLLs
to the Steam root often requires elevation.

## Does the GUI talk to the DLL over IPC?

No. The GUI writes Lua files and reads logs. The DLL already watches Lua files
and hot-reloads changes.

## Where is GUI data stored?

By default, `%APPDATA%\OpenSteamTool-GUI\`.

## Does the GUI auto-update itself?

No. v1 only supports online DLL update/staging. GUI updates are distributed as
release zip files.
