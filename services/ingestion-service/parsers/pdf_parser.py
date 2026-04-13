"""
PDF parser – extracts per-page text using PyMuPDF (fitz).
Falls back to pdfplumber if fitz is not available.
"""

from __future__ import annotations
import io
from typing import List


def parse_pdf(raw: bytes) -> List[str]:
    """
    Returns a list of strings, one per page.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=raw, filetype="pdf")
        pages = [page.get_text("text").strip() for page in doc]
        doc.close()
        return [p for p in pages if p]
    except ImportError:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]
    except ImportError:
        pass

    raise RuntimeError(
        "No PDF parsing library available. "
        "Install pymupdf (`pip install pymupdf`) or pdfplumber."
    )
