"""GitHub manifest repository key parsing."""

from __future__ import annotations

import re

import httpx

from opensteamtool_gui.services.fetcher.base import DepotInfo

KEY_RE = re.compile(r"addappid\((\d+)\s*,\s*1\s*,\s*[\"']([0-9a-fA-F]{64})[\"']\)")


def parse_depot_keys_from_lua(owner_appid: int, content: str, *, source: str) -> list[DepotInfo]:
    result = []
    for match in KEY_RE.finditer(content):
        result.append(
            DepotInfo(
                depot_id=int(match.group(1)),
                owner_appid=owner_appid,
                decryption_key=match.group(2),
                key_source=source,
            )
        )
    return result


class GitHubReposFetcher:
    def __init__(self, client: httpx.AsyncClient, repos: list[str] | None = None) -> None:
        self.client = client
        self.repos = repos or ["Auiowu/ManifestAutoUpdate", "Satisl/MAU"]

    async def fetch_depots(self, appid: int) -> list[DepotInfo]:
        for repo in self.repos:
            depots = await self._fetch_repo(appid, repo)
            if depots:
                return depots
        return []

    async def _fetch_repo(self, appid: int, repo: str) -> list[DepotInfo]:
        url = f"https://raw.githubusercontent.com/{repo}/{appid}/{appid}.lua"
        response = await self.client.get(url)
        if response.status_code >= 400:
            return []
        return parse_depot_keys_from_lua(appid, response.text, source=repo)
