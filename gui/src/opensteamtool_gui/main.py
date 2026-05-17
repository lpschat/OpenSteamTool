"""GUI entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from opensteamtool_gui.app import App


def main() -> int:
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("OpenSteamTool GUI")
    qt_app.setOrganizationName("OpenSteamTool")
    app = App(qt_app)
    app.show()
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
