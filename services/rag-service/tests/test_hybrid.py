"""
Unit tests – Hybrid Retriever (BM25 + RRF merge)
Run with:
    PYTHONPATH=shared:services/rag-service pytest services/rag-service/tests/test_hybrid.py -v
"""

from __future__ import annotations
import sys
sys.path.insert(0, "shared")
sys.path.insert(0, "services/rag-service")

import pytest
from models.schemas import RetrievedChunk
from retrieval.hybrid_retriever import BM25Index, HybridRetriever


# ─── BM25 Index ───────────────────────────────────────────────────────────────

def make_docs(texts: list[str]) -> list[dict]:
    return [
        {"chunk_id": str(i), "content": t, "source": "test.csv", "metadata": {}}
        for i, t in enumerate(texts)
    ]


class TestBM25Index:
    def test_empty_corpus_returns_empty(self):
        idx = BM25Index()
        assert idx.search("anything") == []

    def test_basic_match(self):
        idx = BM25Index()
        idx.fit(make_docs([
            "chest pain angina cardiac",
            "diabetes mellitus insulin glucose",
            "hypertension blood pressure antihypertensive",
        ]))
        results = idx.search("chest pain")
        assert len(results) > 0
        assert results[0].content == "chest pain angina cardiac"

    def test_top_k_respected(self):
        idx = BM25Index()
        docs = make_docs([f"doc {i} keyword" for i in range(20)])
        idx.fit(docs)
        results = idx.search("keyword", top_k=5)
        assert len(results) == 5

    def test_irrelevant_query_returns_low_scores(self):
        idx = BM25Index()
        idx.fit(make_docs(["chest pain", "blood glucose", "ECG findings"]))
        results = idx.search("zzz_nonexistent_term_xyz")
        for r in results:
            assert r.score == 0.0

    def test_scores_are_non_negative(self):
        idx = BM25Index()
        idx.fit(make_docs(["patient presents with fever", "troponin elevated"]))
        results = idx.search("fever")
        for r in results:
            assert r.score >= 0.0

    def test_ranking_order(self):
        idx = BM25Index()
        idx.fit(make_docs([
            "heart failure ejection fraction reduced",
            "heart heart heart failure failure",   # more term repetition
            "completely unrelated content about weather",
        ]))
        results = idx.search("heart failure")
        assert len(results) >= 2
        assert results[0].score >= results[1].score

    def test_fit_replaces_previous_index(self):
        idx = BM25Index()
        idx.fit(make_docs(["old content about diabetes"]))
        idx.fit(make_docs(["new content about cardiology"]))
        results = idx.search("cardiology")
        assert len(results) > 0
        assert "cardiology" in results[0].content

    def test_chunk_ids_preserved(self):
        idx  = BM25Index()
        docs = make_docs(["alpha beta gamma", "delta epsilon zeta"])
        idx.fit(docs)
        results = idx.search("alpha")
        assert results[0].chunk_id == "0"


# ─── RRF merging ──────────────────────────────────────────────────────────────

def make_chunk(chunk_id: str, content: str = "test", score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=chunk_id, content=content, source="s", score=score)


class TestRRFMerge:
    def _retriever(self) -> HybridRetriever:
        """Return a HybridRetriever with dummy dependencies (not used in merge tests)."""
        return HybridRetriever.__new__(HybridRetriever)

    def setup_method(self):
        r = self._retriever()
        r._rrf_k         = 60
        r._dense_weight  = 0.7
        r._sparse_weight = 0.3
        self.r = r

    def test_rrf_merge_deduplicates(self):
        # Same chunk appears in both dense and sparse lists
        chunk = make_chunk("A")
        dense  = [chunk, make_chunk("B")]
        sparse = [chunk, make_chunk("C")]
        merged = self.r._rrf_merge(dense, sparse, top_k=10)
        ids = [c.chunk_id for c in merged]
        assert ids.count("A") == 1, "Duplicate chunk_id A in merged results"

    def test_rrf_merge_top_k_truncation(self):
        dense  = [make_chunk(str(i)) for i in range(10)]
        sparse = [make_chunk(str(i)) for i in range(10, 20)]
        merged = self.r._rrf_merge(dense, sparse, top_k=5)
        assert len(merged) == 5

    def test_rrf_scores_decrease_monotonically(self):
        dense  = [make_chunk(str(i), score=1.0 - i * 0.1) for i in range(5)]
        sparse = [make_chunk(str(i + 5)) for i in range(5)]
        merged = self.r._rrf_merge(dense, sparse, top_k=10)
        scores = [c.score for c in merged]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_empty_lists(self):
        assert self.r._rrf_merge([], [], top_k=5) == []

    def test_rrf_one_empty_list(self):
        dense  = [make_chunk("X", score=0.9)]
        merged = self.r._rrf_merge(dense, [], top_k=5)
        assert len(merged) == 1
        assert merged[0].chunk_id == "X"

    def test_rrf_dense_weighted_higher(self):
        """Chunk that only appears in dense list should outscore sparse-only chunk
        when dense_weight > sparse_weight and both are rank 1."""
        dense_only  = make_chunk("D")   # rank 1 in dense, absent from sparse
        sparse_only = make_chunk("S")   # rank 1 in sparse, absent from dense

        merged = self.r._rrf_merge([dense_only], [sparse_only], top_k=2)
        ids = [c.chunk_id for c in merged]
        # D gets 0.7/(60+1) score, S gets 0.3/(60+1) — D should rank higher
        assert ids[0] == "D"
