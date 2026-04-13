"""
Agent Orchestrator
------------------
1. Receives a user query
2. Uses the LLM to determine intent and build an execution plan
3. Executes plan steps (possibly in parallel)
4. Aggregates results and generates the final response via LLM Service
"""

from __future__ import annotations
import asyncio
import sys
import time
import uuid
from typing import Any, Dict, List

sys.path.insert(0, "/app/shared")

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import AgentSettings
from models.schemas import (
    ExecutionPlan, PlanStep, QueryIntent, QueryRequest, QueryResponse,
    SourceAttribution, HealthResponse, ChatMessage, MessageRole,
)
from planner.intent_planner import IntentPlanner
from utils.logger import configure_logging, get_logger

settings = AgentSettings()
configure_logging("agent-orchestrator", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="Agent Orchestrator", version="1.0.0")
Instrumentator().instrument(app).expose(app)

_http:    httpx.AsyncClient | None = None
_planner: IntentPlanner | None     = None


@app.on_event("startup")
async def startup() -> None:
    global _http, _planner
    _http    = httpx.AsyncClient(timeout=settings.AGENT_TIMEOUT_S)
    _planner = IntentPlanner(settings.LLM_SERVICE_URL, _http)
    log.info("Agent orchestrator started")


@app.on_event("shutdown")
async def shutdown() -> None:
    if _http:
        await _http.aclose()


# ─── Main orchestration route ─────────────────────────────────────────────────

