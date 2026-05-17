"""Tests for M3 data source parsers."""

from __future__ import annotations

from opensteamtool_gui.services.fetcher import caigames, github_repos, steam_api, steamcmd, sudama


def test_parse_steam_appdetails_extracts_name_cover_and_dlcs() -> None:
    payload = {
        "730": {
            "success": True,
            "data": {
                "name": "Counter-Strike 2",
                "type": "game",
                "header_image": "https://cdn.example/header.jpg",
                "dlc": [111, 222],
            },
        }
    }

    result = steam_api.parse_appdetails(730, payload)

    assert result.name == "Counter-Strike 2"
    assert result.header_image == "https://cdn.example/header.jpg"
    assert [dlc.appid for dlc in result.dlcs] == [111, 222]


def test_parse_steamcmd_info_extracts_depots_and_manifest_gid() -> None:
    payload = {
        "data": {
            "730": {
                "depots": {
                    "731": {"manifests": {"public": {"gid": "123456"}}},
                    "branches": {"public": {"buildid": "1"}},
                }
            }
        }
    }

    depots = steamcmd.parse_info(730, payload)

    assert depots[0].depot_id == 731
    assert depots[0].manifest_gid == "123456"


def test_parse_github_lua_extracts_hex_depot_keys() -> None:
    lua = 'addappid(731, 1, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")'

    depots = github_repos.parse_depot_keys_from_lua(730, lua, source="Auiowu/ManifestAutoUpdate")

    assert depots[0].depot_id == 731
    assert depots[0].decryption_key == "a" * 64
    assert depots[0].key_source == "Auiowu/ManifestAutoUpdate"


def test_sudama_lookup_supports_dict_payloads() -> None:
    keys = {"731": "b" * 64}
    tokens = {"730": "42"}

    depots = sudama.lookup_depot_keys(730, keys)
    token = sudama.lookup_access_token(730, tokens)

    assert depots[0].depot_id == 731
    assert depots[0].decryption_key == "b" * 64
    assert token == "42"


def test_parse_caigames_search_results() -> None:
    payload = {"data": [{"appid": 730, "name": "Counter-Strike 2"}]}

    results = caigames.parse_search(payload)

    assert [(item.appid, item.name) for item in results] == [(730, "Counter-Strike 2")]
