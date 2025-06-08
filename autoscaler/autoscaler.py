import time
import logging
import os
import multiprocessing
import signal, sys, docker, json
import requests
from metrics import PrometheusClient, DockerManager, clear_prometheus_targets


class AutoScaler:
    def __init__(
        self,
        prom_url: str,
        docker_image: str,
        label: str = 'autoscale_service',
        cpu_threshold: float = 0.7,
        min_instances: int = 1,
        max_instances: int = 10,
        check_interval: int = 10,
        load_balancer_url: str = "http://host.docker.internal:8000"
    ):
        self.prom = PrometheusClient(prom_url)
        self.dock = DockerManager()
        self.image = docker_image
        self.label = label
        self.threshold = cpu_threshold
        self.min = min_instances
        self.max = max_instances
        self.interval = check_interval

        self.above_since = None
        self.below_since = None

        self.load_balancer_url = load_balancer_url
        
    def notify_load_balancer(self):
        """로드밸런서에 서버 목록 갱신 요청"""
        try:
            refresh_url = f"{self.load_balancer_url}/refresh-servers"
            
            response = requests.post(refresh_url, timeout=3)
            
            if response.status_code == 200:
                logging.info("✅ Load balancer server refresh triggered")
            else:
                logging.warning(f"⚠️ Load balancer refresh failed: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logging.warning("🔌 Could not connect to load balancer")
        except requests.exceptions.Timeout:
            logging.warning("⏰ Load balancer request timed out")
        except Exception as e:
            logging.error(f"❗ Error notifying load balancer: {e}")
            
    def scale(self) -> None:
        containers = self.dock.list_containers(self.label)
        autoscaled_containers = [c for c in containers if not self.dock._is_fixed(c)]
        count = len(containers)

        # under min instances
        if count < self.min:
            logging.info(f"Instances below minimum ({count} < {self.min}). Scaling up.")
            self.dock.run_container(self.image, self.label)
            #서버 갱신 요청
            self.notify_load_balancer()
            
            self.above_since = None
            self.below_since = None
            return
        
        num_cpus = multiprocessing.cpu_count()
        usages = [self.dock.get_container_cpu(c) for c in containers]
        raw_avg = sum(usages) / count if usages else 0.0
        avg_cpu = raw_avg / num_cpus

        logging.info(
            f"Avg CPU: {avg_cpu:.2f}% (per core) "
            f"across {count} containers"
        )

        now = time.time()

        if avg_cpu > (self.threshold*100):
            if self.above_since is None:
                self.above_since = now
                logging.debug("CPU above threshold, starting timer for scale-out.")
            elif now - self.above_since >= 30 and count < self.max:
                logging.info("CPU above threshold for ≥ 2 minutes. Scaling up by 1.")
                self.dock.run_container(self.image, self.label)
                
                # 서버 갱신 요청
                self.notify_load_balancer()
                
                self.above_since = None
                self.below_since = None
        else:
            self.above_since = None

        if avg_cpu < (self.threshold * 50):
            if self.below_since is None:
                self.below_since = now
                logging.debug("CPU below half-threshold, starting timer for scale-in.")
            elif now - self.below_since >= 15 and len(autoscaled_containers) > 0:
                target = autoscaled_containers[-1]
                logging.info(f"CPU below half-threshold for ≥ 1 minute. Scaling down container: {target.name}")
                self.dock.remove_container(target)
                
                 # 서버 갱신 요청
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
            except Exception as e:
                logging.error(f"Error during scaling: {e}")
            time.sleep(self.interval)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
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

    scaler = AutoScaler(
        prom_url,
        docker_img,
        min_instances=min_i,
        max_instances=max_i,
        cpu_threshold=cpu_th,
        check_interval=interval
    )
    scaler.run()
