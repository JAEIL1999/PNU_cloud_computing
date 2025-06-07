from flask import Flask, request
from balancer import choose_backend
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/load', methods=['POST'])
def route_request():
    server = choose_backend()
    if not server:
        return "No healthy servers", 503
    try:
        resp = requests.post(f"{server['host']}/load", data=request.data, headers=request.headers)
        return resp.content, resp.status_code
    except Exception as e:
        print(f"Error forwarding to backend: {e}")
        return "Backend error", 500

@app.route('/set_mode/<mode>', methods=["GET"], strict_slashes=False)
def set_mode(mode):
    import balancer
    if mode in ['round_robin', 'latency']:
        balancer.selection_mode = mode
        return f"Selection mode set to {mode}", 200
    else:
        return "Invalid mode", 400

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    from health_check import start_health_check
    start_health_check()
    app.run(host='0.0.0.0', port=8080)