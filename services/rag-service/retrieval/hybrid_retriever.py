"""
BM25 Hybrid Retriever
---------------------
Combines:
  1. Dense vector search  (Qdrant cosine similarity)
  2. Sparse keyword search (BM25 via rank_bm25)

Results are merged using Reciprocal Rank Fusion (RRF), then optionally
passed to the cross-encoder reranker.

Usage:
    retriever = HybridRetriever(vector_store, bm25_index, embedder)
    chunks    = await retriever.search(query, tenant_id, top_k=10)
"""

from __future__ import annotations

import asyncio
import math
from typing import Any, Dict, List, Optional

from models.schemas import RetrievedChunk
from retrieval.vector_store import VectorStore
from embeddings.embedder import Embedder


class BM25Index:
    """
    In-memory BM25 index over the chunks stored in the vector DB.
    Rebuilt on startup and refreshed periodically.

    In production, replace with Elasticsearch/OpenSearch for scalability.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1       = k1
        self._b        = b
        self._corpus:  List[List[str]]     = []
        self._meta:    List[Dict[str, Any]] = []   # mirrors _corpus rows
        self._idf:     Dict[str, float]    = {}
        self._avgdl:   float               = 0.0

    def fit(self, documents: List[Dict[str, Any]]) -> None:
        """
        Train on a list of dicts with keys: content, chunk_id, source, score.
        """
        self._corpus = [self._tokenise(d["content"]) for d in documents]
        self._meta   = documents
        self._avgdl  = sum(len(t) for t in self._corpus) / max(len(self._corpus), 1)
        self._idf    = self._compute_idf()

    def search(self, query: str, top_k: int = 20) -> List[RetrievedChunk]:
        if not self._corpus:
            return []

        q_tokens = self._tokenise(query)
        scores   = []

        for idx, doc_tokens in enumerate(self._corpus):
            tf_map = {}
            for tok in doc_tokens:
                tf_map[tok] = tf_map.get(tok, 0) + 1

            score = 0.0
            dl    = len(doc_tokens)
            for tok in q_tokens:
                if tok not in self._idf:
                    continue
                tf   = tf_map.get(tok, 0)
                idf  = self._idf[tok]
                num  = tf * (self._k1 + 1)
                den  = tf + self._k1 * (1 - self._b + self._b * dl / self._avgdl)
                score += idf * (num / den)

            scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scores[:top_k]:
            meta = self._meta[idx]
            results.append(
                RetrievedChunk(
                    chunk_id=meta.get("chunk_id", str(idx)),
                    content=meta.get("content",  ""),
                    source=meta.get("source",   ""),
                    score=float(score),
                    metadata=meta.get("metadata", {}),
                )
            )
        return results

    # ── internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        """Lowercase whitespace-split tokenisation (swap for spaCy/NLTK if needed)."""
        return text.lower().split()

    def _compute_idf(self) -> Dict[str, float]:
        n    = len(self._corpus)
        df:  Dict[str, int] = {}
        for tokens in self._corpus:
            for tok in set(tokens):
                df[tok] = df.get(tok, 0) + 1
        return {
            tok: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
            for tok, freq in df.items()
        }


# ─── Hybrid retriever ─────────────────────────────────────────────────────────

class HybridRetriever:
    """
    Combines dense (Qdrant) and sparse (BM25) retrieval using RRF.
    Optionally re-ranks the merged list with a cross-encoder.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index:   BM25Index,
        embedder:     Embedder,
        rrf_k:        int   = 60,           # RRF constant (higher = smoother)
        dense_weight: float = 0.7,          # weight for dense scores
        sparse_weight: float = 0.3,         # weight for BM25 scores
    ) -> None:
        self._vs            = vector_store
        self._bm25          = bm25_index
        self._embedder      = embedder
        self._rrf_k         = rrf_k
        self._dense_weight  = dense_weight
        self._sparse_weight = sparse_weight

    async def search(
        self,
        query:     str,
        tenant_id: str,
        top_k:     int             = 10,
        filters:   Dict[str, Any] | None = None,
        pool_size: int             = 30,   # candidates per retriever
    ) -> List[RetrievedChunk]:
        """
        Returns top_k merged + RRF-scored chunks from both retrievers.
        """
        # Run both retrievers in parallel
        query_vec = await self._embedder.embed_one(query)

        dense_task  = asyncio.create_task(
            self._vs.search(query_vec, tenant_id, top_k=pool_size, filters=filters or {})
        )
        sparse_task = asyncio.create_task(
            asyncio.to_thread(self._bm25.search, query, top_k=pool_size)
        )

        dense_hits, sparse_hits = await asyncio.gather(dense_task, sparse_task)

        # RRF merge
        merged = self._rrf_merge(dense_hits, sparse_hits, top_k=top_k)
        return merged

    def _rrf_merge(
        self,
        dense:  List[RetrievedChunk],
        sparse: List[RetrievedChunk],
        top_k:  int,
    ) -> List[RetrievedChunk]:
        """Reciprocal Rank Fusion."""
        scores: Dict[str, float] = {}
        by_id:  Dict[str, RetrievedChunk] = {}

        for rank, chunk in enumerate(dense, start=1):
            cid = chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + self._dense_weight / (self._rrf_k + rank)
            by_id[cid]  = chunk

        for rank, chunk in enumerate(sparse, start=1):
            cid = chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + self._sparse_weight / (self._rrf_k + rank)
            if cid not in by_id:
                by_id[cid] = chunk

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        result = []
        for cid, rrf_score in ranked:
            chunk = by_id[cid]
            chunk.score = round(rrf_score, 6)
            result.append(chunk)
        return result
