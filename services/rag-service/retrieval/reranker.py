"""
Cross-encoder reranker using sentence-transformers.
Scores (query, passage) pairs and returns top-k results.
"""

from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List

from models.schemas import RetrievedChunk


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self._model_name = model_name
        self._model      = None                # lazy-loaded
        self._executor   = ThreadPoolExecutor(max_workers=2)

    def _load(self) -> None:
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)

    def _score_sync(self, query: str, passages: List[str]) -> List[float]:
        self._load()
        pairs  = [(query, p) for p in passages]
        scores = self._model.predict(pairs).tolist()
        return scores

    async def rerank(
        self,
        query:    str,
        chunks:   List[RetrievedChunk],
        top_k:    int = 10,
    ) -> List[RetrievedChunk]:
        if not chunks:
            return []

        loop    = asyncio.get_running_loop()
        scores  = await loop.run_in_executor(
            self._executor,
            self._score_sync,
            query,
            [c.content for c in chunks],
        )

        ranked = sorted(
            zip(chunks, scores),
            key=lambda t: t[1],
            reverse=True,
        )
        result = []
        for chunk, score in ranked[:top_k]:
            chunk.score = float(score)
            result.append(chunk)
        return result
