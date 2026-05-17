"""Qt stylesheet tokens for light/dark GUI themes."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

THEMES = {"system", "light", "dark"}


def stylesheet(theme: str) -> str:
    mode = "dark" if theme == "dark" else "light"
    colors = _colors(mode)
    return f"""
QWidget {{
    background: {colors["bg"]};
    color: {colors["text"]};
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 10pt;
}}
QLineEdit, QTextEdit, QPlainTextEdit, QTableWidget, QListWidget {{
    background: {colors["surface"]};
    border: 1px solid {colors["border"]};
    border-radius: 6px;
    padding: 4px;
}}
QPushButton {{
    background: {colors["button"]};
    border: 1px solid {colors["border"]};
    border-radius: 6px;
    padding: 6px 10px;
}}
QPushButton:hover {{ background: {colors["button_hover"]}; }}
QHeaderView::section {{
    background: {colors["elevated"]};
    border: 0;
    padding: 4px;
}}
"""


def apply_theme(app: QApplication, theme: str | None) -> None:
    app.setStyleSheet(stylesheet(theme or "system"))


def _colors(mode: str) -> dict[str, str]:
    if mode == "dark":
        return {
            "bg": "#0B0B10",
            "surface": "#15151D",
            "elevated": "#1E1E2A",
            "text": "#F2EDE0",
            "border": "#444450",
            "button": "#242433",
            "button_hover": "#303044",
        }
    return {
        "bg": "#F5F3EE",
        "surface": "#FFFFFF",
        "elevated": "#FAF7F0",
        "text": "#1A1A22",
        "border": "#D8D2C6",
        "button": "#F4F0E8",
        "button_hover": "#E9E2D5",
    }
