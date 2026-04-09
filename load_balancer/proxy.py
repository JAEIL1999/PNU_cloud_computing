from typing import Dict

import httpx
from fastapi import HTTPException, Request, Response

from config import CPU_TOGGLE_TIMEOUT_SECONDS, PROXY_TIMEOUT_SECONDS

EXCLUDED_HEADERS = {
    "host",
    "content-length",
    "connection",
    "upgrade",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
}


def filter_headers(headers):
    return {key: value for key, value in headers.items() if key.lower() not in EXCLUDED_HEADERS}


async def proxy_load_request(client: httpx.AsyncClient, request: Request, server: Dict) -> Response:
    body = await request.body()
    target_url = f"{server['host']}/load"
    response = await client.request(
        method=request.method,
        url=target_url,
        content=body,
        headers=filter_headers(request.headers),
        params=request.query_params,
        timeout=PROXY_TIMEOUT_SECONDS,
    )
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=filter_headers(response.headers),
    )


async def proxy_cpu_toggle_request(client: httpx.AsyncClient, server: Dict) -> Response:
    try:
        response = await client.post(
            f"{server['host']}/cpu/toggle",
            timeout=CPU_TOGGLE_TIMEOUT_SECONDS,
        )
        return Response(content=response.content, status_code=response.status_code)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Backend error: {error}") from error
