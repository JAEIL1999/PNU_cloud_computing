import logging

from cleanup import register_signal_handlers
from config import load_settings
from scaler import AutoScaler
from targets import clear_prometheus_targets


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    register_signal_handlers()
    clear_prometheus_targets()

    settings = load_settings()
    scaler = AutoScaler(
        prom_url=settings.prom_url,
        docker_image=settings.docker_image,
        label=settings.label,
        min_instances=settings.min_instances,
        max_instances=settings.max_instances,
        cpu_threshold=settings.cpu_threshold,
        check_interval=settings.check_interval,
        load_balancer_url=settings.load_balancer_url,
    )
    scaler.run()


if __name__ == "__main__":
    main()
