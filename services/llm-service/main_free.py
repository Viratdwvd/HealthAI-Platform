"""
LLM Service – 100% FREE version
---------------------------------
Priority order (all free, no credit card):
  1. Groq  – cloud, blazing fast, free tier (14,400 req/day)
             Sign up: console.groq.com  (no credit card)
             Models: llama-3.1-70b-versatile, mixtral-8x7b
  2. Ollama – runs 100% locally on your machine
             Install: ollama.com  then: ollama pull llama3.1
  3. HuggingFace Inference API – free tier
             Sign up: huggingface.co  (no credit card)

Set FREE_LLM_PROVIDER in .env:
    FREE_LLM_PROVIDER=groq    ← fastest, recommended
    FREE_LLM_PROVIDER=ollama  ← fully offline
    FREE_LLM_PROVIDER=hf      ← huggingface
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time

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
configure_logging("llm-service-free", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="LLM Service (Free Tier)", version="2.0.0")
Instrumentator().instrument(app).expose(app)
app.include_router(streaming_router)

_redis: aioredis.Redis | None = None

# ── Provider config ───────────────────────────────────────────────────────────
PROVIDER       = os.getenv("FREE_LLM_PROVIDER", "groq").lower()
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL     = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
OLLAMA_URL     = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "llama3.2")
HF_API_KEY     = os.getenv("HF_API_KEY", "")
HF_MODEL       = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
CACHE_TTL      = int(os.getenv("LLM_CACHE_TTL_S", "300"))


@app.on_event("startup")
async def startup() -> None:
    global _redis
    _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    log.info("llm_free_service_started", provider=PROVIDER)
    _log_provider_info()


def _log_provider_info() -> None:
    if PROVIDER == "groq":
        if not GROQ_API_KEY:
            log.warning("GROQ_API_KEY not set! Get free key at console.groq.com")
        else:
            log.info("Using Groq free tier", model=GROQ_MODEL)
    elif PROVIDER == "ollama":
        log.info("Using Ollama (local)", url=OLLAMA_URL, model=OLLAMA_MODEL)
    elif PROVIDER == "hf":
        log.info("Using HuggingFace free inference", model=HF_MODEL)


@app.on_event("shutdown")
async def shutdown() -> None:
    if _redis:
        await _redis.aclose()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/generate", response_model=LLMResponse)
async def generate(req: LLMRequest):
    t0 = time.perf_counter()

    # Cache for deterministic (temp=0) requests
    cache_key = _make_key(req) if req.temperature == 0 else None
    if cache_key and _redis:
        cached = await _redis.get(cache_key)
        if cached:
            log.debug("llm_cache_hit")
            return LLMResponse(**json.loads(cached))

    # Try providers in order
    providers = _get_provider_chain()
    response  = None
    for provider_fn in providers:
        try:
            response = await provider_fn(req)
            break
        except Exception as exc:
            log.warning("provider_failed", error=str(exc)[:120])

    if response is None:
        response = LLMResponse(
            content="I'm unable to generate a response right now. Please check your provider setup.",
            model="none", tokens_in=0, tokens_out=0, latency_ms=0,
        )

    response.latency_ms = (time.perf_counter() - t0) * 1000

    if cache_key and _redis:
        await _redis.set(cache_key, json.dumps(response.model_dump()), ex=CACHE_TTL)

    log.info("llm_generate", provider=PROVIDER, model=response.model,
             tokens_out=response.tokens_out, latency_ms=round(response.latency_ms, 1))
    return response


def _get_provider_chain():
    """Returns ordered list of provider functions to try."""
    chain = []
    if PROVIDER == "groq":
        chain = [_call_groq, _call_ollama, _call_hf]
    elif PROVIDER == "ollama":
        chain = [_call_ollama, _call_groq, _call_hf]
    elif PROVIDER == "hf":
        chain = [_call_hf, _call_groq, _call_ollama]
    else:
        chain = [_call_groq, _call_ollama, _call_hf]
    return chain


# ── Provider implementations ──────────────────────────────────────────────────

async def _call_groq(req: LLMRequest) -> LLMResponse:
    """
    Groq free tier – no credit card required.
    Sign up: https://console.groq.com
    Free limits: 14,400 requests/day, 30 req/min
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")

    messages = _build_messages(req)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model":       GROQ_MODEL,
                "messages":    messages,
                "temperature": req.temperature,
                "max_tokens":  req.max_tokens,
            },
        )
        r.raise_for_status()
        data = r.json()

    return LLMResponse(
        content=data["choices"][0]["message"]["content"],
        model=data["model"],
        tokens_in=data["usage"]["prompt_tokens"],
        tokens_out=data["usage"]["completion_tokens"],
        latency_ms=0,
    )


