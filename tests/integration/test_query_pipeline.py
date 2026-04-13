"""
Integration Tests – Full Query Pipeline (mocked services)
----------------------------------------------------------
Tests the agent orchestrator's data flow end-to-end with all
downstream services mocked via httpx.MockTransport.

Run with:
    PYTHONPATH=shared:services/agent-orchestrator pytest tests/integration/ -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, "shared")
sys.path.insert(0, "services/agent-orchestrator")

import pytest
from models.schemas import (
    QueryIntent, QueryRequest, PlanStep, ExecutionPlan,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_rag_response() -> dict:
    return {
        "query": "chest pain diagnosis",
        "chunks": [
            {
                "chunk_id":  "chunk-001",
                "content":   "Patient P003 presented with chest pain, elevated troponin. ECG showed ST elevation.",
                "source":    "patients.csv",
                "score":     0.91,
                "metadata":  {},
            },
            {
                "chunk_id":  "chunk-002",
                "content":   "Myocardial infarction confirmed. Patient started on aspirin and clopidogrel.",
                "source":    "discharge_summary.pdf",
                "score":     0.87,
                "metadata":  {},
            },
        ],
        "latency_ms": 210.0,
    }


def _make_knowledge_response() -> dict:
    return {
        "rules": [
            {
                "id":             "rule_001",
                "domain":         "cardiology",
                "keywords":       ["chest pain", "angina"],
                "facts":          ["Chest pain may indicate cardiac event."],
                "recommendation": "Refer to cardiology immediately.",
                "severity":       "high",
                "source":         "AHA 2023",
            }
        ],
        "facts":   ["Chest pain may indicate cardiac event."],
        "sources": ["AHA 2023"],
    }


def _make_llm_plan_response() -> dict:
    plan = {
        "intent":    "retrieval",
        "reasoning": "Query relates to clinical symptoms; RAG + Knowledge needed.",
        "steps": [
            {"step_id": 1, "service": "rag",       "action": "retrieve",
             "params": {"top_k": 10}, "depends_on": []},
            {"step_id": 2, "service": "knowledge", "action": "lookup",
             "params": {},             "depends_on": []},
        ],
    }
    return {"content": json.dumps(plan), "model": "gpt-4o", "tokens_in": 120, "tokens_out": 80, "latency_ms": 400}


def _make_llm_answer_response() -> dict:
    return {
        "content":    "Based on the retrieved records, patient P003 presented with chest pain and was diagnosed with myocardial infarction. [Source: patients.csv, discharge_summary.pdf]",
        "model":      "gpt-4o",
        "tokens_in":  800,
        "tokens_out": 150,
        "latency_ms": 900,
    }


# ─── Mock HTTP router ─────────────────────────────────────────────────────────

async def _mock_post(url: str, **kwargs) -> MagicMock:
    """Routes mock HTTP POST calls based on URL path."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.status_code = 200

    if "/generate" in url:
        # First LLM call returns plan; subsequent calls return the answer
        if not hasattr(_mock_post, "_plan_sent"):
            _mock_post._plan_sent = True
            response.json = MagicMock(return_value=_make_llm_plan_response())
        else:
            del _mock_post._plan_sent
            response.json = MagicMock(return_value=_make_llm_answer_response())
    elif "/retrieve" in url:
        response.json = MagicMock(return_value=_make_rag_response())
    elif "/lookup" in url:
        response.json = MagicMock(return_value=_make_knowledge_response())
    else:
        response.json = MagicMock(return_value={})
    return response


