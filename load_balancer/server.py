from flask import Flask, request, jsonify
from balancer import choose_backend, get_backend_servers
import requests
import logging
import time
from urllib.parse import urljoin

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 제외할 헤더들 (프록시 시 문제가 될 수 있는 헤더들)
EXCLUDED_HEADERS = {
    'host', 'content-length', 'connection', 'upgrade',
    'proxy-authenticate', 'proxy-authorization', 'te', 'trailers'
}

def filter_headers(headers):
    """프록시에 안전한 헤더만 필터링"""
    return {
        key: value for key, value in headers.items() 
        if key.lower() not in EXCLUDED_HEADERS
    }

def forward_request(target_url, method, data=None, headers=None, params=None, max_retries=2):
    """백엔드 서버로 요청을 전달하는 함수 - 백엔드 타임아웃에 맞춰 조정"""
    filtered_headers = filter_headers(headers or {})
    
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Forwarding {method} request to {target_url} (attempt {attempt + 1})")
            
            response = requests.request(
                method=method,
                url=target_url,
                data=data,
                headers=filtered_headers,
                params=params,
                timeout=3,  # 백엔드의 0.2초 타임아웃보다 여유있게 설정
                allow_redirects=False
            )
            
            logger.info(f"Backend responded with status {response.status_code}")
            return response
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1} to {target_url}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error on attempt {attempt + 1} to {target_url}")
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1} to {target_url}: {e}")
        
        if attempt < max_retries:
            time.sleep(0.1)  # 짧은 재시도 간격
    
    return None

