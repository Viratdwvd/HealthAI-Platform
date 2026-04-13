"""
Unit tests – Agent Orchestrator (planner + topological sort)
Run with: pytest tests/ -v
"""

import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

import pytest
from models.schemas import PlanStep, QueryIntent


# ─── Topological layer sort ───────────────────────────────────────────────────

def test_topo_single_step():
    from main import _topological_layers

    steps  = [PlanStep(step_id=1, service="rag", action="retrieve", params={}, depends_on=[])]
    layers = _topological_layers(steps)
    assert len(layers) == 1
    assert layers[0][0].step_id == 1


def test_topo_parallel_steps():
    from main import _topological_layers

    steps = [
        PlanStep(step_id=1, service="rag",       action="retrieve", params={}, depends_on=[]),
        PlanStep(step_id=2, service="knowledge", action="lookup",   params={}, depends_on=[]),
    ]
    layers = _topological_layers(steps)
    # Both can run in parallel (layer 0)
    assert len(layers) == 1
    assert len(layers[0]) == 2


def test_topo_sequential_dependency():
    from main import _topological_layers

    steps = [
        PlanStep(step_id=1, service="rag", action="retrieve",  params={}, depends_on=[]),
        PlanStep(step_id=2, service="llm", action="summarize", params={}, depends_on=[1]),
    ]
    layers = _topological_layers(steps)
    assert len(layers) == 2
    assert layers[0][0].step_id == 1
    assert layers[1][0].step_id == 2


def test_topo_diamond_dependency():
    from main import _topological_layers

    steps = [
        PlanStep(step_id=1, service="rag",       action="r",  params={}, depends_on=[]),
        PlanStep(step_id=2, service="knowledge", action="k",  params={}, depends_on=[1]),
        PlanStep(step_id=3, service="analytics", action="a",  params={}, depends_on=[1]),
        PlanStep(step_id=4, service="llm",       action="g",  params={}, depends_on=[2, 3]),
    ]
    layers = _topological_layers(steps)
    assert len(layers) == 3
    assert layers[0][0].step_id == 1
    assert len(layers[1]) == 2      # steps 2 & 3 in parallel
    assert layers[2][0].step_id == 4


# ─── Confidence estimation ────────────────────────────────────────────────────

def test_confidence_no_chunks():
    from main import _estimate_confidence
    assert _estimate_confidence([]) == 0.3


def test_confidence_with_high_scores():
    from main import _estimate_confidence

    chunks = [{"score": 0.95}, {"score": 0.90}, {"score": 0.85}]
    conf   = _estimate_confidence(chunks)
    assert 0.8 < conf <= 1.0


def test_confidence_capped_at_one():
    from main import _estimate_confidence

    chunks = [{"score": 1.5}, {"score": 2.0}]   # unrealistically high
    conf   = _estimate_confidence(chunks)
    assert conf <= 1.0


# ─── Intent Planner (mocked LLM) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_planner_fallback_on_error():
    """Planner should return a safe RAG-only plan when LLM fails."""
    from planner.intent_planner import IntentPlanner

    mock_http = AsyncMock()
    mock_http.post.side_effect = Exception("LLM unreachable")

    planner = IntentPlanner("http://fake-llm:8006", mock_http)
    plan    = await planner.plan("What is the patient's diagnosis?", history=[], context={})

    assert plan.intent  == QueryIntent.RETRIEVAL
    assert len(plan.steps) >= 1
    assert plan.steps[0].service == "rag"


@pytest.mark.asyncio
async def test_planner_parses_valid_llm_response():
    """Planner should correctly parse a well-formed LLM JSON response."""
    import json
    from planner.intent_planner import IntentPlanner

    plan_json = json.dumps({
        "intent": "analytics",
        "reasoning": "User wants a forecast",
        "steps": [
            {"step_id": 1, "service": "analytics", "action": "forecast",
             "params": {"operation": "forecast", "horizon": 30}, "depends_on": []},
        ],
    })

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"content": plan_json})
    mock_response.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.post.return_value = mock_response

    planner = IntentPlanner("http://fake-llm:8006", mock_http)
    plan    = await planner.plan("Forecast admissions for next month", history=[], context={})

    assert plan.intent == QueryIntent.ANALYTICS
    assert plan.steps[0].service == "analytics"
    assert plan.reasoning == "User wants a forecast"
