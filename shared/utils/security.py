"""
shared/utils/security.py
------------------------
HIPAA-oriented security utilities for the healthcare platform.

Provides:
  • PHIScanner  – detects Protected Health Information in text
  • PHIMasker   – masks PHI before logging or storing
  • AuditLogger – structured HIPAA audit trail
  • DataClassifier – classifies sensitivity of a document

These are best-effort helpers. For full HIPAA compliance,
consult a qualified security professional and your legal team.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import get_logger

log = get_logger(__name__)


# ─── PHI patterns ─────────────────────────────────────────────────────────────

class PHIType(str, Enum):
    SSN             = "ssn"
    DATE_OF_BIRTH   = "date_of_birth"
    PHONE           = "phone"
    EMAIL           = "email"
    MRN             = "mrn"             # Medical Record Number
    NPI             = "npi"             # National Provider Identifier
    CREDIT_CARD     = "credit_card"
    IP_ADDRESS      = "ip_address"
    ZIP_CODE        = "zip_code"        # 5-digit US zip (limited context)
    PATIENT_NAME    = "patient_name"    # Heuristic only


_PHI_PATTERNS: List[Tuple[PHIType, re.Pattern]] = [
    (PHIType.SSN,           re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    (PHIType.CREDIT_CARD,   re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    (PHIType.NPI,           re.compile(r"\bNPI[:\s#]+\d{10}\b", re.IGNORECASE)),
    (PHIType.MRN,           re.compile(r"\bMRN[:\s#]+\w{6,12}\b", re.IGNORECASE)),
    (PHIType.PHONE,         re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")),
    (PHIType.EMAIL,         re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    (PHIType.DATE_OF_BIRTH, re.compile(r"\b(?:DOB|Date of Birth|Born)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b", re.IGNORECASE)),
    (PHIType.IP_ADDRESS,    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    (PHIType.ZIP_CODE,      re.compile(r"\b\d{5}(?:-\d{4})?\b")),
]

# Replacement tokens used by the masker
_MASKS: Dict[PHIType, str] = {
    PHIType.SSN:           "[SSN REDACTED]",
    PHIType.CREDIT_CARD:   "[CC REDACTED]",
    PHIType.NPI:           "[NPI REDACTED]",
    PHIType.MRN:           "[MRN REDACTED]",
    PHIType.PHONE:         "[PHONE REDACTED]",
    PHIType.EMAIL:         "[EMAIL REDACTED]",
    PHIType.DATE_OF_BIRTH: "[DOB REDACTED]",
    PHIType.IP_ADDRESS:    "[IP REDACTED]",
    PHIType.ZIP_CODE:      "[ZIP REDACTED]",
    PHIType.PATIENT_NAME:  "[NAME REDACTED]",
}


@dataclass
class PHIMatch:
    phi_type: PHIType
    value:    str
    start:    int
    end:      int


# ─── PHI Scanner ──────────────────────────────────────────────────────────────

class PHIScanner:
    """Detects PHI patterns in text."""

    def scan(self, text: str) -> List[PHIMatch]:
        matches: List[PHIMatch] = []
        for phi_type, pattern in _PHI_PATTERNS:
            for m in pattern.finditer(text):
                matches.append(PHIMatch(
                    phi_type=phi_type,
                    value=m.group(),
                    start=m.start(),
                    end=m.end(),
                ))
        return sorted(matches, key=lambda x: x.start)

    def contains_phi(self, text: str) -> bool:
        return any(True for _ in self._iter_patterns(text))

    def _iter_patterns(self, text: str):
        for _, pattern in _PHI_PATTERNS:
            for m in pattern.finditer(text):
                yield m


# ─── PHI Masker ───────────────────────────────────────────────────────────────

class PHIMasker:
    """Masks PHI in text, replacing matches with typed placeholders."""

    def __init__(self) -> None:
        self._scanner = PHIScanner()

    def mask(self, text: str) -> str:
        matches = self._scanner.scan(text)
        if not matches:
            return text

        # Apply replacements in reverse order to preserve indices
        result = text
        for match in reversed(matches):
            placeholder = _MASKS.get(match.phi_type, "[PHI REDACTED]")
            result = result[: match.start] + placeholder + result[match.end :]
        return result

    def hash_phi(self, text: str) -> str:
        """
        Replace PHI with a deterministic SHA-256 hash.
        Allows de-duplication without exposing the raw value.
        """
        matches = self._scanner.scan(text)
        result  = text
        for match in reversed(matches):
            hashed = hashlib.sha256(match.value.encode()).hexdigest()[:12]
            result = result[: match.start] + f"[PHI:{hashed}]" + result[match.end :]
        return result


# ─── Data classifier ──────────────────────────────────────────────────────────

class DataSensitivity(str, Enum):
    PUBLIC       = "public"
    INTERNAL     = "internal"
    CONFIDENTIAL = "confidential"   # contains PHI
    RESTRICTED   = "restricted"     # highly sensitive PHI (SSN, CC)


class DataClassifier:
    """Classifies the sensitivity level of a document."""

    _HIGH_SENSITIVITY = {PHIType.SSN, PHIType.CREDIT_CARD, PHIType.DATE_OF_BIRTH}

    def classify(self, text: str) -> DataSensitivity:
        scanner = PHIScanner()
        matches = scanner.scan(text)

        if not matches:
            return DataSensitivity.INTERNAL

        types_found = {m.phi_type for m in matches}

        if types_found & self._HIGH_SENSITIVITY:
            return DataSensitivity.RESTRICTED

        return DataSensitivity.CONFIDENTIAL


# ─── HIPAA Audit Logger ───────────────────────────────────────────────────────

@dataclass
class AuditEvent:
    event_id:    str              = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp:   datetime         = field(default_factory=datetime.utcnow)
    tenant_id:   str              = ""
    user_id:     str              = ""
    action:      str              = ""        # "query" | "ingest" | "retrieve" | "export"
    resource:    str              = ""        # file name, query hash, etc.
    sensitivity: DataSensitivity  = DataSensitivity.INTERNAL
    ip_address:  Optional[str]    = None
    session_id:  Optional[str]    = None
    metadata:    Dict[str, Any]   = field(default_factory=dict)
    success:     bool             = True
    reason:      Optional[str]    = None      # failure reason


class AuditLogger:
    """
    HIPAA-compliant audit logger.
    Emits structured log events that can be shipped to a SIEM.
    In production, also write to the query_audit PostgreSQL table.
    """

    def log(self, event: AuditEvent) -> None:
        log.info(
            "audit_event",
            event_id=event.event_id,
            timestamp=event.timestamp.isoformat(),
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            action=event.action,
            resource=event.resource,
            sensitivity=event.sensitivity.value,
            ip_address=event.ip_address,
            session_id=event.session_id,
            success=event.success,
            reason=event.reason,
            **event.metadata,
        )

    def log_query(
        self,
        tenant_id:  str,
        user_id:    str,
        query:      str,
        session_id: Optional[str] = None,
        ip:         Optional[str] = None,
    ) -> None:
        classifier = DataClassifier()
        sensitivity = classifier.classify(query)
        masker     = PHIMasker()
        safe_query = masker.mask(query)

        self.log(AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="query",
            resource=safe_query[:120],
            sensitivity=sensitivity,
            session_id=session_id,
            ip_address=ip,
        ))

    def log_ingest(
        self,
        tenant_id:  str,
        user_id:    str,
        file_name:  str,
        file_type:  str,
        size_bytes: int,
        success:    bool = True,
        reason:     Optional[str] = None,
    ) -> None:
        self.log(AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="ingest",
            resource=file_name,
            sensitivity=DataSensitivity.CONFIDENTIAL,
            success=success,
            reason=reason,
            metadata={"file_type": file_type, "size_bytes": size_bytes},
        ))
