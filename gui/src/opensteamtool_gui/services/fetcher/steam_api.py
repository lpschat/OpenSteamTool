"""Steam store appdetails metadata fetcher."""

from __future__ import annotations

import httpx

from opensteamtool_gui.services.fetcher.base import FetchedApp, FetchedGame
from opensteamtool_gui.utils.http_client import request_json


def parse_appdetails(appid: int, payload: dict) -> FetchedGame:
    node = payload.get(str(appid)) or {}
    if not node.get("success"):
        raise ValueError(f"Steam appdetails failed for {appid}")
    data = node.get("data") or {}
    dlcs = [FetchedApp(appid=int(dlc), type="dlc", source="Steam") for dlc in data.get("dlc") or []]
    return FetchedGame(
        appid=appid,
        name=str(data.get("name") or ""),
        type=str(data.get("type") or "game"),
        header_image=data.get("header_image"),
        dlcs=dlcs,
        source="Steam",
        incomplete=not bool(data.get("name")),
    )


class SteamApiFetcher:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch_metadata(self, appid: int) -> FetchedGame:
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english"
        return parse_appdetails(appid, await request_json(self.client, url))
