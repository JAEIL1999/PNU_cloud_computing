import time
import logging
import os
import multiprocessing
import signal
import sys
import docker
import json

from metrics import PrometheusClient, DockerManager, clear_prometheus_targets


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
        cpu_threshold: float = 0.5,
        min_instances: int = 0,
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
        autoscaled_containers = [c for c in containers if not self.dock._is_fixed(c)]
        count = len(containers)
        now = time.time()

        if count < self.min:
            logging.info(
                "Instances below minimum (%d < %d). Scaling up.",
                count, self.min
            )
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
            logging.error("Failed to fetch CPU metric from Prometheus: %s", e)
            return

        # If there are running containers, compute normalized average; otherwise treat as zero
        if count > 0:
            avg_cpu_fraction = raw_cpu_seconds_per_sec / (count * num_cpus)
            avg_cpu = avg_cpu_fraction * 100  # convert to percentage
        else:
            avg_cpu = 0.0

        logging.info(
            "Average CPU usage (Prometheus): %.2f%% across %d containers (normalized to single-core %%)",
            avg_cpu, count
        )

        now = time.time()

        # --- Scale-out logic: CPU > threshold for ≥ 3 minutes ---
        if avg_cpu > (self.threshold * 100):
            if self.above_since is None:
                self.above_since = now
                logging.debug("CPU above threshold, starting timer for scale-out.")
            elif now - self.above_since >= 3 * 60 and count < self.max:
                logging.info(
                    "CPU above threshold for ≥ 3 minutes. Scaling up by 1."
                )
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
        if avg_cpu < (self.threshold * 100) / 2:
            if self.below_since is None:
                self.below_since = now
                logging.debug("CPU below half-threshold, starting timer for scale-in.")
            elif now - self.below_since >= 1 * 60 and count > self.min:
                target = containers[-1]
                if not self.dock._is_fixed(target):
                    logging.info("CPU below half-threshold for ≥ 1 minute. Scaling down by 1.")
                    self.dock.remove_container(target)
                    self.last_scale_time = now
                    self.above_since = None
                    self.below_since = None
                    return
                else:
                    logging.info("Last container is fixed; cannot scale down that one.")
                    return
            elif now - self.below_since >= 15 and len(autoscaled_containers) > 0:
                target = autoscaled_containers[-1]
                logging.info(
                    "CPU below half-threshold for ≥ 15 seconds. Scaling down container: %s",
                    target.name
                )
                self.dock.remove_container(target)
                self.last_scale_time = now
                self.above_since = None
                self.below_since = None
                return
            elif now - self.below_since >= 30:
                logging.info("CPU below half-threshold, but no removable container found (all fixed).")
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
                logging.error("Error during scaling: %s", e)
            time.sleep(self.interval)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(Y-%m-%d %H:%M:%S [%(levelname)s] %(message)s'
    )
    clear_prometheus_targets()
    prom_url = os.getenv('PROM_URL', 'http://localhost:9090')
    docker_img = os.getenv('DOCKER_IMAGE', '')
    min_i = int(os.getenv('MIN_INSTANCES', 1))
    max_i = int(os.getenv('MAX_INSTANCES', 10))
    cpu_th = float(os.getenv('CPU_THRESHOLD', 0.7))
    interval = int(os.getenv('CHECK_INTERVAL', 30))

    def graceful_shutdown(signum, frame):
        print("📦 Shutting down autoscaler...")

        # 1. Docker에서 autoscale_service-* 컨테이너 삭제
        client = docker.from_env()
        for container in client.containers.list(all=True):
            if container.name.startswith("autoscale_service-"):
                print(f"🗑 Removing container {container.name}")
                try:
                    container.remove(force=True)
                except Exception as e:
                    print(f"❌ Failed to remove {container.name}: {e}")

        # 2. flask.json 초기화
        try:
            flask_json_path = "/app/prometheus/targets/flask.json"
            if os.path.exists(flask_json_path):
                with open(flask_json_path, "w") as f:
                    json.dump([], f)
                print("🧹 flask.json cleared")
        except Exception as e:
            print(f"❌ Failed to clear flask.json: {e}")

        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    scaler = AutoScaler(
        prom_url=prom_url,
        docker_image=docker_img,
        min_instances=min_i,
        max_instances=max_i,
        cpu_threshold=cpu_th,
        check_interval=interval
    )
    scaler.run()
