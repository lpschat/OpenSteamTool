"""HTTP client helpers shared by data fetchers."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


def create_async_client(
    *,
    strict_ssl: bool = False,
    proxy: str | None = None,
) -> httpx.AsyncClient:
    kwargs: dict[str, Any] = {
        "http2": True,
        "verify": strict_ssl,
        "trust_env": proxy is None,
        "timeout": httpx.Timeout(20.0),
        "follow_redirects": True,
    }
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


async def request_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    retries: int = 3,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                await asyncio.sleep(2**attempt)
    raise RuntimeError(f"HTTP request failed: {url}") from last_error


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
