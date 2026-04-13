"""
Unit tests – RAG Service
Run with: pytest tests/ -v
"""

import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

import pytest


# ─── Embedder ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_embedder_cache_hit():
    """Second call with same text should not hit the API."""
    from embeddings.embedder import Embedder

    embedder = Embedder(api_key="fake-key")

    fake_vec = [0.1, 0.2, 0.3]
    # Pre-populate cache
    from embeddings.embedder import _cache_key
    embedder._cache[_cache_key("hello world")] = fake_vec

    result = await embedder.embed_one("hello world")
    assert result == fake_vec


@pytest.mark.asyncio
async def test_embedder_batch_deduplication():
    """Batch should return cached results without extra API calls."""
    from embeddings.embedder import Embedder, _cache_key

    embedder = Embedder(api_key="fake-key")
    embedder._cache[_cache_key("text-a")] = [1.0, 0.0]
    embedder._cache[_cache_key("text-b")] = [0.0, 1.0]

    results = await embedder.embed_batch(["text-a", "text-b"])
    assert results == [[1.0, 0.0], [0.0, 1.0]]


# ─── Reranker ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reranker_empty_chunks():
    from retrieval.reranker import Reranker
    from models.schemas import RetrievedChunk

    reranker = Reranker()
    result   = await reranker.rerank("query", [], top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_reranker_sorts_by_score():
    from retrieval.reranker import Reranker
    from models.schemas import RetrievedChunk

    reranker = Reranker()

    chunks = [
        RetrievedChunk(chunk_id="1", content="Irrelevant content about weather", source="s1", score=0.9),
        RetrievedChunk(chunk_id="2", content="Patient has elevated blood pressure", source="s2", score=0.2),
        RetrievedChunk(chunk_id="3", content="Hypertension treatment protocol", source="s3", score=0.5),
    ]

    # Mock the cross-encoder to return known scores
    with patch.object(reranker, "_score_sync", return_value=[0.1, 0.9, 0.7]):
        result = await reranker.rerank("hypertension", chunks, top_k=2)

    assert len(result) == 2
    assert result[0].chunk_id == "2"    # score 0.9 → top
    assert result[1].chunk_id == "3"    # score 0.7 → second


@pytest.mark.asyncio
async def test_reranker_top_k_truncation():
    from retrieval.reranker import Reranker
    from models.schemas import RetrievedChunk

    reranker = Reranker()
    chunks   = [
        RetrievedChunk(chunk_id=str(i), content=f"content {i}", source="s", score=float(i) / 10)
        for i in range(10)
    ]

    with patch.object(reranker, "_score_sync", return_value=[float(i) / 10 for i in range(10)]):
        result = await reranker.rerank("query", chunks, top_k=3)

    assert len(result) == 3
