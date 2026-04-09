import asyncio
import logging
import time

import httpx

from balancer import update_backend_servers
from config import DEFAULT_HEALTH_CHECK_INTERVAL
from discovery import discover_containers

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

immediate_check_event = asyncio.Event()
fail_counters = {}


async def check_single_server(client: httpx.AsyncClient, server):
    target_url = f"{server['host']}/health"
    server_id = server["host"]
    fail_counters.setdefault(server_id, 0)

    try:
        response = await client.get(target_url, timeout=5.0)
        if response.status_code == 200:
            server["status"] = "healthy"
            start_check = time.time()
            response = await client.get(target_url, timeout=5.0)
            if response.status_code == 200:
                server["status"] = "healthy"
                server["latency"] = round(time.time() - start_check, 3)
            fail_counters[server_id] = 0
        else:
            raise Exception(f"Status {response.status_code}")
    except Exception:
        fail_counters[server_id] += 1
        if fail_counters[server_id] < 3:
            server["status"] = "healthy"
            logger.warning(
                "%s slow/failed (%s/3). Keeping healthy.",
                server["container_name"],
                fail_counters[server_id],
            )
        else:
            server["status"] = "unhealthy"
            logger.error("%s marked UNHEALTHY after 3 failures.", server["container_name"])
        server["latency"] = float("inf")

    return server


async def health_check_loop(interval: int = DEFAULT_HEALTH_CHECK_INTERVAL):
    logger.info("Robust async health check loop started (interval: %ss)", interval)

    async with httpx.AsyncClient() as client:
        while True:
            try:
                servers = await discover_containers()
                if not servers:
                    await update_backend_servers([])
                else:
                    checked_servers = await asyncio.gather(
                        *(check_single_server(client, server) for server in servers)
                    )
                    await update_backend_servers(checked_servers)
            except Exception as error:
                logger.error("Error in health check loop: %s", error)

            try:
                await asyncio.wait_for(immediate_check_event.wait(), timeout=interval)
                immediate_check_event.clear()
            except asyncio.TimeoutError:
                pass


def trigger_server_refresh():
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(immediate_check_event.set)
    except RuntimeError:
        pass


def start_health_check(interval: int = DEFAULT_HEALTH_CHECK_INTERVAL):
    return asyncio.create_task(health_check_loop(interval))
