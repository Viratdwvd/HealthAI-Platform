"""
LLM Service – FREE LOCAL VERSION
----------------------------------
Uses Ollama (runs models on YOUR machine, 100% free, no API key needed).

Primary model:  llama3.2 (3B – fast on any laptop)
Fallback model: mistral  (7B – better quality, needs ~8GB RAM)

Install Ollama: https://ollama.com
Then run:  ollama pull llama3.2
"""

from __future__ import annotations
import hashlib, json, sys, time, os
sys.path.insert(0, "/app/shared")

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import LLMSettings
from models.schemas import LLMRequest, LLMResponse, HealthResponse
from streaming import router as streaming_router
from utils.logger import configure_logging, get_logger

settings = LLMSettings()
configure_logging("llm-service", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="LLM Service (Free/Local)", version="2.0.0")
Instrumentator().instrument(app).expose(app)
app.include_router(streaming_router)

_redis: aioredis.Redis | None = None

# Ollama runs locally on port 11434 by default
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
PRIMARY_MODEL  = os.getenv("OLLAMA_PRIMARY_MODEL",  "llama3.2")
FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "mistral")


@app.on_event("startup")
async def startup() -> None:
    global _redis
    _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    log.info("llm_service_started", mode="local/ollama", primary=PRIMARY_MODEL)


@app.on_event("shutdown")
async def shutdown() -> None:
    if _redis:
        await _redis.aclose()


@app.post("/generate", response_model=LLMResponse)
async def generate(req: LLMRequest):
    t0 = time.perf_counter()

    # Only cache temperature=0 (deterministic) calls
    cache_key = _make_cache_key(req) if req.temperature == 0 else None
    if cache_key and _redis:
        cached = await _redis.get(cache_key)
        if cached:
            log.debug("llm_cache_hit", key=cache_key[:12])
            return LLMResponse(**json.loads(cached))

    response = await _call_ollama(req, PRIMARY_MODEL)

    # If primary model fails, try fallback
    if response is None:
        log.warning("primary_model_failed", model=PRIMARY_MODEL, fallback=FALLBACK_MODEL)
        response = await _call_ollama(req, FALLBACK_MODEL)

    if response is None:
        # Last resort: return a helpful error message
        response = LLMResponse(
            content="Ollama is not running. Please start it with: ollama serve",
            model="error",
            tokens_in=0,
            tokens_out=0,
            latency_ms=0,
        )

    response.latency_ms = (time.perf_counter() - t0) * 1000

    if cache_key and _redis and response.model != "error":
        await _redis.set(cache_key, json.dumps(response.model_dump()), ex=settings.CACHE_TTL_S)

    log.info("llm_generate", model=response.model,
             tokens_in=response.tokens_in, tokens_out=response.tokens_out,
             latency_ms=round(response.latency_ms, 1))
    return response


async def _call_ollama(req: LLMRequest, model: str) -> LLMResponse | None:
    """Call Ollama's local API. Returns None if Ollama is not running."""
    # Build the prompt from system + history + user message
    messages = [{"role": "system", "content": req.system_prompt}]
    for m in req.history:
        messages.append({"role": m.role.value, "content": m.content})
    messages.append({"role": "user", "content": req.user_prompt})

    payload = {
        "model":    model,
        "messages": messages,
        "stream":   False,
        "options": {
            "temperature": req.temperature,
            "num_predict": req.max_tokens,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data    = resp.json()
            content = data.get("message", {}).get("content", "")
            usage   = data.get("usage", {})

            return LLMResponse(
                content=content,
                model=model,
                tokens_in=usage.get("prompt_tokens", len(req.user_prompt.split())),
                tokens_out=usage.get("completion_tokens", len(content.split())),
                latency_ms=0,
            )
    except Exception as exc:
        log.warning("ollama_call_failed", model=model, error=str(exc))
        return None


def _make_cache_key(req: LLMRequest) -> str:
    raw = f"{req.system_prompt[:300]}|{req.user_prompt[:500]}|{PRIMARY_MODEL}"
    return "llm:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


@app.get("/health", response_model=HealthResponse)
async def health():
    # Check if Ollama is reachable
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            ollama_ok = PRIMARY_MODEL.split(":")[0] in " ".join(models)
    except Exception:
        models, ollama_ok = [], False

    return HealthResponse(
        service="llm-service",
        details={
            "mode":          "local/ollama",
            "primary_model": PRIMARY_MODEL,
            "ollama_url":    OLLAMA_URL,
            "ollama_online": ollama_ok,
            "available_models": models[:5],
        }
    )
