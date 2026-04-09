import json
import os

FLASK_TARGET_PATH = "/etc/prometheus/targets/flask.json"


def write_prometheus_targets(targets):
    os.makedirs(os.path.dirname(FLASK_TARGET_PATH), exist_ok=True)
    with open(FLASK_TARGET_PATH, "w") as file:
        json.dump([{"targets": targets, "labels": {"job": "flask-autoscaled"}}], file)


def clear_prometheus_targets():
    write_prometheus_targets([])
