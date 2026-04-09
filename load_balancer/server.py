from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse
from contextlib import asynccontextmanager
import httpx
import time
import logging
import asyncio
import balancer
from health_check import start_health_check, trigger_server_refresh, discover_containers

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 비동기 HTTP 클라이언트 (타임아웃을 10초로 연장)
client = httpx.AsyncClient(timeout=10.0, limits=httpx.Limits(max_connections=1000, max_keepalive_connections=100))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 실행될 로직"""
    logger.info("🚀 Starting Load Balancer (FastAPI)...")
    
    # 헬스 체크 루프 시작 (10초 주기로 기본 설정)
    health_task = start_health_check(interval=10)
    
    yield
    
    # 종료 시 클라이언트 닫기 및 헬스 체크 중지
    await client.aclose()
    health_task.cancel()
    logger.info("👋 Load Balancer shutting down...")

app = FastAPI(lifespan=lifespan, title="PNU Cloud Load Balancer (Async)")

EXCLUDED_HEADERS = {
    'host', 'content-length', 'connection', 'upgrade',
    'proxy-authenticate', 'proxy-authorization', 'te', 'trailers'
}

def filter_headers(headers):
    return {k: v for k, v in headers.items() if k.lower() not in EXCLUDED_HEADERS}

@app.get("/")
async def home():
    all_servers = await balancer.get_all_servers()
    return {
        "message": "PNU Cloud Computing Load Balancer (FastAPI/Async)",
        "total_backends": len(all_servers),
        "healthy_backends": len([s for s in all_servers if s['status'] == 'healthy']),
        "mode": balancer.selection_mode
    }

@app.api_route("/load", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_load(request: Request):
    """백엔드로 /load 요청을 비동기 프록시"""
    start_time = time.time()
    
    # 1. 백엔드 선택
    server = await balancer.choose_backend()
    if not server:
        logger.error("No healthy backend servers available")
        raise HTTPException(status_code=503, detail="No healthy servers")

    target_url = f"{server['host']}/load"
    
    # 2. 요청 전달 (최대 2번 재시도)
    for attempt in range(2):
        try:
            # 요청 바디 읽기
            body = await request.body()
            
            # 비동기 요청 전송
            resp = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=filter_headers(request.headers),
                params=request.query_params,
                timeout=10.0
            )
            
            duration = round(time.time() - start_time, 3)
            logger.info(f"Forwarded to {server['container_name']} - {resp.status_code} in {duration}s")
            
            # 응답 반환
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=filter_headers(resp.headers)
            )
            
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning(f"Backend {server['container_name']} failed (attempt {attempt+1}): {e}")
            # 다른 서버로 재시도
            server = await balancer.choose_backend()
            if not server: break
            target_url = f"{server['host']}/load"

    raise HTTPException(status_code=502, detail="All backend servers unavailable")

@app.post("/refresh-servers")
async def refresh_servers(background_tasks: BackgroundTasks):
    """오토스케일러로부터의 갱신 요청을 1순위로 즉시 처리"""
    logger.info("⚡ Priority Refresh Request received from Autoscaler")
    
    # 1. 즉시 헬스체크 이벤트 트리거
    trigger_server_refresh()
    
    # 2. 백그라운드에서 즉시 컨테이너 재탐색 시도 (더 빠른 반영)
    async def fast_refresh():
        servers = await discover_containers()
        # 일단 존재 여부만 확인해서 밸런서에 반영 (헬스체크는 루프에서 보완)
        if servers:
            for s in servers: s['status'] = 'healthy' # 새로 뜬 애들은 일단 시도해봄
            await balancer.update_backend_servers(servers)
            logger.info(f"✅ Fast refresh completed: {len(servers)} servers found")

    background_tasks.add_task(fast_refresh)
    return {"status": "success", "message": "Priority refresh triggered"}

@app.get("/status")
async def get_status():
    all_servers = await balancer.get_all_servers()
    return {
        "load_balancer": {
            "status": "healthy",
            "mode": balancer.selection_mode,
            "timestamp": time.time()
        },
        "backend_servers": {
            "total": len(all_servers),
            "healthy": len([s for s in all_servers if s['status'] == 'healthy']),
            "servers": all_servers
        }
    }

@app.get("/set_mode/{mode}")
async def set_mode(mode: str):
    valid_modes = ['round_robin', 'latency']
    if mode in valid_modes:
        balancer.selection_mode = mode
        return {"message": f"Mode set to {mode}"}
    raise HTTPException(status_code=400, detail="Invalid mode")

@app.get("/health")
async def health():
    return "OK"

@app.post("/cpu/toggle")
async def cpu_toggle_proxy():
    """백엔드의 /cpu/toggle 엔드포인트를 비동기로 프록시"""
    server = await balancer.choose_backend()
    if not server:
        raise HTTPException(status_code=503, detail="No healthy servers")
    
    try:
        target_url = f"{server['host']}/cpu/toggle"
        # POST 요청 전달
        resp = await client.post(target_url, timeout=5.0)
        return Response(content=resp.content, status_code=resp.status_code)
    except Exception as e:
        logger.error(f"Error forwarding /cpu/toggle: {e}")
        raise HTTPException(status_code=500, detail=f"Backend error: {str(e)}")

@app.get("/metrics")
async def metrics():
    """로드밸런서 및 백엔드 메트릭 통합 수집"""
    all_servers = await balancer.get_all_servers()
    healthy_servers = [s for s in all_servers if s['status'] == 'healthy']
    
    # 1. 로드밸런서 자체 메트릭
    lb_metrics = [
        f"backend_servers_total {len(all_servers)}",
        f"backend_servers_healthy {len(healthy_servers)}",
        f"load_balancer_uptime {time.time()}"
    ]
    
    # 2. 백엔드들로부터 메트릭 수집 (병렬 처리)
    backend_outputs = []
    async def fetch_backend_metrics(server):
        try:
            r = await client.get(f"{server['host']}/metrics", timeout=2.0)
            if r.status_code == 200:
                return f"\n# Backend: {server['container_name']}\n{r.text}"
        except:
            return ""
        return ""

    if healthy_servers:
        results = await asyncio.gather(*(fetch_backend_metrics(s) for s in healthy_servers))
        backend_outputs = [r for r in results if r]
    
    full_metrics = "\n".join(lb_metrics) + "\n" + "\n".join(backend_outputs)
    return PlainTextResponse(full_metrics)

if __name__ == "__main__":
    import uvicorn
    # 워커 수를 늘려 동시 처리 성능 극대화 (CPU 코어 수에 맞게 조절 가능)
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
