import httpx


async def post_json(url: str, payload: dict) -> dict:
    """
    Send JSON to a service and return parsed JSON response.

    Raises httpx.HTTPError on transport or HTTP status failure.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
