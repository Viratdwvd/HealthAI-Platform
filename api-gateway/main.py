"""
API Gateway – single entry-point for all client traffic.
Responsibilities: JWT auth, rate limiting, request routing to microservices.
"""

from __future__ import annotations
import asyncio
import time
import sys
import os

sys.path.insert(0, "/app/shared")

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import APIGatewaySettings
from middleware.auth import get_current_user, TokenData
from middleware.rate_limit import RateLimiter
from models.schemas import HealthResponse, QueryRequest, IngestionRequest
from routes.knowledge import router as knowledge_router

settings = APIGatewaySettings()

app = FastAPI(
    title="Healthcare Intelligence Platform – API Gateway",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Prometheus ───────────────────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app)

# Register sub-routers
app.include_router(knowledge_router, prefix="/api/v1")

# ─── HTTP client pool ─────────────────────────────────────────────────────────
_http: httpx.AsyncClient | None = None

async def get_http() -> httpx.AsyncClient:
    return _http  # type: ignore

@app.on_event("startup")
async def startup() -> None:
    global _http
    _http = httpx.AsyncClient(timeout=settings.__dict__.get("AGENT_TIMEOUT_S", 30))

@app.on_event("shutdown")
async def shutdown() -> None:
    if _http:
        await _http.aclose()


# ─── Rate limiter ─────────────────────────────────────────────────────────────
rate_limiter = RateLimiter(
    redis_url=settings.REDIS_URL,
    max_per_minute=settings.RATE_LIMIT_PER_MIN,
)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await rate_limiter.check(client_ip)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


# ─── Helpers ──────────────────────────────────────────────────────────────────

SERVICE_URLS = {
    "ingestion":  "http://ingestion-service:8001",
    "rag":        "http://rag-service:8002",
    "analytics":  "http://analytics-service:8003",
    "knowledge":  "http://knowledge-service:8004",
    "agent":      "http://agent-orchestrator:8005",
    "llm":        "http://llm-service:8006",
    "session":    "http://session-service:8007",
}

async def proxy(
    http:    httpx.AsyncClient,
    service: str,
    path:    str,
    method:  str = "POST",
    json:    dict | None = None,
    params:  dict | None = None,
) -> dict:
    url = f"{SERVICE_URLS[service]}{path}"
    try:
        resp = await http.request(method, url, json=json, params=params)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Service {service} unavailable: {exc}")


# ─── Auth endpoints ───────────────────────────────────────────────────────────

from middleware.auth import create_access_token
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: str

@app.post("/auth/token", tags=["auth"])
async def login(req: LoginRequest):
    token = create_access_token(
        {"sub": req.username, "tenant_id": req.tenant_id},
        settings.SECRET_KEY,
        settings.ACCESS_TOKEN_EXPIRE,
    )
    return {"access_token": token, "token_type": "bearer"}


# ─── Ingestion ────────────────────────────────────────────────────────────────

@app.post("/api/v1/ingest", tags=["ingestion"])
async def ingest(
    req:  IngestionRequest,
    user: TokenData = Depends(get_current_user),
    http: httpx.AsyncClient = Depends(get_http),
):
    req.tenant_id = user.tenant_id
    req.user_id   = user.username
    return await proxy(http, "ingestion", "/ingest", json=req.model_dump())

@app.get("/api/v1/ingest/{job_id}", tags=["ingestion"])
async def ingest_status(
    job_id: str,
    user:   TokenData = Depends(get_current_user),
    http:   httpx.AsyncClient = Depends(get_http),
):
    return await proxy(http, "ingestion", f"/ingest/{job_id}", method="GET")


# ─── Query / Agent ────────────────────────────────────────────────────────────

@app.post("/api/v1/query", tags=["query"])
async def query(
    req:  QueryRequest,
    user: TokenData = Depends(get_current_user),
    http: httpx.AsyncClient = Depends(get_http),
):
    req.tenant_id = user.tenant_id
    req.user_id   = user.username
    return await proxy(http, "agent", "/orchestrate", json=req.model_dump())


# ─── Analytics ────────────────────────────────────────────────────────────────

from models.schemas import AnalyticsRequest

@app.post("/api/v1/analytics", tags=["analytics"])
async def analytics(
    req:  AnalyticsRequest,
    user: TokenData = Depends(get_current_user),
    http: httpx.AsyncClient = Depends(get_http),
):
    req.tenant_id = user.tenant_id
    return await proxy(http, "analytics", "/analyze", json=req.model_dump())


# ─── Session ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/sessions/{session_id}", tags=["session"])
async def get_session(
    session_id: str,
    user:       TokenData = Depends(get_current_user),
    http:       httpx.AsyncClient = Depends(get_http),
):
    return await proxy(http, "session", f"/sessions/{session_id}", method="GET")

@app.delete("/api/v1/sessions/{session_id}", tags=["session"])
async def delete_session(
    session_id: str,
    user:       TokenData = Depends(get_current_user),
    http:       httpx.AsyncClient = Depends(get_http),
):
    return await proxy(http, "session", f"/sessions/{session_id}", method="DELETE")


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health(http: httpx.AsyncClient = Depends(get_http)):
    service_health: dict = {}
    checks = [
        asyncio.create_task(_ping(http, svc, url))
        for svc, url in SERVICE_URLS.items()
    ]
    results = await asyncio.gather(*checks, return_exceptions=True)
    for (svc, _), result in zip(SERVICE_URLS.items(), results):
        service_health[svc] = "ok" if result is True else "degraded"
    return HealthResponse(service="api-gateway", details=service_health)

async def _ping(http: httpx.AsyncClient, svc: str, base: str) -> bool:
    try:
        r = await http.get(f"{base}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False
