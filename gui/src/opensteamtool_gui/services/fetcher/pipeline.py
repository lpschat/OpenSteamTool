"""Aggregate data fetching pipeline for the add-game workflow."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from opensteamtool_gui.models.game import Depot, Game, GameRepository
from opensteamtool_gui.services.fetcher.base import (
    DepotFetcher,
    DepotInfo,
    FetchedApp,
    FetchedGame,
    MetadataFetcher,
    TokenFetcher,
)
from opensteamtool_gui.utils.cache import JsonCache


@dataclass(frozen=True)
class FetchOptions:
    include_dlcs: bool = True
    include_depot_keys: bool = True
    include_manifest_gids: bool = True
    include_access_token: bool = True


class FetchPipeline:
    def __init__(
        self,
        metadata_fetchers: list[MetadataFetcher],
        depot_fetchers: list[DepotFetcher],
        token_fetchers: list[TokenFetcher],
    ) -> None:
        self.metadata_fetchers = metadata_fetchers
        self.depot_fetchers = depot_fetchers
        self.token_fetchers = token_fetchers

    async def fetch_game(self, appid: int, options: FetchOptions | None = None) -> FetchedGame:
        options = options or FetchOptions()
        game = await self._fetch_metadata(appid)
        if not options.include_dlcs:
            game.dlcs.clear()
        game.depots = await self._fetch_depots(appid, options)
        await self._fetch_dlc_depots(game, options)
        if options.include_access_token:
            game.access_token = await self._fetch_access_token(appid)
        game.incomplete = game.incomplete or _is_incomplete(game)
        return game

    async def fetch_many(
        self,
        appids: list[int],
        options: FetchOptions | None = None,
        *,
        concurrency: int = 5,
    ) -> list[FetchedGame]:
        semaphore = asyncio.Semaphore(concurrency)

        async def _one(appid: int) -> FetchedGame:
            async with semaphore:
                return await self.fetch_game(appid, options)

        return await asyncio.gather(*[_one(appid) for appid in appids])

    async def _fetch_metadata(self, appid: int) -> FetchedGame:
        warnings = []
        for fetcher in self.metadata_fetchers:
            try:
                return await fetcher.fetch_metadata(appid)
            except Exception as exc:
                warnings.append(f"{type(fetcher).__name__}: {exc}")
        return FetchedGame(appid=appid, incomplete=True, warnings=warnings)

    async def _fetch_depots(self, appid: int, options: FetchOptions) -> list[DepotInfo]:
        if not (options.include_depot_keys or options.include_manifest_gids):
            return []
        merged: dict[int, DepotInfo] = {}
        for fetcher in self.depot_fetchers:
            try:
                _merge_depots(merged, await fetcher.fetch_depots(appid))
            except Exception:
                continue
        return list(merged.values())

    async def _fetch_dlc_depots(self, game: FetchedGame, options: FetchOptions) -> None:
        for dlc in game.dlcs:
            depots = await self._fetch_depots(dlc.appid, options)
            game_depot = FetchedGame(dlc.appid, dlcs=[], depots=depots)
            dlc.depots = game_depot.depots  # type: ignore[attr-defined]

    async def _fetch_access_token(self, appid: int) -> str | None:
        for fetcher in self.token_fetchers:
            try:
                token = await fetcher.fetch_access_token(appid)
            except Exception:
                continue
            if token:
                return token
        return None


def save_to_repository(repo: GameRepository, fetched: FetchedGame) -> list[int]:
    repo.upsert_game(_to_game(fetched, parent_appid=None))
    saved = [fetched.appid]
    for dlc in fetched.dlcs:
        repo.upsert_game(_to_game(dlc, parent_appid=fetched.appid))
        saved.append(dlc.appid)
    return saved


def _merge_depots(target: dict[int, DepotInfo], incoming: list[DepotInfo]) -> None:
    for depot in incoming:
        current = target.get(depot.depot_id)
        if current is None:
            target[depot.depot_id] = depot
            continue
        current.decryption_key = current.decryption_key or depot.decryption_key
        current.manifest_gid = current.manifest_gid or depot.manifest_gid
        current.key_source = current.key_source or depot.key_source


def _to_game(app: FetchedApp, parent_appid: int | None) -> Game:
    depots = getattr(app, "depots", [])
    return Game(
        appid=app.appid,
        name=app.name,
        type=app.type,
        parent_appid=parent_appid,
        header_image=app.header_image,
        source=app.source or "Fetched",
        fetched_at=_now(),
        incomplete=getattr(app, "incomplete", False),
        depots=[
            Depot(d.depot_id, app.appid, d.decryption_key, d.manifest_gid, d.key_source)
            for d in depots
        ],
        access_token=getattr(app, "access_token", None),
    )


def _is_incomplete(game: FetchedGame) -> bool:
    return not game.name or any(d.decryption_key is None for d in game.depots)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_default_pipeline(client, cache_root: Path) -> FetchPipeline:
    from opensteamtool_gui.services.fetcher import (
        caigames,
        github_repos,
        steam_api,
        steamcmd,
        sudama,
    )

    cache = JsonCache(cache_root)
    return FetchPipeline(
        metadata_fetchers=[steam_api.SteamApiFetcher(client), caigames.CaiGamesFetcher(client)],
        depot_fetchers=[
            steamcmd.SteamCmdFetcher(client),
            github_repos.GitHubReposFetcher(client),
            sudama.SudamaFetcher(client, cache),
        ],
        token_fetchers=[sudama.SudamaFetcher(client, cache)],
    )
