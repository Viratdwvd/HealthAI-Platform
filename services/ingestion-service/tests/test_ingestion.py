"""
Unit tests – Ingestion Service
Run with: pytest tests/ -v
"""

import base64
import io
import sys

sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

import pytest


# ─── CSV parser ───────────────────────────────────────────────────────────────

def test_csv_parse_basic():
    from parsers.csv_parser import parse_csv

    csv_bytes = b"name,age,diagnosis\nAlice,45,Hypertension\nBob,62,Diabetes\n"
    blocks = parse_csv(csv_bytes)
    assert len(blocks) >= 1
    assert "Alice" in blocks[0]
    assert "Diabetes" in blocks[0]


def test_csv_parse_empty():
    from parsers.csv_parser import parse_csv

    blocks = parse_csv(b"")
    assert blocks == []


def test_csv_parse_header_only():
    from parsers.csv_parser import parse_csv

    blocks = parse_csv(b"col1,col2,col3\n")
    assert blocks == []


def test_csv_parse_row_grouping():
    from parsers.csv_parser import parse_csv

    rows = ["name,val"] + [f"row{i},{i}" for i in range(120)]
    csv_bytes = "\n".join(rows).encode()
    blocks = parse_csv(csv_bytes, rows_per_block=50)
    assert len(blocks) >= 2  # 120 rows / 50 = at least 2 blocks


# ─── Chunker ──────────────────────────────────────────────────────────────────

def test_chunker_basic():
    from processors.chunker import chunk_text

    text   = " ".join([f"word{i}" for i in range(600)])
    chunks = chunk_text(text, max_tokens=100, overlap=20)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.split()) > 0


def test_chunker_empty_text():
    from processors.chunker import chunk_text

    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunker_short_text_single_chunk():
    from processors.chunker import chunk_text

    short = "Hello world this is a short paragraph."
    chunks = chunk_text(short, max_tokens=200)
    assert len(chunks) == 1
    assert chunks[0] == short


def test_chunker_overlap():
    from processors.chunker import chunk_text

    words  = [f"w{i}" for i in range(50)]
    text   = " ".join(words)
    chunks = chunk_text(text, max_tokens=20, overlap=5)
    # Consecutive chunks should share some words due to overlap
    if len(chunks) >= 2:
        last_words_of_first  = set(chunks[0].split()[-5:])
        first_words_of_second = set(chunks[1].split()[:5])
        assert len(last_words_of_first & first_words_of_second) > 0


# ─── Validator ────────────────────────────────────────────────────────────────

def test_validator_accepts_csv():
    from processors.validator import validate_file
    from models.schemas import FileType

    content = base64.b64encode(b"col1,col2\n1,2\n").decode()
    err = validate_file("data.csv", FileType.CSV, content, max_size_mb=50)
    assert err is None


def test_validator_rejects_bad_extension():
    from processors.validator import validate_file
    from models.schemas import FileType

    content = base64.b64encode(b"some data").decode()
    err = validate_file("data.xlsx", FileType.CSV, content)
    assert err is not None
    assert "xlsx" in err.lower()


def test_validator_rejects_oversized():
    from processors.validator import validate_file
    from models.schemas import FileType

    big = base64.b64encode(b"x" * (2 * 1024 * 1024)).decode()   # 2 MB
    err = validate_file("data.csv", FileType.CSV, big, max_size_mb=1)
    assert err is not None
    assert "size" in err.lower()


def test_validator_rejects_invalid_base64():
    from processors.validator import validate_file
    from models.schemas import FileType

    err = validate_file("data.csv", FileType.CSV, "not!!valid==base64!!", max_size_mb=50)
    assert err is not None


def test_validator_rejects_pdf_without_magic():
    from processors.validator import validate_file
    from models.schemas import FileType

    content = base64.b64encode(b"this is not a pdf").decode()
    err = validate_file("report.pdf", FileType.PDF, content)
    assert err is not None
    assert "PDF" in err
