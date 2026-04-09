from flask import Flask, request, Response
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from multiprocessing import Process, Manager, cpu_count
import multiprocessing
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import requests


app = Flask(__name__)
health_app = Flask(__name__)
CORS(app)

metrics = PrometheusMetrics(app, group_by='endpoint')
load_request_counter = Counter("load_requests_total", "Total /load POST requests")

TARGET_URL = "http://load_balancer:8000/load"

# 전역 상태
manager = Manager()
stop_event = manager.Event()
load_process = None

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

# 전역 프로세스 풀 (부하 연산용)
cpu_executor = ProcessPoolExecutor(max_workers=4)

# 실제 CPU 부하를 주는 작업 (휴식 제거)
def cpu_stress_worker(duration):
    # stop_event 제거 (Pool에서 실행하기 위해 단순화)
    end = time.time() + duration
    while time.time() < end:
        # 타이트한 루프 연산
        _ = [i * i for i in range(1000)]
    return "done"

# 백엔드 서버에서 부하 처리
@app.route('/load', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def load_handler():
    load_request_counter.inc()
    duration = float(request.args.get("duration", "0.5"))
    
    # 프로세스 풀에 부하 작업 던지기 (비차단)
    # 헬스체크 응답을 방해하지 않기 위해 메인 스레드는 즉시 반환하거나 짧게만 대기
    cpu_executor.submit(cpu_stress_worker, duration)
    
    return "ok"

# rps만큼 병렬로 POST /load 호출
def _send_requests(rps, duration_sec, url, stop_event):
    if not url:
        return

    interval = 1.0 / rps
    end_time = time.time() + duration_sec
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        while time.time() < end_time:
            if stop_event.is_set():
                break
            # 비동기적으로 요청 발사
            executor.submit(requests.post, url, timeout=5.0)
            time.sleep(interval)

# 증가하는 RPS로 부하 주기 루프
def send_http_load_loop(stop_event):
    url = f"{TARGET_URL}?duration=0.5"
    step_duration = 5
    max_rps = 150
    rps = 20
    rps_increment = 20

    print(f"🚀 부하 생성 루프 시작 (Target: {url})")
    while not stop_event.is_set():
        print(f"🔥 현재 부하 강도: {rps} RPS")
        _send_requests(rps, step_duration, url, stop_event)
        if rps < max_rps:
            rps += rps_increment


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


@app.route('/health', methods=['GET','POST'])
def health_check():
    return "OK", 200

@app.route('/metrics')
def metrics_handler():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# 기본 루트
@app.route('/')
def home():
    return "hello, this is pnu cloud computing term project", 200

if __name__ == '__main__':
    # health_process = multiprocessing.Process(target=run_health_process, daemon=True)
    # health_process.start()
    
    app.run(host='0.0.0.0', port=5000, threaded=True)
