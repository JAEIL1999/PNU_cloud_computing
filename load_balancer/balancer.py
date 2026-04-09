import asyncio
from typing import List, Dict

# 비동기 환경을 위한 락
lock = asyncio.Lock()
backend_servers: List[Dict] = []  # 백엔드 서버 인스턴스 리스트
current_index = 0  # 라운드 로빈용 인덱스
selection_mode = "round_robin"  # 기본 선택 모드

async def update_backend_servers(new_list: List[Dict]): 
    """서버 목록 갱신 (비동기)"""
    global backend_servers, current_index 
    async with lock:
        backend_servers = new_list 
        # 인덱스 범위 초과 방지
        if current_index >= len(backend_servers): 
            current_index = 0 
        print(f"DEBUG: Balancer updated with {len(backend_servers)} servers")

async def choose_backend() -> Dict: 
    """현재 모드에 맞는 백엔드 서버 선택 (비동기)"""
    global current_index 
    
    async with lock:
        healthy_servers = [server for server in backend_servers if server.get('status') == 'healthy']
        
        if not healthy_servers: 
            return None 
            
        if selection_mode == "round_robin": 
            server = healthy_servers[current_index % len(healthy_servers)]
            current_index = (current_index + 1) % len(healthy_servers)
            return server
            
        elif selection_mode == "latency":
            # 레이턴시가 가장 낮은 서버 선택 (inf 제외)
            return min(healthy_servers, key=lambda s: s.get('latency', float('inf')))
            
        else:
            raise ValueError(f"Unknown selection mode: {selection_mode}")
    
async def get_all_servers() -> List[Dict]:
    """현재 모든 서버 상태 반환"""
    async with lock:
        return list(backend_servers)
