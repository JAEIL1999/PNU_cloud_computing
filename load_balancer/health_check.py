import docker
import time
import requests
from balancer import update_backend_servers
from flask_cors import CORS

def check_servers(label='autoscale_service'):
    client = docker.from_env()
    
    while True:
        containers = client.containers.list(filters={"label": label, "status": "running"})
        servers = []
        for container in containers:
            ip = container.attrs['NetworkSettings']['IPAddress']
            servers.append({
                'host': f'http://{ip}:5000',
                'status': 'unknown',  # Assume unknown initially
                'latency': float('inf')  # Placeholder for latency
            })
        # 서버 상태 점검
        for server in servers:
            try:
                start = time.time()
                resp = requests.get(server['host'] + '/health', timeout=2)
                end = time.time()
                if resp.status_code == 200:
                    server['status'] = 'healthy'
                    server['latency'] = end - start
                else:
                    server['status'] = 'unhealthy'
            except Exception as e:
                print(f"[ERROR] Health check failed: {e}")
                server['status'] = 'unhealthy'
                server['latency'] = float('inf')
                
        update_backend_servers(servers)
        print(f"✅ Updated backend servers: {servers}")
        
        time.sleep(30)

def start_health_check():
    import threading
    t = threading.Thread(target=check_servers, daemon=True)
    t.start()