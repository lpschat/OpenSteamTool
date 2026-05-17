"""steamcmd.net depot/manifest parser and fetcher."""

from __future__ import annotations

import httpx

from opensteamtool_gui.services.fetcher.base import DepotInfo
from opensteamtool_gui.utils.http_client import request_json


def parse_info(appid: int, payload: dict) -> list[DepotInfo]:
    app = _app_node(appid, payload)
    depots = app.get("depots") or {}
    result: list[DepotInfo] = []
    for raw_depot_id, data in depots.items():
        if not str(raw_depot_id).isdigit() or not isinstance(data, dict):
            continue
        manifest = _first_manifest(data.get("manifests") or {})
        result.append(DepotInfo(int(raw_depot_id), appid, manifest_gid=manifest))
    return result


class SteamCmdFetcher:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch_depots(self, appid: int) -> list[DepotInfo]:
        url = f"https://api.steamcmd.net/v1/info/{appid}"
        return parse_info(appid, await request_json(self.client, url))


def _app_node(appid: int, payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    node = data.get(str(appid), data)
    return node if isinstance(node, dict) else {}


def _first_manifest(manifests: dict) -> str | None:
    for value in manifests.values():
        if isinstance(value, dict) and value.get("gid"):
            return str(value["gid"])
    return None
