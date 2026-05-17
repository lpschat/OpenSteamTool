"""Tests for importing existing Lua unlock files."""

from __future__ import annotations

from opensteamtool_gui.services import lua_parser


def test_parse_lua_extracts_game_depots_tokens_tickets_and_stat() -> None:
    content = """
-- AppID 730: Counter-Strike 2
addappid(730)
addappid(731, 1, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
addtoken(730, "42")
setManifestid(731, "123456")
setAppTicket(730, "deadbeef")
setETicket(730, "cafe")
setStat(730, "76561198000000000")
"""

    game = lua_parser.parse_lua(content)

    assert game.appid == 730
    assert game.name == "Counter-Strike 2"
    assert game.managed is False
    assert game.depots[0].depot_id == 731
    assert game.depots[0].decryption_key == "a" * 64
    assert game.depots[0].manifest_gid == "123456"
    assert game.access_token == "42"
    assert game.app_ticket_hex == "deadbeef"
    assert game.e_ticket_hex == "cafe"
    assert game.stat_steam_id == "76561198000000000"
