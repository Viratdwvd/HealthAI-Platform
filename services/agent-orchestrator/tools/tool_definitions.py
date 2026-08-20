"""
Agent Orchestrator – Tool Definitions
--------------------------------------
Defines the callable tools the LLM planner can invoke via function-calling.
Each tool maps to a microservice endpoint.

These are passed to the LLM as the `tools` parameter in OpenAI format,
giving the planner structured, validated parameters instead of free-form JSON.
"""

from __future__ import annotations
from typing import Any, Dict, List


# ─── Tool schema (OpenAI function-calling format) ─────────────────────────────

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_documents",
            "description": (
                "Search the vector database for relevant clinical documents, patient records, "
                "or any text matching the query. Returns scored chunks with source attribution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type":        "string",
                        "description": "The search query. Be specific and clinical where possible.",
                    },
                    "top_k": {
                        "type":        "integer",
                        "description": "Maximum number of chunks to retrieve (default 10, max 30).",
                        "default":     10,
                    },
                    "filters": {
                        "type":        "object",
                        "description": "Optional metadata filters, e.g. {\"source\": \"patients.csv\"}.",
                    },
                    "use_hybrid": {
                        "type":        "boolean",
                        "description": "Whether to use hybrid BM25+vector search (default true).",
                        "default":     True,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_clinical_knowledge",
            "description": (
                "Look up clinical rules, guidelines, and domain knowledge for a medical query. "
                "Returns matched rules, key facts, and source citations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type":        "string",
                        "description": "The clinical topic or question to look up.",
                    },
                    "domains": {
                        "type":        "array",
                        "items":       {"type": "string"},
                        "description": "Optional list of clinical domains to restrict search "
                                       "(e.g. ['cardiology', 'diabetes']).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_analytics",
            "description": (
                "Run statistical analysis or time-series forecasting on a dataset. "
                "Use 'stats' for descriptive statistics, 'forecast' for future predictions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type":        "string",
                        "enum":        ["stats", "forecast"],
                        "description": "The analytics operation to perform.",
                    },
                    "dataset_id": {
                        "type":        "string",
                        "description": "ID of the dataset to analyse.",
                    },
                    "horizon": {
                        "type":        "integer",
                        "description": "For forecast: number of days to predict ahead (default 30).",
                        "default":     30,
                    },
                },
                "required": ["operation", "dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarise_documents",
            "description": (
                "Summarise a collection of document chunks into a concise clinical summary. "
                "Use after retrieve_documents when the user wants a high-level overview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type":        "string",
                        "description": "The combined text content to summarise.",
                    },
                    "style": {
                        "type":        "string",
                        "enum":        ["clinical", "plain", "bullet"],
                        "description": "Summary style (default: clinical).",
                        "default":     "clinical",
                    },
                    "max_words": {
                        "type":        "integer",
                        "description": "Target word count for the summary (default 200).",
                        "default":     200,
                    },
                },
                "required": ["content"],
            },
        },
    },
]


# ─── Tool dispatcher ──────────────────────────────────────────────────────────

class ToolDispatcher:
    """
    Maps LLM function-call names → actual service calls.
    Used by the Agent Orchestrator when operating in function-calling mode.
    """

    def __init__(
        self,
        rag_url:       str,
        knowledge_url: str,
        analytics_url: str,
        llm_url:       str,
        tenant_id:     str,
        http,                          # httpx.AsyncClient
    ) -> None:
        self._rag       = rag_url
        self._knowledge = knowledge_url
        self._analytics = analytics_url
        self._llm       = llm_url
        self._tenant    = tenant_id
        self._http      = http

    async def call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Dispatch a tool call by name."""
        dispatch = {
            "retrieve_documents":       self._retrieve,
            "lookup_clinical_knowledge": self._knowledge_lookup,
            "run_analytics":            self._analytics_run,
            "summarise_documents":      self._summarise,
        }
        fn = dispatch.get(name)
        if not fn:
            raise ValueError(f"Unknown tool: {name}")
        return await fn(arguments)

    async def _retrieve(self, args: Dict[str, Any]) -> Any:
        payload = {
            "query":     args["query"],
            "tenant_id": self._tenant,
            "top_k":     args.get("top_k", 10),
            "filters":   args.get("filters", {}),
            "use_rerank": True,
        }
        r = await self._http.post(f"{self._rag}/retrieve", json=payload)
        r.raise_for_status()
        return r.json()

    async def _knowledge_lookup(self, args: Dict[str, Any]) -> Any:
        payload = {
            "query":     args["query"],
            "tenant_id": self._tenant,
            "domains":   args.get("domains", []),
        }
        r = await self._http.post(f"{self._knowledge}/lookup", json=payload)
        r.raise_for_status()
        return r.json()

    async def _analytics_run(self, args: Dict[str, Any]) -> Any:
        payload = {
            "tenant_id":  self._tenant,
            "dataset_id": args["dataset_id"],
            "operation":  args["operation"],
            "params":     {"horizon": args.get("horizon", 30)},
        }
        r = await self._http.post(f"{self._analytics}/analyze", json=payload)
        r.raise_for_status()
        return r.json()

    async def _summarise(self, args: Dict[str, Any]) -> Any:
        from services.llm_service.prompts.templates import SUMMARISE_SYSTEM
        payload = {
            "system_prompt": SUMMARISE_SYSTEM,
            "user_prompt":   f"Summarise in {args.get('max_words', 200)} words ({args.get('style', 'clinical')} style):\n\n{args['content']}",
            "temperature":   0.1,
            "max_tokens":    512,
        }
        r = await self._http.post(f"{self._llm}/generate", json=payload)
        r.raise_for_status()
        return {"summary": r.json().get("content", "")}
