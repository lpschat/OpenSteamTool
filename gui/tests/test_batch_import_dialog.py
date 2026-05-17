"""Tests for batch import parsing."""

from __future__ import annotations

from opensteamtool_gui.views.batch_import_dialog import parse_appids


def test_parse_appids_accepts_lines_urls_and_deduplicates() -> None:
    text = "730\nhttps://store.steampowered.com/app/440/Team_Fortress_2/\n730\ninvalid"

    assert parse_appids(text) == [730, 440]
