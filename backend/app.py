from flask import Flask, Response, request
from flask_cors import CORS
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from prometheus_flask_exporter import PrometheusMetrics

from config import DEFAULT_LOAD_DURATION, TARGET_URL
from stress import StressController


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    PrometheusMetrics(app, group_by="endpoint")
    load_request_counter = Counter(
        "load_requests_total",
        "Total /load POST requests",
    )
    stress_controller = StressController(TARGET_URL)

    @app.route("/load", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def load_handler():
        load_request_counter.inc()
        duration = float(request.args.get("duration", str(DEFAULT_LOAD_DURATION)))
        stress_controller.enqueue_cpu_load(duration)
        return "ok"

    @app.route("/cpu/toggle", methods=["POST"])
    def cpu_toggle():
        return stress_controller.toggle()

    @app.route("/health", methods=["GET", "POST"])
    def health_check():
        return "OK", 200

    @app.route("/metrics")
    def metrics_handler():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.route("/")
    def home():
        return "hello, this is pnu cloud computing term project", 200

    return app


app = create_app()