async def _call_ollama(req: LLMRequest) -> LLMResponse:
    """
    Ollama – runs AI models 100% locally, completely free.
    Install: https://ollama.com
    Then run: ollama pull llama3.2
    (Uses ~2GB RAM for llama3.2, or ~4GB for llama3.1)
    """
    messages = _build_messages(req)
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model":    OLLAMA_MODEL,
                "messages": messages,
                "stream":   False,
                "options":  {"temperature": req.temperature, "num_predict": req.max_tokens},
            },
        )
        r.raise_for_status()
        data = r.json()

    content = data.get("message", {}).get("content", "")
    usage   = data.get("usage", {})
    return LLMResponse(
        content=content,
        model=f"ollama/{OLLAMA_MODEL}",
        tokens_in=usage.get("prompt_tokens", 0),
        tokens_out=usage.get("completion_tokens", len(content.split())),
        latency_ms=0,
    )


async def _call_hf(req: LLMRequest) -> LLMResponse:
    """
    HuggingFace Inference API – free tier.
    Sign up: https://huggingface.co (free, no credit card)
    Get token: huggingface.co/settings/tokens
    """
    if not HF_API_KEY:
        raise ValueError("HF_API_KEY not set")

    prompt = f"[INST] {req.system_prompt}\n\n{req.user_prompt} [/INST]"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://api-inference.huggingface.co/models/{HF_MODEL}",
            headers={"Authorization": f"Bearer {HF_API_KEY}"},
            json={
                "inputs":      prompt,
                "parameters":  {"max_new_tokens": req.max_tokens, "temperature": max(0.01, req.temperature)},
            },
        )
        r.raise_for_status()
        data = r.json()

    content = data[0].get("generated_text", "") if isinstance(data, list) else str(data)
    # Strip the prompt echo that HF sometimes includes
    if "[/INST]" in content:
        content = content.split("[/INST]", 1)[-1].strip()

    return LLMResponse(
        content=content,
        model=f"hf/{HF_MODEL}",
        tokens_in=len(prompt.split()),
        tokens_out=len(content.split()),
        latency_ms=0,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_messages(req: LLMRequest) -> list:
    msgs = [{"role": "system", "content": req.system_prompt}]
    for m in req.history:
        msgs.append({"role": m.role.value, "content": m.content})
    msgs.append({"role": "user", "content": req.user_prompt})
    return msgs


def _make_key(req: LLMRequest) -> str:
    raw = f"{req.system_prompt[:300]}|{req.user_prompt[:500]}|{GROQ_MODEL}"
    return "llm:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


@app.get("/health", response_model=HealthResponse)
async def health():
    details = {"provider": PROVIDER, "model": GROQ_MODEL if PROVIDER == "groq" else OLLAMA_MODEL}
    if PROVIDER == "groq" and not GROQ_API_KEY:
        details["warning"] = "GROQ_API_KEY not set – get free key at console.groq.com"
    return HealthResponse(service="llm-service-free", details=details)


@app.get("/providers")
async def list_providers():
    """Shows all available free providers and their setup status."""
    return {
        "current": PROVIDER,
        "available": {
            "groq": {
                "status": "ready" if GROQ_API_KEY else "missing GROQ_API_KEY",
                "free_signup": "https://console.groq.com",
                "requires_credit_card": False,
                "model": GROQ_MODEL,
                "speed": "very fast (cloud)",
                "daily_limit": "14,400 requests/day",
            },
            "ollama": {
                "status": "depends on local install",
                "install": "https://ollama.com then: ollama pull llama3.2",
                "requires_credit_card": False,
                "model": OLLAMA_MODEL,
                "speed": "medium (local CPU/GPU)",
                "daily_limit": "unlimited",
            },
            "hf": {
                "status": "ready" if HF_API_KEY else "missing HF_API_KEY",
                "free_signup": "https://huggingface.co",
                "requires_credit_card": False,
                "model": HF_MODEL,
                "speed": "slow (shared inference)",
                "daily_limit": "~1000 requests/day",
            },
        },
    }
