Release DLLs are staged here by CI:

- OpenSteamTool.dll
- dwmapi.dll
- xinput1_4.dll
- manifest.json

Local development may leave this directory without DLLs; the installer page
will report the built-in source as incomplete until the files are present.
