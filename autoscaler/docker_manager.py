import logging
import os
import time
import uuid

import docker

from targets import write_prometheus_targets


class DockerManager:
    def __init__(self):
        self.client = docker.from_env()

    def list_containers(self, label: str):
        containers = self.client.containers.list(filters={"label": label})
        for container in containers:
            logging.debug(
                "Container %s (%s) - fixed=%s",
                container.name,
                container.short_id,
                container.labels.get("fixed"),
            )
        return containers

    def run_container(self, image: str, label: str):
        project = os.getenv("COMPOSE_PROJECT_NAME", "pnu_cloud_computing")
        compose_labels = {
            "com.docker.compose.project": project,
            "com.docker.compose.service": label,
            "com.docker.compose.oneoff": "False",
            "autoscale_service": label,
        }
        labels = {"autoscale_service": label}
        existing = self.list_containers(label)
        if not any(self.is_fixed(container) for container in existing):
            labels["fixed"] = "true"

        container_name = f"{label}-{uuid.uuid4().hex[:5]}"
        container = self.client.containers.run(
            image,
            name=container_name,
            labels={**compose_labels, **labels},
            detach=True,
            ports={"5000/tcp": None},
            network="pnu_cloud_computing_mynet",
        )
        self.update_prometheus_targets(label)
        return container

    def remove_container(self, container):
        if self.is_fixed(container):
            logging.info("Skipping fixed container: %s (%s)", container.name, container.short_id)
            return

        logging.info("Removing container: %s (%s)", container.name, container.short_id)
        container.stop()
        container.remove()
        self.update_prometheus_targets(container.labels.get("autoscale_service"))

    def get_container_cpu(self, container):
        stats_stream = container.stats(stream=True, decode=True)
        first = next(stats_stream)
        time.sleep(1)
        second = next(stats_stream)
        del stats_stream

        cpu_delta = (
            second["cpu_stats"]["cpu_usage"]["total_usage"]
            - first["cpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            second["cpu_stats"]["system_cpu_usage"]
            - first["cpu_stats"]["system_cpu_usage"]
        )

        if system_delta > 0.0 and cpu_delta > 0.0:
            num_cpus = len(second["cpu_stats"]["cpu_usage"].get("percpu_usage", [])) or 1
            return (cpu_delta / system_delta) * num_cpus * 100.0
        return 0.0

    def update_prometheus_targets(self, label: str):
        containers = self.list_containers(label)
        targets = [f"{container.name}:5000" for container in containers if not self.is_fixed(container)]
        write_prometheus_targets(targets)

    def is_fixed(self, container) -> bool:
        return str(container.labels.get("fixed", "")).lower() == "true"
