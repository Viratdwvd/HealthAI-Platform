"""
Embedder – FREE LOCAL VERSION
-------------------------------
Uses sentence-transformers running entirely on your machine.
No API key. No internet. No cost.

Model: BAAI/bge-small-en-v1.5
  - 384-dimensional embeddings
  - ~130MB download (once)
  - Runs on CPU, ~50ms per batch
  - Very high quality for English text
"""

from __future__ import annotations
import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import List

_MODEL = None   # lazy-loaded on first call
_executor = ThreadPoolExecutor(max_workers=2)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384   # matches this model's output size


def _load_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        print(f"⏳ Loading embedding model {MODEL_NAME} (one-time ~30s download)...")
        _MODEL = SentenceTransformer(MODEL_NAME)
        print(f"✅ Embedding model loaded — {EMBEDDING_DIM}d vectors")
    return _MODEL


def _embed_sync(texts: List[str]) -> List[List[float]]:
    """Run embedding synchronously (called in thread pool)."""
    model = _load_model()
    # BGE models work better with a query prefix for retrieval
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


class Embedder:
    """Local sentence-transformers embedder — completely free."""

    def __init__(self, api_key: str = "", model: str = MODEL_NAME) -> None:
        # api_key is ignored — kept for interface compatibility
        self._cache: dict[str, List[float]] = {}

    async def embed_one(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        uncached: list[int] = []
        results: list[List[float] | None] = [None] * len(texts)

        for i, t in enumerate(texts):
            key = _cache_key(t)
            if key in self._cache:
                results[i] = self._cache[key]
            else:
                uncached.append(i)

        if uncached:
            batch = [texts[i] for i in uncached]
            loop  = asyncio.get_running_loop()
            vecs  = await loop.run_in_executor(_executor, _embed_sync, batch)
            for i, vec in zip(uncached, vecs):
                self._cache[_cache_key(texts[i])] = vec
                results[i] = vec

        return results  # type: ignore

    async def close(self) -> None:
        pass  # nothing to close for local model


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()
