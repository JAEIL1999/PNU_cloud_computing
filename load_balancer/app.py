import time
from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

import balancer
from config import (
    APP_TITLE,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    MAX_CONNECTIONS,
    MAX_KEEPALIVE_CONNECTIONS,
)
from discovery import discover_containers
from health_check import logger, start_health_check, trigger_server_refresh
from metrics import build_metrics_response
from proxy import proxy_cpu_toggle_request, proxy_load_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting load balancer (FastAPI)...")
    app.state.http_client = httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
        ),
    )
    health_task = start_health_check(interval=DEFAULT_HEALTH_CHECK_INTERVAL)
    yield
    await app.state.http_client.aclose()
    health_task.cancel()
    logger.info("Load balancer shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title=APP_TITLE)

    @app.get("/")
    async def home():
        all_servers = await balancer.get_all_servers()
        return {
            "message": APP_TITLE,
            "total_backends": len(all_servers),
            "healthy_backends": len([server for server in all_servers if server["status"] == "healthy"]),
            "mode": balancer.selection_mode,
        }

    @app.api_route("/load", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def route_load(request: Request):
        start_time = time.time()
        server = await balancer.choose_backend()
        if not server:
            logger.error("No healthy backend servers available")
            raise HTTPException(status_code=503, detail="No healthy servers")

        client = request.app.state.http_client
        for attempt in range(2):
            try:
                response = await proxy_load_request(client, request, server)
                duration = round(time.time() - start_time, 3)
                logger.info(
                    "Forwarded to %s - %s in %ss",
                    server["container_name"],
                    response.status_code,
                    duration,
                )
                return response
            except (httpx.RequestError, httpx.TimeoutException) as error:
                logger.warning(
                    "Backend %s failed (attempt %s): %s",
                    server["container_name"],
                    attempt + 1,
                    error,
                )
                server = await balancer.choose_backend()
                if not server:
                    break

        raise HTTPException(status_code=502, detail="All backend servers unavailable")

    @app.post("/refresh-servers")
    async def refresh_servers(background_tasks: BackgroundTasks):
        logger.info("Priority refresh request received from autoscaler")
        trigger_server_refresh()

        async def fast_refresh():
            servers = await discover_containers()
            if servers:
                for server in servers:
                    server["status"] = "healthy"
                await balancer.update_backend_servers(servers)
                logger.info("Fast refresh completed: %s servers found", len(servers))

        background_tasks.add_task(fast_refresh)
        return {"status": "success", "message": "Priority refresh triggered"}

    @app.get("/status")
    async def get_status():
        all_servers = await balancer.get_all_servers()
        return {
            "load_balancer": {
                "status": "healthy",
                "mode": balancer.selection_mode,
                "timestamp": time.time(),
            },
            "backend_servers": {
                "total": len(all_servers),
                "healthy": len([server for server in all_servers if server["status"] == "healthy"]),
                "servers": all_servers,
            },
        }

    @app.get("/set_mode/{mode}")
    async def set_mode(mode: str):
        valid_modes = ["round_robin", "latency"]
        if mode in valid_modes:
            balancer.selection_mode = mode
            return {"message": f"Mode set to {mode}"}
        raise HTTPException(status_code=400, detail="Invalid mode")

    @app.get("/health")
    async def health():
        return "OK"

    @app.post("/cpu/toggle")
    async def cpu_toggle_proxy(request: Request):
        server = await balancer.choose_backend()
        if not server:
            raise HTTPException(status_code=503, detail="No healthy servers")

        logger.info("Forwarding /cpu/toggle to %s", server["container_name"])
        return await proxy_cpu_toggle_request(request.app.state.http_client, server)

    @app.get("/metrics")
    async def metrics(request: Request):
        all_servers = await balancer.get_all_servers()
        healthy_servers = [server for server in all_servers if server["status"] == "healthy"]
        return await build_metrics_response(
            request.app.state.http_client,
            healthy_servers,
            all_servers,
        )

    return app


app = create_app()
