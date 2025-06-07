import docker
import time
import requests
import logging
from balancer import update_backend_servers

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_servers(label='image', network_name='pnu_cloud_computing_mynet'):
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
                try:
                    start = time.time()
                    resp = requests.get(server['host'] + '/health', timeout=2)
                    end = time.time()
                    if resp.status_code == 200:
                        server['status'] = 'healthy'
                        server['latency'] = end - start
                        healthy_servers.append(server)
                        logger.info(f"✅ {server['container_name']} - Healthy (latency: {server['latency']}s)")
                    else:
                        server['status'] = 'unhealthy'
                        server['latency'] = float('inf')
                        logger.warning(f"❌ {server['container_name']} - Unhealthy (status: {resp.status_code})")
                        
                except requests.exceptions.Timeout:
                    server['status'] = 'unhealthy'
                    server['latency'] = float('inf')
                    logger.error(f"⏰ {server['container_name']} - Timeout")
                    
                except requests.exceptions.ConnectionError:
                    server['status'] = 'unhealthy'
                    server['latency'] = float('inf')
                    logger.error(f"🔌 {server['container_name']} - Connection failed")

                except Exception as e:
                    server['status'] = 'unhealthy'
                    server['latency'] = float('inf')
                    logger.error(f"❗ {server['container_name']} - Health check failed: {e}")
            
            #Update Load_balancer        
            update_backend_servers(healthy_servers)
        
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
        
        time.sleep(300)

def start_health_check():
    """Health check를 별도 스레드에서 시작"""
    import threading
    logger.info("🚀 Starting health check service...")
    t = threading.Thread(target=check_servers, daemon=True)
    t.start()
    logger.info("✅ Health check service started")
    return t