"""
Unit tests – Knowledge Service
Run with: pytest tests/ -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

import pytest
import yaml


SAMPLE_RULES = {
    "rules": [
        {
            "id": "r001",
            "domain": "cardiology",
            "keywords": ["chest pain", "angina"],
            "facts": ["Chest pain may indicate cardiac event."],
            "source": "AHA 2023",
        },
        {
            "id": "r002",
            "domain": "diabetes",
            "keywords": ["blood glucose", "HbA1c"],
            "pattern": "HbA1c\\s*>",
            "facts": ["Elevated HbA1c is diagnostic for diabetes."],
            "source": "ADA 2024",
        },
        {
            "id": "r003",
            "domain": "cardiology",
            "keywords": ["ECG", "arrhythmia"],
            "facts": ["ECG is essential for arrhythmia diagnosis."],
            "source": "ESC 2022",
        },
    ]
}


@pytest.fixture
def rule_engine(tmp_path):
    import asyncio
    from rules.rule_engine import RuleEngine

    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(yaml.dump(SAMPLE_RULES))

    engine = RuleEngine(str(rules_file))
    asyncio.get_event_loop().run_until_complete(engine.load())
    return engine


def test_load_rules(rule_engine):
    assert len(rule_engine) == 3


def test_keyword_match(rule_engine):
    matches = rule_engine.match("Patient reports chest pain")
    assert any(r["id"] == "r001" for r in matches)


def test_regex_match(rule_engine):
    matches = rule_engine.match("Lab shows HbA1c> 7.2")
    assert any(r["id"] == "r002" for r in matches)


def test_no_match(rule_engine):
    matches = rule_engine.match("Patient complains of a headache today")
    assert matches == []


def test_domain_filter(rule_engine):
    """Should only return cardiology rules when domain filter applied."""
    matches = rule_engine.match("ECG shows changes", domains=["cardiology"])
    ids = [r["id"] for r in matches]
    assert "r003" in ids
    assert "r002" not in ids


def test_domain_filter_excludes_all(rule_engine):
    matches = rule_engine.match("chest pain ECG", domains=["oncology"])
    assert matches == []


def test_multiple_matches(rule_engine):
    matches = rule_engine.match("ECG normal, chest pain present, angina suspected")
    ids = [r["id"] for r in matches]
    assert "r001" in ids
    assert "r003" in ids


def test_case_insensitive_keyword(rule_engine):
    matches = rule_engine.match("Patient's CHEST PAIN started yesterday")
    assert any(r["id"] == "r001" for r in matches)


def test_facts_returned(rule_engine):
    matches = rule_engine.match("chest pain")
    assert len(matches) >= 1
    assert "facts" in matches[0]
    assert len(matches[0]["facts"]) > 0
