"""Sudama full-library depot key and access token helpers."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx

from opensteamtool_gui.services.fetcher.base import DepotInfo
from opensteamtool_gui.utils.cache import JsonCache
from opensteamtool_gui.utils.http_client import request_json

KEYS_URL = "https://api.993499094.xyz/depotkeys.json"
TOKENS_URL = "https://api.993499094.xyz/appaccesstokens.json"


def lookup_depot_keys(owner_appid: int, payload: Any) -> list[DepotInfo]:
    if isinstance(payload, dict):
        rows = payload.items()
    elif isinstance(payload, list):
        rows = ((_row_depot_id(row), _row_key(row)) for row in payload)
    else:
        rows = []
    result = []
    for depot_id, value in rows:
        key = _extract_key(value)
        if str(depot_id).isdigit() and key:
            result.append(DepotInfo(int(depot_id), owner_appid, key, key_source="Sudama"))
    return result


def lookup_access_token(appid: int, payload: Any) -> str | None:
    if isinstance(payload, dict):
        value = payload.get(str(appid)) or payload.get(appid)
        return str(value) if value else None
    for row in payload if isinstance(payload, list) else []:
        if int(row.get("appid", 0)) == appid and row.get("token"):
            return str(row["token"])
    return None


class SudamaFetcher:
    def __init__(self, client: httpx.AsyncClient, cache: JsonCache) -> None:
        self.client = client
        self.cache = cache

    async def fetch_depots(self, appid: int) -> list[DepotInfo]:
        payload = await self._cached_json("sudama_keys.json", KEYS_URL)
        return lookup_depot_keys(appid, payload)

    async def fetch_access_token(self, appid: int) -> str | None:
        payload = await self._cached_json("sudama_tokens.json", TOKENS_URL)
        return lookup_access_token(appid, payload)

    async def _cached_json(self, key: str, url: str) -> Any:
        cached = self.cache.read(key, ttl=timedelta(hours=24))
        if cached is not None:
            return cached
        payload = await request_json(self.client, url)
        self.cache.write(key, payload)
        return payload


def _extract_key(value: Any) -> str | None:
    if isinstance(value, str) and len(value) == 64:
        return value
    if isinstance(value, dict):
        return value.get("decryption_key") or value.get("key")
    return None


def _row_depot_id(row: dict) -> object:
    return row.get("depot_id") or row.get("depotid") or row.get("id")


def _row_key(row: dict) -> object:
    return row.get("decryption_key") or row.get("key")
