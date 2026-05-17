"""Import legacy OpenSteamTool Lua files into GUI game records."""

from __future__ import annotations

import re

from opensteamtool_gui.models.game import Depot, Game

ADDAPPID_RE = re.compile(
    r"addappid\(\s*(\d+)(?:\s*,\s*\d+\s*,\s*[\"']([0-9a-fA-F]{64})[\"'])?",
    re.IGNORECASE,
)
CALL_RE = re.compile(r"(addtoken|setManifestid|setAppTicket|setETicket|setStat)\((.*?)\)")
COMMENT_RE = re.compile(r"--\s*AppID\s+(\d+)\s*:\s*(.+)")


class LuaParseError(ValueError):
    """Raised when a Lua file does not contain an importable appid."""


def parse_lua(content: str, *, appid_hint: int | None = None) -> Game:
    names = _comment_names(content)
    add_calls = list(ADDAPPID_RE.finditer(content))
    main_appid = appid_hint or _first_appid(add_calls)
    if main_appid is None:
        raise LuaParseError("Lua file does not contain addappid(appid)")
    depots = _parse_depots(main_appid, add_calls)
    _apply_manifest_ids(depots, content)
    values = _parse_app_values(main_appid, content)
    return Game(
        appid=main_appid,
        name=names.get(main_appid, ""),
        source="Imported",
        managed=False,
        depots=depots,
        access_token=values.get("addtoken"),
        app_ticket_hex=values.get("setAppTicket"),
        e_ticket_hex=values.get("setETicket"),
        stat_steam_id=values.get("setStat"),
    )


def _comment_names(content: str) -> dict[int, str]:
    result = {}
    for match in COMMENT_RE.finditer(content):
        result[int(match.group(1))] = match.group(2).strip()
    return result


def _first_appid(matches: list[re.Match[str]]) -> int | None:
    return int(matches[0].group(1)) if matches else None


def _parse_depots(main_appid: int, matches: list[re.Match[str]]) -> list[Depot]:
    depots = []
    for match in matches:
        appid = int(match.group(1))
        key = match.group(2)
        if appid == main_appid and key is None:
            continue
        if key is not None:
            depots.append(Depot(appid, main_appid, decryption_key=key))
    return depots


def _apply_manifest_ids(depots: list[Depot], content: str) -> None:
    by_id = {depot.depot_id: depot for depot in depots}
    for call, args in CALL_RE.findall(content):
        if call != "setManifestid":
            continue
        parsed = _parse_two_args(args)
        if parsed and parsed[0] in by_id:
            by_id[parsed[0]].manifest_gid = parsed[1]


def _parse_app_values(appid: int, content: str) -> dict[str, str]:
    values = {}
    for call, args in CALL_RE.findall(content):
        if call == "setManifestid":
            continue
        parsed = _parse_two_args(args)
        if parsed and parsed[0] == appid:
            values[call] = parsed[1]
    return values


def _parse_two_args(args: str) -> tuple[int, str] | None:
    match = re.search(r"\s*(\d+)\s*,\s*[\"']([^\"']+)[\"']", args)
    if not match:
        return None
    return int(match.group(1)), match.group(2)
