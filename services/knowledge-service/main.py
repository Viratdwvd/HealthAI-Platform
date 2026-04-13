"""
Knowledge Service
-----------------
• Loads domain rules from YAML at startup
• Matches query against rules using keyword + regex matching
• Optional UMLS API enrichment for medical term lookup
"""

from __future__ import annotations
import re
import sys

sys.path.insert(0, "/app/shared")

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import KnowledgeSettings
from models.schemas import KnowledgeRequest, KnowledgeResult, HealthResponse
from rules.rule_engine import RuleEngine
from utils.logger import configure_logging, get_logger

settings = KnowledgeSettings()
configure_logging("knowledge-service", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="Knowledge Service", version="1.0.0")
Instrumentator().instrument(app).expose(app)

_engine: RuleEngine | None = None


@app.on_event("startup")
async def startup() -> None:
    global _engine
    _engine = RuleEngine(settings.RULES_FILE)
    await _engine.load()
    log.info("Knowledge service started", rules=len(_engine))


@app.post("/lookup", response_model=KnowledgeResult)
async def lookup(req: KnowledgeRequest):
    assert _engine
    matched_rules = _engine.match(req.query, domains=req.domains)

    facts: list[str] = []
    sources: list[str] = []

    for rule in matched_rules:
        facts.extend(rule.get("facts", []))
        if "source" in rule:
            sources.append(rule["source"])

    return KnowledgeResult(
        rules=matched_rules,
        facts=list(set(facts)),
        sources=list(set(sources)),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="knowledge-service")