async def _mock_get(url: str, **kwargs) -> MagicMock:
    response = MagicMock()
    response.status_code = 404       # session not found → auto-create
    response.json = MagicMock(return_value={})
    response.raise_for_status = MagicMock(side_effect=Exception("404"))
    return response


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_query_pipeline_retrieval():
    """
    End-to-end: a 'chest pain diagnosis' query should flow through
    planner → RAG + knowledge → LLM answer → QueryResponse.
    """
    import httpx
    from main import orchestrate, startup

    # Reset mock state
    if hasattr(_mock_post, "_plan_sent"):
        del _mock_post._plan_sent

    # Patch the global http client
    import main as orchestrator_main

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(side_effect=_mock_post)
    mock_http.get  = AsyncMock(side_effect=_mock_get)

    orchestrator_main._http    = mock_http
    orchestrator_main._planner = MagicMock()
    orchestrator_main._planner.plan = AsyncMock(return_value=ExecutionPlan(
        intent=QueryIntent.RETRIEVAL,
        reasoning="RAG + Knowledge for clinical query",
        steps=[
            PlanStep(step_id=1, service="rag",       action="retrieve", params={"top_k": 10}, depends_on=[]),
            PlanStep(step_id=2, service="knowledge", action="lookup",   params={},             depends_on=[]),
        ],
    ))

    req = QueryRequest(
        query="What is the diagnosis for chest pain?",
        tenant_id="tenant-test",
        user_id="test_user",
    )

    response = await orchestrate(req)

    assert response.query     == req.query
    assert response.intent    == QueryIntent.RETRIEVAL
    assert len(response.answer) > 0
    assert len(response.sources) > 0
    assert 0.0 <= response.confidence <= 1.0
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_empty_rag_results_still_returns_answer():
    """Should gracefully handle zero RAG results (LLM says 'not found')."""
    import main as orchestrator_main

    mock_http = AsyncMock()

    async def mock_post_empty(url, **kw):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.status_code = 200
        if "/retrieve" in url:
            resp.json = MagicMock(return_value={"query": "x", "chunks": [], "latency_ms": 10})
        elif "/lookup" in url:
            resp.json = MagicMock(return_value={"rules": [], "facts": [], "sources": []})
        elif "/generate" in url:
            resp.json = MagicMock(return_value={
                "content": "I could not find relevant information in the available documents.",
                "model": "gpt-4o", "tokens_in": 100, "tokens_out": 30, "latency_ms": 300,
            })
        else:
            resp.json = MagicMock(return_value={})
        return resp

    mock_http.post = AsyncMock(side_effect=mock_post_empty)
    mock_http.get  = AsyncMock(side_effect=_mock_get)

    orchestrator_main._http    = mock_http
    orchestrator_main._planner = MagicMock()
    orchestrator_main._planner.plan = AsyncMock(return_value=ExecutionPlan(
        intent=QueryIntent.RETRIEVAL,
        reasoning="Standard retrieval",
        steps=[PlanStep(step_id=1, service="rag", action="retrieve", params={}, depends_on=[])],
    ))

    req = QueryRequest(
        query="What is the meaning of life?",
        tenant_id="tenant-test",
        user_id="test_user",
    )
    response = await orchestrate(req)

    assert len(response.answer) > 0
    assert response.confidence == 0.3   # no chunks → fallback confidence
    assert response.sources == []


@pytest.mark.asyncio
async def test_service_failure_does_not_crash_orchestrator():
    """A failing downstream service should result in partial results, not a crash."""
    import main as orchestrator_main

    async def mock_post_fail(url, **kw):
        if "/retrieve" in url:
            raise Exception("RAG service timeout")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(return_value={
            "content": "Partial answer from knowledge only.",
            "model": "gpt-4o", "tokens_in": 50, "tokens_out": 20, "latency_ms": 200,
        })
        return resp

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(side_effect=mock_post_fail)
    mock_http.get  = AsyncMock(side_effect=_mock_get)

    orchestrator_main._http    = mock_http
    orchestrator_main._planner = MagicMock()
    orchestrator_main._planner.plan = AsyncMock(return_value=ExecutionPlan(
        intent=QueryIntent.MIXED,
        reasoning="Multi-service",
        steps=[
            PlanStep(step_id=1, service="rag",       action="retrieve", params={}, depends_on=[]),
            PlanStep(step_id=2, service="knowledge", action="lookup",   params={}, depends_on=[]),
        ],
    ))

    req = QueryRequest(
        query="Tell me about hypertension guidelines",
        tenant_id="tenant-test",
        user_id="test_user",
    )

    # Should NOT raise – orchestrator handles partial failures gracefully
    response = await orchestrate(req)
    assert response is not None
    assert len(response.answer) > 0
