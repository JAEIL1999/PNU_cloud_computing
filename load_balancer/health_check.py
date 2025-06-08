import docker
import time
import requests
import threading 
import logging
from balancer import update_backend_servers
from flask_cors import CORS
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

server_last_success = defaultdict(float)

immediate_check_event = threading.Event()

def check_servers(network_name='pnu_cloud_computing_mynet'):
    client = docker.from_env()
    
    while True:
        servers = []
        try:
            containers = client.containers.list(
                filters={
                    "status": "running",
                    "ancestor": "backend"  # autoscale_service=backend 라벨
                }
            )

            for container in containers:
                try:
                    network_settings = container.attrs['NetworkSettings']['Networks']
                    if network_name in network_settings:
                        ip = network_settings[network_name]['IPAddress']
                        if ip:
                            servers.append({
                                'container_id': container.id[:12],
                                'container_name': container.name,
                                'ip': ip,
                                'host': f'http://{ip}:5000',
                                'status': 'unknown',  # Assume unknown initially
                                'latency': float('inf')  # Placeholder for latency
                            })
                            logger.info(f"Found backend : ({ip})")
                        else:
                            logger.warning(f"has no IP address")
                    else:
                        logger.warning(f"not in network {network_name}")
                except KeyError as e:
                    logger.error(f"Error accessing network info: {e}")
                    continue
            
            if not servers:
                logger.warning("No backend servers found!")
                time.sleep(30)
                continue
            
            # 서버 상태 점검
            healthy_servers = []
        
            for server in servers:
                server_id = server['host']
                ip = server['ip']
                target_url = f"{server['host']}/health"
                try:
                    start = time.time()
                    resp = requests.get(target_url, timeout=15)
                    end = time.time()
                    if resp.status_code == 200:
                        server['status'] = 'healthy'
                        server['latency'] = round(end - start, 3)
                        server_last_success[server_id] = time.time()
                        healthy_servers.append(server)
                        logger.info(f"✅ {server['container_name']} - Healthy (latency: {server['latency']}s)")
                    else:
                        server['status'] = 'healthy'
                        server['latency'] = float('inf')
                        healthy_servers.append(server)
                        logger.warning(f"❌ {server['container_name']} - Unhealthy (status: {resp.status_code})")
                        
                except requests.exceptions.Timeout:
                    server['status'] = 'healthy'
                    server['latency'] = float('inf')
                    healthy_servers.append(server)
                    logger.error(f"⏰ {server['container_name']} - Timeout")
                    
                except requests.exceptions.ConnectionError:
                    server['status'] = 'healthy'
                    server['latency'] = float('inf')
                    healthy_servers.append(server)
                    logger.error(f"🔌 {server['container_name']} - Connection failed")

                except Exception as e:
                    server['status'] = 'healthy'
                    server['latency'] = float('inf')
                    healthy_servers.append(server)
                    logger.error(f"❗ {server['container_name']} - Health check failed: {e}")
        
            last_success = server_last_success.get(server_id, 0)
            grace_period = 600  # 10분 grace period
            if time.time() - last_success < grace_period and server['status'] == 'unhealthy':
                server['status'] = 'healthy'  # 최근에 성공했으면 healthy로 처리
                server['latency'] = float('inf')  # degraded 상태는 latency를 무한대로 설정
                logger.warning(f"⚠️ {server.get('container_name', server_id)} - Failed but keeping as degraded (recent success)")
                healthy_servers.append(server)
            #Update Load_balancer        
            update_backend_servers(servers)
        
            total_servers = len(servers)
            healthy_count = len(healthy_servers)
            logger.info(f"📊 Health Check Summary: {healthy_count}/{total_servers} servers healthy")
            
            if healthy_count == 0:
                logger.critical("🚨 All backend servers are unhealthy!")
            elif healthy_count < total_servers:
                logger.warning(f"⚠️ {total_servers - healthy_count} servers are unhealthy")
            
        except docker.errors.DockerException as e:
            logger.error(f"Docker API error: {e}")
            update_backend_servers(servers)
        except Exception as e:
            logger.error(f"Unexpected error in health check: {e}")
            update_backend_servers(servers)
            
        print(f"✅ Updated backend servers: {servers}")
        
        if immediate_check_event.wait(timeout=300):
            immediate_check_event.clear()  # 신호 끄기
            logger.info("⚡ 즉시 체크 요청 받음!")
            # 다시 루프 시작 (서버 재체크)
        else:
            logger.info("⏰ 5분 경과, 정상 체크")

def trigger_server_refresh():
    immediate_check_event.set()  # 신호 보내기!
    
def start_health_check():
    """Health check를 별도 스레드에서 시작"""
    import threading
    logger.info("🚀 Starting health check service...")
    t = threading.Thread(target=check_servers, daemon=True)
    t.start()
    logger.info("✅ Health check service started")
    return t