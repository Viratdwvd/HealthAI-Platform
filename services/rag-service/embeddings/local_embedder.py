"""
Free Local Embedder using sentence-transformers
------------------------------------------------
Runs 100% on your CPU/GPU – no API key, no cost, no internet after first download.

Models (auto-downloaded on first run, ~90MB each):
  • all-MiniLM-L6-v2    – fast, 384 dims, great for most uses  ← DEFAULT
  • all-mpnet-base-v2   – better quality, 768 dims, slower
  • paraphrase-MiniLM-L3-v2 – tiny, 384 dims, fastest

Change model via EMBEDDING_MODEL env var:
  EMBEDDING_MODEL=all-MiniLM-L6-v2
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from utils.logger import get_logger

log = get_logger(__name__)

# Default to the best free local model
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Dimension map – used to auto-configure Qdrant collection
MODEL_DIMS = {
    "all-MiniLM-L6-v2":           384,
    "all-mpnet-base-v2":           768,
    "paraphrase-MiniLM-L3-v2":    384,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
    "multi-qa-MiniLM-L6-cos-v1":  384,
}


class LocalEmbedder:
    """
    Wraps sentence-transformers for async, cached, batched embedding.
    Model is loaded once and kept in memory.
    Thread-safe via a dedicated ThreadPoolExecutor.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model      = None          # lazy-loaded on first call
        self._executor   = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embedder")
        self._lock       = threading.Lock()
        self._cache:     dict[str, List[float]] = {}
        self.dim         = MODEL_DIMS.get(model_name, 384)

    def _load_model(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            log.info("loading_embedding_model", model=self._model_name,
                     note="Downloading ~90MB on first run, cached after")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            # Update dim from actual model
            self.dim = self._model.get_sentence_embedding_dimension()
            log.info("embedding_model_loaded", model=self._model_name, dim=self.dim)

    def _encode_sync(self, texts: List[str]) -> List[List[float]]:
        """Runs in thread pool – blocks, but doesn't block the event loop."""
        self._load_model()
        embeddings = self._model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,   # cosine similarity works correctly
        )
        return embeddings.tolist()

    # ── Public async API ──────────────────────────────────────────────────────

    async def embed_one(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds texts with local caching – never re-embeds the same string."""
        results:          List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices: List[int] = []

        for i, text in enumerate(texts):
            key = _cache_key(text)
            if key in self._cache:
                results[i] = self._cache[key]
            else:
                uncached_indices.append(i)

        if uncached_indices:
            batch  = [texts[i] for i in uncached_indices]
            loop   = asyncio.get_running_loop()
            vecs   = await loop.run_in_executor(self._executor, self._encode_sync, batch)
            for idx, vec in zip(uncached_indices, vecs):
                self._cache[_cache_key(texts[idx])] = vec
                results[idx] = vec

        return results   # type: ignore


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


# ── Module-level singleton ─────────────────────────────────────────────────────

_embedder: Optional[LocalEmbedder] = None


def get_embedder(model_name: str = DEFAULT_MODEL) -> LocalEmbedder:
    """Return the shared embedder instance (created once)."""
    global _embedder
    if _embedder is None:
        _embedder = LocalEmbedder(model_name)
    return _embedder
