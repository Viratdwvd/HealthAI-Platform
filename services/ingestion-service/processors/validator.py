"""
Pre-ingestion file validation.
Returns an error string or None if validation passes.
"""

from __future__ import annotations
import base64
from typing import Optional

from models.schemas import FileType


ALLOWED_TYPES = {FileType.CSV, FileType.PDF, FileType.JSON}


def validate_file(
    file_name:    str,
    file_type:    FileType,
    content_b64:  str,
    max_size_mb:  int = 50,
) -> Optional[str]:
    """Returns error message string, or None if valid."""

    # Extension check
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in {t.value for t in ALLOWED_TYPES}:
        return f"Unsupported file extension '.{ext}'. Allowed: csv, pdf, json"

    # Type consistency
    if ext != file_type.value:
        return f"File extension '.{ext}' doesn't match declared type '{file_type.value}'"

    # Size check
    try:
        raw = base64.b64decode(content_b64)
    except Exception:
        return "content_b64 is not valid base-64"

    size_mb = len(raw) / (1024 * 1024)
    if size_mb > max_size_mb:
        return f"File size {size_mb:.1f} MB exceeds limit of {max_size_mb} MB"

    # Magic bytes check
    if file_type == FileType.PDF and not raw.startswith(b"%PDF"):
        return "File is declared as PDF but does not have a PDF signature"

    return None
