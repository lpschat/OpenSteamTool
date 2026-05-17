"""CaiGames backup metadata/search fetcher."""

from __future__ import annotations

import httpx

from opensteamtool_gui.services.fetcher.base import FetchedApp, FetchedGame
from opensteamtool_gui.utils.http_client import request_json

AUTH_HEADER = {"X-Client-Auth": "CaiGames-pvzcxw"}
BASE_URL = "https://api.9178666.xyz"


def parse_search(payload: dict) -> list[FetchedApp]:
    rows = payload.get("data") or payload.get("results") or payload
    if not isinstance(rows, list):
        return []
    return [
        FetchedApp(appid=int(row["appid"]), name=str(row.get("name") or ""), source="CaiGames")
        for row in rows
        if isinstance(row, dict) and str(row.get("appid") or "").isdigit()
    ]


def parse_metadata(appid: int, payload: dict) -> FetchedGame:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    return FetchedGame(
        appid=appid,
        name=str(data.get("name") or data.get("title") or ""),
        header_image=data.get("header_image") or data.get("header"),
        source="CaiGames",
        incomplete=not bool(data.get("name") or data.get("title")),
    )


class CaiGamesFetcher:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch_metadata(self, appid: int) -> FetchedGame:
        return parse_metadata(
            appid,
            await request_json(self.client, f"{BASE_URL}/cmd/{appid}", headers=AUTH_HEADER),
        )

    async def search(self, query: str) -> list[FetchedApp]:
        payload = await request_json(self.client, f"{BASE_URL}/search?keyword={query}")
        return parse_search(payload)
