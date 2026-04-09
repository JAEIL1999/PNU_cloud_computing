import asyncio
import time

from fastapi.responses import PlainTextResponse

from config import METRICS_TIMEOUT_SECONDS


async def build_metrics_response(client, healthy_servers, all_servers):
    lb_metrics = [
        f"backend_servers_total {len(all_servers)}",
        f"backend_servers_healthy {len(healthy_servers)}",
        f"load_balancer_uptime {time.time()}",
    ]

    async def fetch_backend_metrics(server):
        try:
            response = await client.get(
                f"{server['host']}/metrics",
                timeout=METRICS_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                return f"\n# Backend: {server['container_name']}\n{response.text}"
        except Exception:
            return ""
        return ""

    backend_outputs = []
    if healthy_servers:
        results = await asyncio.gather(*(fetch_backend_metrics(server) for server in healthy_servers))
        backend_outputs = [result for result in results if result]

    full_metrics = "\n".join(lb_metrics) + "\n" + "\n".join(backend_outputs)
    return PlainTextResponse(full_metrics)
