"""Tests for the M3 aggregate fetch pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from opensteamtool_gui.models.database import connect
from opensteamtool_gui.models.game import GameRepository
from opensteamtool_gui.services.fetcher.base import DepotInfo, FetchedApp, FetchedGame
from opensteamtool_gui.services.fetcher.pipeline import (
    FetchOptions,
    FetchPipeline,
    save_to_repository,
)


class MetadataSource:
    async def fetch_metadata(self, appid: int) -> FetchedGame:
        return FetchedGame(
            appid=appid,
            name="Counter-Strike 2",
            header_image="https://cdn.example/header.jpg",
            dlcs=[FetchedApp(appid=731, name="Prime Status", type="dlc")],
            source="Steam",
        )


class DepotSource:
    async def fetch_depots(self, appid: int) -> list[DepotInfo]:
        return [
            DepotInfo(
                depot_id=appid + 1000,
                owner_appid=appid,
                decryption_key="c" * 64,
                manifest_gid=str(appid * 10),
                key_source="test",
            )
        ]


class TokenSource:
    async def fetch_access_token(self, appid: int) -> str | None:
        return str(appid * 100)


@pytest.mark.asyncio
async def test_pipeline_merges_metadata_depots_tokens_and_dlcs() -> None:
    pipeline = FetchPipeline([MetadataSource()], [DepotSource()], [TokenSource()])

    result = await pipeline.fetch_game(730, FetchOptions(include_dlcs=True))

    assert result.name == "Counter-Strike 2"
    assert result.access_token == "73000"
    assert result.depots[0].depot_id == 1730
    assert result.dlcs[0].depots[0].owner_appid == 731


@pytest.mark.asyncio
async def test_pipeline_saves_fetched_game_to_repository(tmp_path: Path) -> None:
    conn = connect(tmp_path / "lib.db")
    repo = GameRepository(conn)
    pipeline = FetchPipeline([MetadataSource()], [DepotSource()], [TokenSource()])
    fetched = await pipeline.fetch_game(730, FetchOptions(include_dlcs=True))

    saved = save_to_repository(repo, fetched)

    assert saved == [730, 731]
    assert repo.get(730).name == "Counter-Strike 2"  # type: ignore[union-attr]
    assert repo.get(731).parent_appid == 730  # type: ignore[union-attr]
