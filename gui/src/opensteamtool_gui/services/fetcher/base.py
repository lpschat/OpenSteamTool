"""Shared fetcher dataclasses and protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class DepotInfo:
    depot_id: int
    owner_appid: int
    decryption_key: str | None = None
    manifest_gid: str | None = None
    key_source: str | None = None


@dataclass
class FetchedApp:
    appid: int
    name: str = ""
    type: str = "game"
    header_image: str | None = None
    source: str | None = None


@dataclass
class FetchedGame(FetchedApp):
    dlcs: list[FetchedApp] = field(default_factory=list)
    depots: list[DepotInfo] = field(default_factory=list)
    access_token: str | None = None
    incomplete: bool = False
    warnings: list[str] = field(default_factory=list)


class MetadataFetcher(Protocol):
    async def fetch_metadata(self, appid: int) -> FetchedGame: ...


class DepotFetcher(Protocol):
    async def fetch_depots(self, appid: int) -> list[DepotInfo]: ...


class TokenFetcher(Protocol):
    async def fetch_access_token(self, appid: int) -> str | None: ...