@app.route('/load', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def route_request():
    """백엔드의 /load 엔드포인트와 호환되는 로드밸런싱"""
    start_time = time.time()
    
    # 요청 크기 제한 (5MB) - 백엔드 처리 능력 고려
    if request.content_length and request.content_length > 5 * 1024 * 1024:
        logger.warning(f"Request too large: {request.content_length} bytes")
        return "Request too large", 413
    
    # 백엔드 서버 선택
    server = choose_backend()
    if not server:
        logger.error("No healthy backend servers available")
        return "No healthy servers", 503
    
    target_url = f"{server['host']}/load"
    logger.info(f"Selected backend: {server.get('container_name', 'unknown')} ({server['host']})")
    
    # 최대 3번의 서버로 재시도 (백엔드가 빠르게 실패할 수 있으므로)
    for retry in range(5):
        response = forward_request(
            target_url=target_url,
            method=request.method,
            data=request.get_data(),
            headers=request.headers,
            params=request.args
        )
        
        if response is not None:
            # 응답 시간 로깅
            duration = round(time.time() - start_time, 3)
            logger.info(f"Request completed in {duration}s")
            
            # 백엔드가 단순 문자열 "ok"를 반환하므로 그대로 전달
            if response.headers.get('content-type'):
                response_headers = {k: v for k, v in response.headers.items() 
                                 if k.lower() not in EXCLUDED_HEADERS}
                return response.content, response.status_code, response_headers
            else:
                return response.content, response.status_code
        
        # 실패한 경우 다른 서버 선택
        if retry < 2:
            logger.warning(f"Backend {server['host']} failed, trying another server")
            server = choose_backend()
            if not server:
                break
            target_url = f"{server['host']}/load"
    
    logger.error("All backend servers failed to respond")
    return "All backend servers unavailable", 502

@app.route('/cpu/toggle', methods=['POST'])
def cpu_toggle_proxy():
    """백엔드의 /cpu/toggle 엔드포인트를 프록시"""
    server = choose_backend()
    if not server:
        return "No healthy servers", 503
    
    try:
        target_url = f"{server['host']}/cpu/toggle"
        response = requests.post(target_url, timeout=5)
        return response.content, response.status_code
    except Exception as e:
        logger.error(f"Error forwarding /cpu/toggle: {e}")
        return "Backend error", 500

@app.route('/set_mode/<mode>')
def set_mode(mode):
    """로드밸런싱 모드 변경"""
    import balancer
    
    valid_modes = ['round_robin', 'latency', 'least_connections', 'weighted']
    
    if mode in valid_modes:
        old_mode = getattr(balancer, 'selection_mode', 'unknown')
        balancer.selection_mode = mode
        logger.info(f"Load balancing mode changed: {old_mode} -> {mode}")
        return jsonify({
            "message": f"Selection mode set to {mode}",
            "previous_mode": old_mode,
            "available_modes": valid_modes
        }), 200
    else:
        logger.warning(f"Invalid mode requested: {mode}")
        return jsonify({
            "error": "Invalid mode",
            "available_modes": valid_modes
        }), 400

@app.route('/health')
def health():
    """로드밸런서 헬스체크"""
    return "OK", 200

@app.route('/status')
def status():
    """로드밸런서와 백엔드 서버들의 상태 조회"""
    try:
        import balancer
        servers = get_backend_servers()
        
        status_info = {
            "load_balancer": {
                "status": "healthy",
                "mode": getattr(balancer, 'selection_mode', 'round_robin'),
                "timestamp": time.time()
            },
            "backend_servers": {
                "total": len(servers),
                "healthy": len([s for s in servers if s.get('status') == 'healthy']),
                "servers": [
                    {
                        "host": s['host'],
                        "status": s.get('status', 'unknown'),
                        "latency": s.get('latency', 'unknown'),
                        "container_name": s.get('container_name', 'unknown')
                    }
                    for s in servers
                ]
            }
        }
        
        return jsonify(status_info), 200
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": "Failed to get status"}), 500

@app.route('/metrics')
def metrics():
    """기본적인 메트릭 정보"""
    try:
        servers = get_backend_servers()
        healthy_count = len([s for s in servers if s.get('status') == 'healthy'])
        
        # 백엔드 서버들의 /metrics 엔드포인트 수집
        backend_metrics = []
        for server in servers:
            if server.get('status') == 'healthy':
                try:
                    resp = requests.get(f"{server['host']}/metrics", timeout=2)
                    if resp.status_code == 200:
                        backend_metrics.append(f"# Backend: {server['host']}\n{resp.text}")
                except:
                    pass
        
        # 로드밸런서 자체 메트릭
        lb_metrics = f"""# HELP backend_servers_total Total number of backend servers
# TYPE backend_servers_total gauge
backend_servers_total {len(servers)}

# HELP backend_servers_healthy Number of healthy backend servers  
# TYPE backend_servers_healthy gauge
backend_servers_healthy {healthy_count}

# HELP load_balancer_uptime Load balancer uptime
# TYPE load_balancer_uptime gauge
load_balancer_uptime {time.time()}

"""
        
        # 모든 메트릭 결합
        all_metrics = lb_metrics + "\n".join(backend_metrics)
        
        return all_metrics, 200, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return "# Error generating metrics\n", 500, {'Content-Type': 'text/plain'}

@app.route('/favicon.ico')
def favicon():
    """파비콘 요청 처리"""
    return '', 204

@app.route('/')
def home():
    """로드밸런서 홈페이지 - 백엔드들을 프록시하지 않음"""
    try:
        servers = get_backend_servers()
        healthy_count = len([s for s in servers if s.get('status') == 'healthy'])
        
        return jsonify({
            "message": "PNU Cloud Computing Load Balancer",
            "total_backends": len(servers),
            "healthy_backends": healthy_count,
            "endpoints": {
                "load_balancing": "/load",
                "status": "/status", 
                "health": "/health",
                "metrics": "/metrics",
                "set_mode": "/set_mode/<mode>",
                "cpu_toggle": "/cpu/toggle"
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "message": "PNU Cloud Computing Load Balancer",
            "error": str(e)
        }), 200

@app.errorhandler(404)
def not_found(error):
    return "Endpoint not found", 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return "Internal server error", 500

if __name__ == '__main__':
    logger.info("🚀 Starting Load Balancer Server...")
    
    # Health check 시작
    from health_check import start_health_check
    start_health_check()
    logger.info("✅ Health check service started")
    
    # Flask 서버 시작
    logger.info("🌐 Load Balancer listening on http://0.0.0.0:8000")
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)