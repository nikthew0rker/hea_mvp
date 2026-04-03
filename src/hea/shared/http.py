from __future__ import annotations

from typing import Any

import httpx

from hea.shared.config import get_settings

async def post_json(url: str, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    timeout = timeout if timeout is not None else get_settings().controller_request_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"raw": data}


async def get_bytes(url: str, timeout: float | None = None) -> tuple[bytes, str]:
    timeout = timeout if timeout is not None else get_settings().controller_request_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content, str(response.headers.get("content-type") or "")
