import time
import logging
import os
import multiprocessing
from metrics import PrometheusClient, DockerManager

class AutoScaler:
    """
    scale-out only if CPU > threshold for ≥ 3 minutes
    scale-in only if CPU < threshold/2 for ≥ 1 minute
    """
    def __init__(
        self,
        prom_url: str,
        docker_image: str,
        label: str = 'autoscale_service',
        cpu_threshold: float = 0.7,
        min_instances: int = 1,
        max_instances: int = 10,
        check_interval: int = 30
    ):
        self.prom = PrometheusClient(prom_url)
        self.dock = DockerManager()
        self.image = docker_image
        self.label = label
        self.threshold = cpu_threshold
        self.min = min_instances
        self.max = max_instances
        self.interval = check_interval

        # Timestamps tracking when thresholds were first breached
        self.above_since = None   # for scale-out
        self.below_since = None   # for scale-in
        self.last_scale_time = None  # to skip one fetch cycle after scaling

    def scale(self) -> None:
        containers = self.dock.list_containers(self.label)
        count = len(containers)
        now = time.time()

        # Ensure minimum instances immediately
        if count < self.min:
            logging.info(f"Instances below minimum ({count} < {self.min}). Scaling up.")
            self.dock.run_container(self.image, self.label)
            self.above_since = None
            self.below_since = None
            self.last_scale_time = now
            return

        # If we just scaled, skip this cycle to allow Prometheus to collect new metrics
        if self.last_scale_time and (now - self.last_scale_time) < self.interval:
            logging.debug("Skipping Prometheus fetch due to recent scaling action.")
            return

        num_cpus = multiprocessing.cpu_count()

        # --- Fetch CPU usage from Prometheus ---
        try:
            promql = (
                'sum('
                'rate(container_cpu_usage_seconds_total{'
                'container_label_autoscale_service="'
                + self.label +
                '"}[1m])'
                ')'
            )
            raw_cpu_seconds_per_sec = self.prom.get_metric(promql)
        except Exception as e:
            logging.error(f"Failed to fetch CPU metric from Prometheus: {e}")
            return

        # If there are running containers, compute normalized average; otherwise treat as zero load
        if count > 0:
            avg_cpu_fraction = raw_cpu_seconds_per_sec / (count * num_cpus)
            avg_cpu = avg_cpu_fraction * 100  # convert to percentage
        else:
            avg_cpu = 0.0

        logging.info(
            f"Average CPU usage (Prometheus): {avg_cpu:.2f}% across {count} containers "
            f"(normalized to single-core %)"
        )

        # --- Scale-out logic: CPU > threshold for ≥ 3 minutes ---
        if avg_cpu > (self.threshold * 100):
            if self.above_since is None:
                self.above_since = now
                logging.debug("CPU above threshold, starting timer for scale-out.")
            elif now - self.above_since >= 3 * 60 and count < self.max:
                logging.info("CPU above threshold for ≥ 3 minutes. Scaling up by 1.")
                self.dock.run_container(self.image, self.label)
                self.last_scale_time = now
                self.above_since = None
                self.below_since = None
                return
        else:
            if self.above_since is not None:
                logging.debug("CPU dropped below threshold, resetting scale-out timer.")
            self.above_since = None

        # --- Scale-in logic: CPU < threshold/2 for ≥ 1 minute ---
        if avg_cpu < (self.threshold * 50):
            if self.below_since is None:
                self.below_since = now
                logging.debug("CPU below half-threshold, starting timer for scale-in.")
            elif now - self.below_since >= 1 * 60 and count > self.min:
                logging.info("CPU below half-threshold for ≥ 1 minute. Scaling down by 1.")
                to_remove = containers[-1]
                self.dock.remove_container(to_remove)
                self.last_scale_time = now
                self.above_since = None
                self.below_since = None
                return
        else:
            if self.below_since is not None:
                logging.debug("CPU rose above half-threshold, resetting scale-in timer.")
            self.below_since = None

    def run(self) -> None:
        logging.info("Starting AutoScaler loop.")
        while True:
            try:
                self.scale()
            except Exception as e:
                logging.error(f"Error during scaling: {e}")
            time.sleep(self.interval)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(Y-%m-%d %H:%M:%S [%(levelname)s] %(message)s'
    )
    prom_url = os.getenv('PROM_URL', 'http://localhost:9090')
    docker_img = os.getenv('DOCKER_IMAGE', '')
    min_i = int(os.getenv('MIN_INSTANCES', 1))
    max_i = int(os.getenv('MAX_INSTANCES', 10))
    cpu_th = float(os.getenv('CPU_THRESHOLD', 0.7))
    interval = int(os.getenv('CHECK_INTERVAL', 30))

    scaler = AutoScaler(
        prom_url=prom_url,
        docker_image=docker_img,
        min_instances=min_i,
        max_instances=max_i,
        cpu_threshold=cpu_th,
        check_interval=interval
    )
    scaler.run()
