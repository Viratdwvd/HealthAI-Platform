"""
LLM Service – Streaming SSE (Ollama local version)
---------------------------------------------------
Streams tokens from Ollama in real-time via Server-Sent Events.
"""

from __future__ import annotations
import json, os, sys
sys.path.insert(0, "/app/shared")

from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import httpx

from models.schemas import LLMRequest
from utils.logger import get_logger

log      = get_logger(__name__)
router   = APIRouter(tags=["llm-streaming"])
OLLAMA_URL    = os.getenv("OLLAMA_URL", "http://ollama:11434")
PRIMARY_MODEL = os.getenv("OLLAMA_PRIMARY_MODEL", "llama3.2")


@router.post("/generate/stream")
async def generate_stream(req: LLMRequest):
    return StreamingResponse(
        _stream_ollama(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


async def _stream_ollama(req: LLMRequest) -> AsyncGenerator[str, None]:
    messages = [{"role": "system", "content": req.system_prompt}]
    for m in req.history:
        messages.append({"role": m.role.value, "content": m.content})
    messages.append({"role": "user", "content": req.user_prompt})

    payload = {
        "model":    PRIMARY_MODEL,
        "messages": messages,
        "stream":   True,
        "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
    }

    tokens = 0
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            tokens += 1
                            yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                        if chunk.get("done"):
                            yield f"data: {json.dumps({'token': '', 'done': True, 'tokens': tokens})}\n\n"
                            return
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        yield f"data: {json.dumps({'error': str(exc), 'done': True})}\n\n"
