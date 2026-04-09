import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import Manager, Process

import requests

from config import (
    CPU_POOL_WORKERS,
    DEFAULT_LOAD_DURATION,
    INITIAL_RPS,
    LOAD_STEP_DURATION,
    MAX_RPS,
    REQUEST_TIMEOUT_SECONDS,
    RPS_INCREMENT,
    THREAD_POOL_WORKERS,
)


def cpu_stress_worker(duration: float):
    end = time.time() + duration
    while time.time() < end:
        _ = [i * i for i in range(1000)]
    return "done"


def send_requests(rps: int, duration_sec: int, url: str, stop_event) -> None:
    if not url:
        return

    interval = 1.0 / rps
    end_time = time.time() + duration_sec

    with ThreadPoolExecutor(max_workers=THREAD_POOL_WORKERS) as executor:
        while time.time() < end_time:
            if stop_event.is_set():
                break
            executor.submit(requests.post, url, timeout=REQUEST_TIMEOUT_SECONDS)
            time.sleep(interval)


def send_http_load_loop(stop_event, target_url: str) -> None:
    url = f"{target_url}?duration={DEFAULT_LOAD_DURATION}"
    rps = INITIAL_RPS

    print(f"Starting load generation loop (target: {url})")
    while not stop_event.is_set():
        print(f"Current load level: {rps} RPS")
        send_requests(rps, LOAD_STEP_DURATION, url, stop_event)
        if rps < MAX_RPS:
            rps += RPS_INCREMENT


class StressController:
    def __init__(self, target_url: str):
        self.target_url = target_url
        self.manager = Manager()
        self.stop_event = self.manager.Event()
        self.load_process = None
        self.cpu_executor = ProcessPoolExecutor(max_workers=CPU_POOL_WORKERS)

    def enqueue_cpu_load(self, duration: float) -> None:
        self.cpu_executor.submit(cpu_stress_worker, duration)

    def toggle(self) -> str:
        if self.load_process is None or not self.load_process.is_alive():
            print("Starting stress process")
            self.stop_event = self.manager.Event()
            self.load_process = Process(
                target=send_http_load_loop,
                args=(self.stop_event, self.target_url),
            )
            self.load_process.start()
            print(f"Stress process started with pid={self.load_process.pid}")
            return "started"

        print("Received request to stop stress process")
        self.stop_event.set()
        self.load_process.join(timeout=3)
        if self.load_process.is_alive():
            print("Stress process is still alive. Terminating it forcefully.")
            self.load_process.terminate()
            self.load_process.join()
        else:
            print("Stress process stopped cleanly.")
        self.load_process = None
        return "stopped"
