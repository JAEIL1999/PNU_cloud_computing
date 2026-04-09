import docker
import asyncio
import httpx
import logging
import time
from typing import List, Dict
from balancer import update_backend_servers

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 상태 관리
immediate_check_event = asyncio.Event()
fail_counters = {} # 서버별 연속 실패 횟수 저장

async def check_single_server(client: httpx.AsyncClient, server: Dict) -> Dict:
    """개별 서버의 상태를 비동기로 체크 (Soft Failure 로직 도입)"""
    target_url = f"{server['host']}/health"
    server_id = server['host']
    
    # 실패 카운터 초기화
    if server_id not in fail_counters:
        fail_counters[server_id] = 0

    try:
        # 부하 상황을 고려하여 타임아웃을 5초로 연장
        response = await client.get(target_url, timeout=5.0)
        
        if response.status_code == 200:
            server['status'] = 'healthy'
            server['latency'] = round(time.time() - server.get('_start_time', time.time()), 3)
            fail_counters[server_id] = 0 # 성공 시 카운터 리셋
        else:
            raise Exception(f"Status {response.status_code}")
            
    except Exception as e:
        fail_counters[server_id] += 1
        # 3회 연속 실패 전까지는 'healthy' 상태 유지 (단, 레이턴시는 무한대)
        if fail_counters[server_id] < 3:
            server['status'] = 'healthy'
            logger.warning(f"⚠️ {server['container_name']} slow/failed ({fail_counters[server_id]}/3). Keeping healthy.")
        else:
            server['status'] = 'unhealthy'
            logger.error(f"❌ {server['container_name']} marked UNHEALTHY after 3 failures.")
        
        server['latency'] = float('inf')
        
    return server

async def discover_containers(network_name='pnu_cloud_computing_mynet') -> List[Dict]:
    """Docker API를 사용하여 백엔드 컨테이너 탐색"""
    loop = asyncio.get_event_loop()
    client = await loop.run_in_executor(None, docker.from_env)
    
    servers = []
    containers = await loop.run_in_executor(None, 
        lambda: client.containers.list(filters={"status": "running", "label": "autoscale_service=backend"})
    )
    
    if not containers:
        containers = await loop.run_in_executor(None,
            lambda: client.containers.list(filters={"status": "running", "ancestor": "backend"})
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
                        'status': 'unknown',
                        'latency': float('inf'),
                        '_start_time': time.time()
                    })
        except Exception:
            continue
            
    return servers

async def health_check_loop(interval: int = 10):
    """주기적인 비동기 헬스 체크 루프"""
    logger.info(f"🚀 Robust Async Health Check Loop started (interval: {interval}s)")
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                servers = await discover_containers()
                
                if not servers:
                    await update_backend_servers([])
                else:
                    tasks = [check_single_server(client, server) for server in servers]
                    checked_servers = await asyncio.gather(*tasks)
                    await update_backend_servers(checked_servers)
                    
                    healthy_count = len([s for s in checked_servers if s['status'] == 'healthy'])
                    # logger.info(f"📊 Health Summary: {healthy_count}/{len(checked_servers)} healthy")

            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

            try:
                await asyncio.wait_for(immediate_check_event.wait(), timeout=interval)
                immediate_check_event.clear()
            except asyncio.TimeoutError:
                pass

def trigger_server_refresh():
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(immediate_check_event.set)
    except RuntimeError:
        pass

def start_health_check(interval: int = 10):
    return asyncio.create_task(health_check_loop(interval))
