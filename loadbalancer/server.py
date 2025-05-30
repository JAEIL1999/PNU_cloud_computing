from flask import Flask, request, jsonify
import requests
from balancer import RoundRobinBalancer

app = Flask(__name__)

# 백엔드 서버 리스트
backend_servers = [
    "http://127.0.0.1:5001",
    "http://127.0.0.1:5002",
    "http://127.0.0.1:5003"
]

balancer = RoundRobinBalancer(backend_servers)

@app.route('/', methods=['GET', 'POST'])
def load_balance():
    target = balancer.get_next_server()
    try:
        # 요청 전달
        resp = requests.request(
            method=request.method,
            url=f"{target}{request.full_path}",
            headers=request.headers,
            data=request.get_data(),
            allow_redirects=False
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 502

if __name__ == '__main__':
    app.run(port=8080)
