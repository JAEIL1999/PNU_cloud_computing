import os
from dataclasses import dataclass


@dataclass
class AutoScalerSettings:
    prom_url: str
    docker_image: str
    label: str
    cpu_threshold: float
    min_instances: int
    max_instances: int
    check_interval: int
    load_balancer_url: str


def load_settings() -> AutoScalerSettings:
    return AutoScalerSettings(
        prom_url=os.getenv("PROM_URL", "http://localhost:9090"),
        docker_image=os.getenv("DOCKER_IMAGE", ""),
        label=os.getenv("AUTOSCALE_LABEL", "autoscale_service"),
        cpu_threshold=float(os.getenv("CPU_THRESHOLD", 0.7)),
        min_instances=int(os.getenv("MIN_INSTANCES", 1)),
        max_instances=int(os.getenv("MAX_INSTANCES", 10)),
        check_interval=int(os.getenv("CHECK_INTERVAL", 30)),
        load_balancer_url=os.getenv(
            "LOAD_BALANCER_URL",
            "http://host.docker.internal:8000",
        ),
    )
