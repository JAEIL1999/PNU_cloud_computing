import signal
import sys

import docker
from targets import FLASK_TARGET_PATH, clear_prometheus_targets


def cleanup_autoscaled_containers():
    client = docker.from_env()
    for container in client.containers.list(all=True):
        if container.name.startswith("autoscale_service-"):
            print(f"Removing container {container.name}")
            try:
                container.remove(force=True)
            except Exception as error:
                print(f"Failed to remove {container.name}: {error}")


def clear_local_target_file():
    clear_prometheus_targets()
    print(f"Cleared target file: {FLASK_TARGET_PATH}")


def register_signal_handlers():
    def graceful_shutdown(signum, frame):
        print("Shutting down autoscaler...")
        cleanup_autoscaled_containers()
        try:
            clear_local_target_file()
        except Exception as error:
            print(f"Failed to clear flask.json: {error}")
        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
