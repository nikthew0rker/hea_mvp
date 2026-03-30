import httpx


async def post_json(url: str, payload: dict) -> dict:
    """
    Lightweight async HTTP helper for internal agent-to-agent calls.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def get_json(url: str) -> dict:
    """
    Lightweight async GET helper for internal service reads.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
