import threading 
from typing import List, Dict, Optional

lock = threading.Lock()
backend_servers = []  # List to hold backend server instances 
current_index = 0  # Current index for round-robin balancing 
selection_mode = "round_robin"  # Default selection mode 

def update_backend_servers(new_list): 
    global backend_servers, current_index 
    backend_servers = new_list 
    if current_index >= len(backend_servers): 
        current_index = 0 
 
def choose_backend(): 
    global current_index 
    
    healthy_servers = [server for server in backend_servers if server['status'] == 'healthy']
    if not healthy_servers: 
        return None 
    if selection_mode == "round_robin": 
        if not healthy_servers: 
            return None
        server = healthy_servers[current_index % len(healthy_servers)]
        current_index = (current_index + 1) % len(healthy_servers)
        return server
    elif selection_mode == "latency":
        return min(healthy_servers, key=lambda s: s['latency'])
    else:
        raise ValueError(f"Unknown selection mode: {selection_mode}")
    
def get_backend_servers() -> List[Dict]:
    """
    현재 백엔드 서버 목록을 반환

    Returns:
        List[Dict]: 백엔드 서버 정보 리스트
    """
    with lock:
        return backend_servers.copy()