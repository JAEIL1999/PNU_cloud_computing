import asyncio
import time
from typing import Dict, List

import docker


async def discover_containers(network_name="pnu_cloud_computing_mynet") -> List[Dict]:
    loop = asyncio.get_event_loop()
    client = await loop.run_in_executor(None, docker.from_env)

    containers = await loop.run_in_executor(
        None,
        lambda: client.containers.list(
            filters={"status": "running", "label": "autoscale_service=backend"}
        ),
    )
    if not containers:
        containers = await loop.run_in_executor(
            None,
            lambda: client.containers.list(
                filters={"status": "running", "ancestor": "backend"}
            ),
        )

    servers = []
    for container in containers:
        try:
            network_settings = container.attrs["NetworkSettings"]["Networks"]
            if network_name in network_settings:
                ip = network_settings[network_name]["IPAddress"]
                if ip:
                    servers.append(
                        {
                            "container_id": container.id[:12],
                            "container_name": container.name,
                            "ip": ip,
                            "host": f"http://{ip}:5000",
                            "status": "unknown",
                            "latency": float("inf"),
                            "_start_time": time.time(),
                        }
                    )
        except Exception:
            continue

    return servers
