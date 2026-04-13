"""
YAML-based rule engine.
Rules file schema:
  rules:
    - id: rule_001
      domain: cardiology
      keywords: [chest pain, angina, myocardial]
      pattern: "chest\\s+pain|angina"   # optional regex
      facts:
        - "Chest pain may indicate angina or myocardial infarction."
        - "Recommend ECG within 10 minutes of presentation."
      recommendation: "Refer to cardiology immediately."
      severity: high
      source: "AHA Guidelines 2023"
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml


class RuleEngine:
    def __init__(self, rules_file: str) -> None:
        self._path  = Path(rules_file)
        self._rules: List[Dict[str, Any]] = []

    async def load(self) -> None:
        if not self._path.exists():
            # Write sample rules so the service starts in dev environments
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(_SAMPLE_RULES_YAML)

        with open(self._path) as f:
            data = yaml.safe_load(f)
        self._rules = data.get("rules", [])

    def __len__(self) -> int:
        return len(self._rules)

    def match(self, query: str, domains: List[str] | None = None) -> List[Dict[str, Any]]:
        q_lower  = query.lower()
        matched  = []

        for rule in self._rules:
            # Domain filter
            if domains and rule.get("domain") not in domains:
                continue

            # Keyword matching
            keywords: List[str] = rule.get("keywords", [])
            kw_hit   = any(kw.lower() in q_lower for kw in keywords)

            # Regex matching (optional)
            pattern: str | None = rule.get("pattern")
            re_hit   = bool(re.search(pattern, query, re.IGNORECASE)) if pattern else False

            if kw_hit or re_hit:
                matched.append(rule)

        return matched


# ── Sample rules bundled for dev/demo ─────────────────────────────────────────
_SAMPLE_RULES_YAML = """
rules:
  - id: rule_001
    domain: cardiology
    keywords: [chest pain, angina, myocardial, MI, heart attack]
    pattern: "chest\\\\s+pain|myocardial\\\\s+infarction"
    facts:
      - "Chest pain may indicate angina or myocardial infarction."
      - "Recommend ECG within 10 minutes of presentation."
    recommendation: "Refer to cardiology immediately."
    severity: high
    source: "AHA Guidelines 2023"

  - id: rule_002
    domain: diabetes
    keywords: [blood glucose, HbA1c, hyperglycemia, diabetes, insulin]
    facts:
      - "HbA1c > 6.5% is diagnostic for diabetes mellitus."
      - "Fasting glucose > 126 mg/dL on two occasions is diagnostic."
    recommendation: "Start lifestyle intervention; consider metformin."
    severity: medium
    source: "ADA Standards 2024"

  - id: rule_003
    domain: hypertension
    keywords: [blood pressure, hypertension, systolic, diastolic, BP]
    pattern: "BP\\\\s*>|blood\\\\s+pressure"
    facts:
      - "Stage 1 hypertension: SBP 130–139 or DBP 80–89 mmHg."
      - "Stage 2 hypertension: SBP ≥ 140 or DBP ≥ 90 mmHg."
    recommendation: "DASH diet, exercise, consider ACE inhibitor or ARB."
    severity: medium
    source: "JNC8 Guidelines"

  - id: rule_004
    domain: oncology
    keywords: [tumor, cancer, malignant, biopsy, metastasis, chemotherapy]
    facts:
      - "Biopsy is the gold standard for cancer diagnosis."
      - "Staging determines treatment protocol."
    recommendation: "Refer to oncology MDT."
    severity: high
    source: "NCCN Guidelines 2024"

  - id: rule_005
    domain: medication
    keywords: [drug interaction, contraindication, allergy, adverse effect]
    facts:
      - "Always verify drug-drug interactions before prescribing."
      - "Document patient allergies before any new prescription."
    recommendation: "Use clinical decision support tool for interaction check."
    severity: medium
    source: "Clinical Pharmacology Database"
"""