@app.post("/orchestrate", response_model=QueryResponse)
async def orchestrate(req: QueryRequest):
    t0 = time.perf_counter()
    assert _http and _planner

    # 1. Fetch conversation history from session service
    history: List[ChatMessage] = []
    if req.session_id:
        history = await _fetch_session_history(req.session_id)

    # 2. Build execution plan via LLM planner
    plan: ExecutionPlan = await _planner.plan(req.query, history, req.context)
    log.info("plan_created", plan_id=str(plan.plan_id), steps=len(plan.steps), intent=plan.intent)

    # 3. Execute steps (respecting dependencies)
    step_results: Dict[int, Any] = {}
    executed_layers = _topological_layers(plan.steps)

    for layer in executed_layers:
        tasks = [
            asyncio.create_task(_execute_step(step, req, step_results))
            for step in layer
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for step, result in zip(layer, results):
            if isinstance(result, Exception):
                log.error("step_failed", step_id=step.step_id, error=str(result))
                step_results[step.step_id] = {"error": str(result)}
            else:
                step_results[step.step_id] = result

    # 4. Aggregate context for final LLM call
    rag_chunks   = _extract_rag_chunks(step_results)
    analytics    = _extract_analytics(step_results)
    knowledge    = _extract_knowledge(step_results)

    # 5. Generate final answer via LLM service
    answer, reasoning = await _generate_answer(req.query, rag_chunks, analytics, knowledge, history)

    # 6. Build source attributions
    sources = [
        SourceAttribution(
            chunk_id=c.get("chunk_id", ""),
            source=c.get("source", ""),
            content=c.get("content", "")[:300],
            score=c.get("score", 0.0),
        )
        for c in rag_chunks[:5]
    ]

    # 7. Persist updated session
    if req.session_id:
        await _update_session(req.session_id, req.query, answer, req.tenant_id, req.user_id)

    latency = (time.perf_counter() - t0) * 1000
    log.info("orchestrate_done", latency_ms=latency)

    return QueryResponse(
        query=req.query,
        answer=answer,
        intent=plan.intent,
        sources=sources,
        confidence=_estimate_confidence(rag_chunks),
        reasoning=reasoning,
        latency_ms=latency,
        session_id=req.session_id,
    )


# ─── Step executor ────────────────────────────────────────────────────────────

async def _execute_step(
    step:         PlanStep,
    req:          QueryRequest,
    prev_results: Dict[int, Any],
) -> Any:
    svc = step.service
    log.debug("executing_step", step_id=step.step_id, service=svc, action=step.action)

    if svc == "rag":
        return await _call_service(
            settings.RAG_SERVICE_URL, "/retrieve",
            {"query": req.query, "tenant_id": req.tenant_id, **step.params},
        )
    elif svc == "analytics":
        return await _call_service(
            settings.ANALYTICS_SERVICE_URL, "/analyze",
            {"tenant_id": req.tenant_id, "dataset_id": req.context.get("dataset_id", ""), **step.params},
        )
    elif svc == "knowledge":
        return await _call_service(
            settings.KNOWLEDGE_SERVICE_URL, "/lookup",
            {"query": req.query, "tenant_id": req.tenant_id, **step.params},
        )
    elif svc == "llm":
        return await _call_service(
            settings.LLM_SERVICE_URL, "/generate",
            step.params,
        )
    else:
        log.warning("unknown_service", service=svc)
        return {}


async def _call_service(base_url: str, path: str, payload: dict) -> Any:
    assert _http
    try:
        resp = await _http.post(f"{base_url}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"HTTP {exc.response.status_code} from {base_url}{path}")
    except httpx.RequestError as exc:
        raise RuntimeError(f"Connection error to {base_url}: {exc}")


# ─── Session helpers ──────────────────────────────────────────────────────────

async def _fetch_session_history(session_id: str) -> List[ChatMessage]:
    assert _http
    try:
        r = await _http.get(f"{settings.SESSION_SERVICE_URL}/sessions/{session_id}")
        if r.status_code == 200:
            data = r.json()
            return [ChatMessage(**m) for m in data.get("messages", [])]
    except Exception:
        pass
    return []


async def _update_session(
    session_id: str, query: str, answer: str, tenant_id: str, user_id: str
) -> None:
    assert _http
    try:
        await _http.post(
            f"{settings.SESSION_SERVICE_URL}/sessions/{session_id}/messages",
            json={
                "session_id": session_id,
                "tenant_id":  tenant_id,
                "user_id":    user_id,
                "messages":   [
                    {"role": "user",      "content": query},
                    {"role": "assistant", "content": answer},
                ],
            },
        )
    except Exception as exc:
        log.warning("session_update_failed", error=str(exc))


# ─── Result extraction helpers ────────────────────────────────────────────────

def _extract_rag_chunks(results: Dict[int, Any]) -> List[Dict]:
    chunks = []
    for r in results.values():
        if isinstance(r, dict) and "chunks" in r:
            chunks.extend(r["chunks"])
    return chunks


def _extract_analytics(results: Dict[int, Any]) -> Dict:
    for r in results.values():
        if isinstance(r, dict) and "operation" in r:
            return r
    return {}


def _extract_knowledge(results: Dict[int, Any]) -> Dict:
    for r in results.values():
        if isinstance(r, dict) and "rules" in r:
            return r
    return {}


async def _generate_answer(
    query:     str,
    chunks:    List[Dict],
    analytics: Dict,
    knowledge: Dict,
    history:   List[ChatMessage],
) -> tuple[str, str]:
    context_parts: List[str] = []

    if chunks:
        context_parts.append("=== Retrieved Documents ===")
        for i, c in enumerate(chunks[:6], 1):
            context_parts.append(f"[{i}] (source: {c.get('source','?')}, score: {c.get('score',0):.2f})\n{c.get('content','')}")

    if analytics:
        context_parts.append(f"\n=== Analytics Result ===\n{analytics}")

    if knowledge and knowledge.get("facts"):
        context_parts.append("\n=== Clinical Knowledge ===\n" + "\n".join(knowledge["facts"]))

    assert _http
    payload = {
        "system_prompt": _SYSTEM_PROMPT,
        "user_prompt":   f"Context:\n{chr(10).join(context_parts)}\n\nUser Question: {query}",
        "history":       [m.model_dump(mode="json") for m in history[-6:]],
        "temperature":   0.2,
        "max_tokens":    1024,
    }

    try:
        r = await _http.post(f"{settings.LLM_SERVICE_URL}/generate", json=payload)
        r.raise_for_status()
        data    = r.json()
        content = data.get("content", "I was unable to generate a response.")
        reasoning = data.get("reasoning", "")
        return content, reasoning
    except Exception as exc:
        log.error("llm_call_failed", error=str(exc))
        return "I encountered an error generating a response. Please try again.", ""


# ─── Utilities ────────────────────────────────────────────────────────────────

def _topological_layers(steps: List[PlanStep]) -> List[List[PlanStep]]:
    """Group steps into execution layers based on depends_on."""
    step_map = {s.step_id: s for s in steps}
    layers: List[List[PlanStep]] = []
    remaining = list(steps)

    while remaining:
        layer = [s for s in remaining if all(d not in {r.step_id for r in remaining} for d in s.depends_on)]
        if not layer:
            layer = [remaining[0]]   # cycle-break fallback
        layers.append(layer)
        for s in layer:
            remaining.remove(s)

    return layers


def _estimate_confidence(chunks: List[Dict]) -> float:
    if not chunks:
        return 0.3
    top_scores = [c.get("score", 0.0) for c in chunks[:3]]
    return round(min(sum(top_scores) / len(top_scores), 1.0), 3)


_SYSTEM_PROMPT = """You are a highly capable healthcare intelligence assistant.
Answer questions using ONLY the context provided below.
Always cite the source document when making factual claims.
If the context does not contain enough information, say so clearly.
For clinical decisions, always recommend consulting a qualified healthcare professional.
Format your response in clear, professional language."""
