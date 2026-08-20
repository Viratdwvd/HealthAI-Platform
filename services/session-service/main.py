"""
Session Service
---------------
Stores per-user conversation sessions in Redis with TTL.
Supports multi-turn memory for the Agent Orchestrator.
"""

from __future__ import annotations
import json
import sys

sys.path.insert(0, "/app/shared")

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from config.settings import SessionSettings
from models.schemas import ChatMessage, MessageRole, Session, HealthResponse
from utils.logger import configure_logging, get_logger

settings = SessionSettings()
configure_logging("session-service", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="Session Service", version="1.0.0")
Instrumentator().instrument(app).expose(app)

_redis: aioredis.Redis | None = None


@app.on_event("startup")
async def startup() -> None:
    global _redis
    _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    log.info("Session service started", ttl=settings.SESSION_TTL_S)


@app.on_event("shutdown")
async def shutdown() -> None:
    if _redis:
        await _redis.aclose()


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.post("/sessions", response_model=Session, status_code=201)
async def create_session(tenant_id: str, user_id: str):
    session = Session(tenant_id=tenant_id, user_id=user_id)
    await _save(session)
    log.info("session_created", session_id=session.session_id, user_id=user_id)
    return session


@app.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    session = await _load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


class AppendMessagesRequest(BaseModel):
    session_id: str
    tenant_id:  str
    user_id:    str
    messages:   list[dict]


@app.post("/sessions/{session_id}/messages", response_model=Session)
async def append_messages(session_id: str, req: AppendMessagesRequest):
    session = await _load(session_id)
    if not session:
        # Auto-create session
        session = Session(
            session_id=session_id,
            tenant_id=req.tenant_id,
            user_id=req.user_id,
        )

    for m in req.messages:
        session.add_message(
            role=MessageRole(m["role"]),
            content=m["content"],
        )

    await _save(session)
    return session


@app.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    assert _redis
    await _redis.delete(_key(session_id))
    log.info("session_deleted", session_id=session_id)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="session-service")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _key(session_id: str) -> str:
    return f"session:{session_id}"


async def _save(session: Session) -> None:
    assert _redis
    await _redis.set(
        _key(session.session_id),
        session.model_dump_json(),
        ex=settings.SESSION_TTL_S,
    )


async def _load(session_id: str) -> Session | None:
    assert _redis
    raw = await _redis.get(_key(session_id))
    if not raw:
        return None
    return Session.model_validate_json(raw)
