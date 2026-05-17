"""China network detection used for GitHub mirror preference."""

from __future__ import annotations

import httpx

CN_CHECK_URL = "https://mips.kugou.com/check/iscn?&format=json"


async def is_cn(client: httpx.AsyncClient) -> bool:
    try:
        response = await client.get(CN_CHECK_URL, timeout=5.0)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return False
    value = payload.get("flag", payload.get("is_cn", payload.get("isCN")))
    return bool(value)
