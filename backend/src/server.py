from flask import Flask, request, Response
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from multiprocessing import Process, Manager, cpu_count
import os
import time
import requests

app = Flask(__name__)
CORS(app)

metrics = PrometheusMetrics(app, group_by='endpoint')
load_request_counter = Counter("load_requests_total", "Total /load POST requests")

TARGET_URL = "http://host.docker.internal:8000/load"

# 전역 상태
manager = Manager()
stop_event = manager.Event()
load_process = None

# 실제 CPU 부하를 주는 작업
def cpu_stress_worker(duration, stop_event):
    end = time.time() + duration
    while time.time() < end:
        if stop_event.is_set():
            print("💤 부하 조기 종료")
            break
        for _ in range(10000):
            _ = sum(i * i for i in range(1000))

# 백엔드 서버에서 부하 처리
@app.route('/load', methods=['POST'])
def load_handler():
    load_request_counter.inc()
    duration = float(request.args.get("duration", "0.2"))
    num_cores = min(cpu_count(), 2)
    processes = []

    for _ in range(num_cores):
        p = Process(target=cpu_stress_worker, args=(duration, stop_event))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    return "ok"

# rps만큼 반복적으로 POST /load 호출
def _send_requests(rps, duration_sec, urls, stop_event):
    if not urls:
        return

    interval = 1.0 / rps
    end_time = time.time() + duration_sec
    i = 0

    while time.time() < end_time:
        if stop_event.is_set():
            print("요청 루프 중단됨")
            break

        url = urls[i % len(urls)]

        try:
            if stop_event.is_set():
                break
            response = requests.post(url, timeout=3.0)
            print(f"요청 성공: {response.status_code}")
        except Exception as e:
            print(f"요청 실패: {e}")
            if stop_event.is_set():
                break

        if stop_event.wait(timeout=interval):
            break

        i += 1

# 증가하는 RPS로 부하 주기 루프
def send_http_load_loop(stop_event):
    url = f"{TARGET_URL}?duration=0.2"
    step_duration = 2
    max_rps = 300
    rps = 50
    rps_increment = 50

    while not stop_event.is_set():
        _send_requests(rps, step_duration, [url], stop_event)
        rps = min(rps + rps_increment, max_rps)


@app.route('/cpu/toggle', methods=['POST'])
def cpu_toggle():
    global load_process, stop_event

    if load_process is None or not load_process.is_alive():
        print("📌 부하 시작")
        stop_event = manager.Event()
        load_process = Process(target=send_http_load_loop, args=(stop_event,))
        load_process.start()
        print(f"✅ 부하 프로세스 시작됨: pid={load_process.pid}")
        return "started"
    else:
        print("🛑 부하 중지 요청 받음")
        stop_event.set()
        load_process.join(timeout=3)
        if load_process.is_alive():
            print("⚠️ 프로세스가 살아있어서 강제 종료합니다.")
            load_process.terminate()
            load_process.join()
        else:
            print("✅ 프로세스 정상 종료됨.")
        load_process = None
        return "stopped"

@app.route('/health')
def health():
    """헬스체크"""
    return "OK", 200

@app.route('/metrics')
def metrics_handler():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# 기본 루트
@app.route('/')
def home():
    return "hello, this is pnu cloud computing term project", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
