"""
CSV parser – converts raw bytes to a list of row-group text blocks.
Each block is later chunked by the chunker.
"""

from __future__ import annotations
import csv
import io
from typing import List


def parse_csv(raw: bytes, rows_per_block: int = 50) -> List[str]:
    """
    Read a CSV and group rows into text blocks.
    Each block becomes a candidate for embedding.
    """
    text_stream = io.StringIO(raw.decode("utf-8", errors="replace"))
    reader = csv.DictReader(text_stream)

    if not reader.fieldnames:
        return []

    header = ", ".join(reader.fieldnames)
    blocks: List[str] = []
    buffer: List[str] = [f"Columns: {header}"]

    for i, row in enumerate(reader):
        line = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
        buffer.append(line)
        if (i + 1) % rows_per_block == 0:
            blocks.append("\n".join(buffer))
            buffer = [f"Columns: {header}"]  # keep header in each block

    if len(buffer) > 1:              # trailing rows
        blocks.append("\n".join(buffer))

    return blocks
