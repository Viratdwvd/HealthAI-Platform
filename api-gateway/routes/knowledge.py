"""
Knowledge routes — appended to the API gateway.
Add these routes to api-gateway/main.py's knowledge section.

This module is imported in main.py via:
    from routes.knowledge import router as knowledge_router
    app.include_router(knowledge_router, prefix="/api/v1")
"""

from __future__ import annotations
import sys
sys.path.insert(0, "/app/shared")

import httpx
from fastapi import APIRouter, Depends, HTTPException

from models.schemas import KnowledgeRequest
from middleware.auth import TokenData, get_current_user

router = APIRouter(tags=["knowledge"])

KNOWLEDGE_SERVICE_URL = "http://knowledge-service:8004"


@router.post("/knowledge")
async def knowledge_lookup(
    req:  KnowledgeRequest,
    user: TokenData = Depends(get_current_user),
):
    req.tenant_id = user.tenant_id
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(f"{KNOWLEDGE_SERVICE_URL}/lookup", json=req.model_dump())
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Knowledge service unavailable: {exc}")
