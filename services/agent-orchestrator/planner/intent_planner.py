"""
IntentPlanner – uses the LLM Service to classify query intent
and produce a structured multi-step execution plan.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List

import httpx

from models.schemas import ChatMessage, ExecutionPlan, PlanStep, QueryIntent


_PLANNER_SYSTEM = """You are an AI planning agent for a healthcare intelligence platform.
Given a user query, output a JSON execution plan with this exact structure:

{
  "intent": "<retrieval|analytics|forecast|summary|knowledge|mixed>",
  "reasoning": "<why you chose these steps>",
  "steps": [
    {
      "step_id": 1,
      "service": "<rag|analytics|knowledge|llm>",
      "action": "<describe action>",
      "params": {},
      "depends_on": []
    }
  ]
}

Rules:
- For factual/clinical questions → use rag (and optionally knowledge)
- For data analysis / statistics → use analytics
- For time-series predictions → use analytics with operation=forecast
- For drug/disease knowledge → use knowledge
- For complex questions → use multiple services
- Keep steps minimal and purposeful
- Output ONLY valid JSON, no markdown fences
"""


class IntentPlanner:
    def __init__(self, llm_service_url: str, http: httpx.AsyncClient) -> None:
        self._url  = llm_service_url
        self._http = http

    async def plan(
        self,
        query:   str,
        history: List[ChatMessage],
        context: Dict[str, Any],
    ) -> ExecutionPlan:
        user_prompt = f"User query: {query}\nContext metadata: {json.dumps(context)}"

        payload = {
            "system_prompt": _PLANNER_SYSTEM,
            "user_prompt":   user_prompt,
            "history":       [m.model_dump(mode="json") for m in history[-4:]],
            "temperature":   0.0,
            "max_tokens":    512,
        }

        try:
            r = await self._http.post(f"{self._url}/generate", json=payload, timeout=15)
            r.raise_for_status()
            raw_json = r.json().get("content", "{}")
            plan_data = json.loads(raw_json)
        except Exception:
            # Fallback: single RAG step
            plan_data = {
                "intent":    "retrieval",
                "reasoning": "Fallback to RAG due to planner error.",
                "steps": [
                    {"step_id": 1, "service": "rag", "action": "retrieve",
                     "params": {"top_k": 10}, "depends_on": []},
                ],
            }

        steps = [PlanStep(**s) for s in plan_data.get("steps", [])]
        intent_str = plan_data.get("intent", "retrieval")
        try:
            intent = QueryIntent(intent_str)
        except ValueError:
            intent = QueryIntent.RETRIEVAL

        return ExecutionPlan(
            intent=intent,
            steps=steps,
            reasoning=plan_data.get("reasoning", ""),
        )
