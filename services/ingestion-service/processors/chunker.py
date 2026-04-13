"""
Token-aware text chunker with sliding window overlap.
Uses tiktoken when available; falls back to word-count approximation.
"""

from __future__ import annotations
from typing import List


def _count_tokens(text: str, model: str = "gpt-4o") -> int:
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception:
        return len(text.split())          # crude approximation


def _split_words(text: str) -> List[str]:
    return text.split()


def chunk_text(
    text:         str,
    max_tokens:   int = 512,
    overlap:      int = 64,
) -> List[str]:
    """
    Splits `text` into overlapping chunks of at most `max_tokens` tokens.
    """
    if not text.strip():
        return []

    words = _split_words(text)
    chunks: List[str] = []
    start = 0

    while start < len(words):
        # Grow window until we exceed max_tokens
        end = start
        while end < len(words):
            candidate = " ".join(words[start : end + 1])
            if _count_tokens(candidate) > max_tokens:
                break
            end += 1

        if end == start:        # single word exceeds limit – include it anyway
            end = start + 1

        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)

        # Slide forward, but keep `overlap` words from the tail
        advance = max(1, end - start - overlap)
        start += advance

    return chunks
