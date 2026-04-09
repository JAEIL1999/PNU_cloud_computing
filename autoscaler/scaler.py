import logging
import multiprocessing
import time

from docker_manager import DockerManager
from notifier import LoadBalancerNotifier
from prometheus_client import PrometheusClient


class AutoScaler:
    def __init__(
        self,
        prom_url: str,
        docker_image: str,
        label: str = "autoscale_service",
        cpu_threshold: float = 0.7,
        min_instances: int = 1,
        max_instances: int = 10,
        check_interval: int = 10,
        load_balancer_url: str = "http://host.docker.internal:8000",
    ):
        self.prom = PrometheusClient(prom_url)
        self.dock = DockerManager()
        self.notifier = LoadBalancerNotifier(load_balancer_url)
        self.image = docker_image
        self.label = label
        self.threshold = cpu_threshold
        self.min = min_instances
        self.max = max_instances
        self.interval = check_interval
        self.above_since = None
        self.below_since = None

    def notify_load_balancer(self) -> None:
        self.notifier.notify_refresh()

    def scale(self) -> None:
        containers = self.dock.list_containers(self.label)
        autoscaled_containers = [container for container in containers if not self.dock.is_fixed(container)]
        count = len(containers)

        if count < self.min:
            logging.info("Instances below minimum (%s < %s). Scaling up.", count, self.min)
            self.dock.run_container(self.image, self.label)
            self.notify_load_balancer()
            self.above_since = None
            self.below_since = None
            return

        num_cpus = multiprocessing.cpu_count()
        usages = [self.dock.get_container_cpu(container) for container in containers]
        raw_avg = sum(usages) / count if usages else 0.0
        avg_cpu = raw_avg

        logging.info("Avg CPU: %.2f%% (per core) across %s containers", avg_cpu, count)

        now = time.time()
        if avg_cpu > (self.threshold * 100):
            if self.above_since is None:
                self.above_since = now
                logging.debug("CPU above threshold, starting timer for scale-out.")
            elif now - self.above_since >= 30 and count < self.max:
                logging.info("CPU above threshold long enough. Scaling up by 1.")
                self.dock.run_container(self.image, self.label)
                self.notify_load_balancer()
                self.above_since = None
                self.below_since = None
        else:
            self.above_since = None

        if avg_cpu < (self.threshold * 50):
            if self.below_since is None:
                self.below_since = now
                logging.debug("CPU below half-threshold, starting timer for scale-in.")
            elif now - self.below_since >= 15 and autoscaled_containers:
                target = autoscaled_containers[-1]
                logging.info("CPU below half-threshold long enough. Scaling down container: %s", target.name)
                self.dock.remove_container(target)
                self.notify_load_balancer()
                self.above_since = None
                self.below_since = None
            elif now - self.below_since >= 30:
                logging.info("CPU below half-threshold, but no removable container found (all fixed).")
        else:
            self.below_since = None

    def run(self) -> None:
        logging.info("Starting AutoScaler loop.")
        while True:
            try:
                self.scale()
            except Exception as error:
                logging.error("Error during scaling: %s", error)
            time.sleep(self.interval)
