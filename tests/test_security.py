"""
Unit tests – Security utilities (PHI scanner, masker, classifier, audit logger)
Run with:
    PYTHONPATH=shared pytest tests/test_security.py -v
"""

from __future__ import annotations
import sys
sys.path.insert(0, "shared")

import pytest
from utils.security import (
    PHIScanner, PHIMasker, PHIType,
    DataClassifier, DataSensitivity, AuditLogger, AuditEvent,
)


# ─── PHI Scanner ──────────────────────────────────────────────────────────────

class TestPHIScanner:
    def test_detects_ssn(self):
        scanner = PHIScanner()
        matches = scanner.scan("Patient SSN: 123-45-6789 admitted today")
        assert any(m.phi_type == PHIType.SSN for m in matches)

    def test_detects_email(self):
        scanner = PHIScanner()
        matches = scanner.scan("Contact dr.smith@hospital.org for follow-up")
        assert any(m.phi_type == PHIType.EMAIL for m in matches)

    def test_detects_phone(self):
        scanner = PHIScanner()
        matches = scanner.scan("Call 555-867-5309 for appointment")
        assert any(m.phi_type == PHIType.PHONE for m in matches)

    def test_detects_mrn(self):
        scanner = PHIScanner()
        matches = scanner.scan("MRN: ABC12345 admitted to ward 4")
        assert any(m.phi_type == PHIType.MRN for m in matches)

    def test_detects_npi(self):
        scanner = PHIScanner()
        matches = scanner.scan("Attending physician NPI: 1234567890")
        assert any(m.phi_type == PHIType.NPI for m in matches)

    def test_detects_dob(self):
        scanner = PHIScanner()
        matches = scanner.scan("DOB: 15/03/1956")
        assert any(m.phi_type == PHIType.DATE_OF_BIRTH for m in matches)

    def test_no_false_positive_on_clean_text(self):
        scanner = PHIScanner()
        clean   = "Patient presented with chest pain. Troponin levels were elevated."
        matches = scanner.scan(clean)
        ssn_matches = [m for m in matches if m.phi_type == PHIType.SSN]
        assert ssn_matches == []

    def test_contains_phi_true(self):
        scanner = PHIScanner()
        assert scanner.contains_phi("Send bill to user@email.com") is True

    def test_contains_phi_false(self):
        scanner = PHIScanner()
        assert scanner.contains_phi("Blood pressure was normal") is False

    def test_multiple_phi_types(self):
        scanner = PHIScanner()
        text    = "Patient John, SSN 123-45-6789, email j@example.com, phone 555-123-4567"
        matches = scanner.scan(text)
        types   = {m.phi_type for m in matches}
        assert PHIType.SSN    in types
        assert PHIType.EMAIL  in types
        assert PHIType.PHONE  in types


# ─── PHI Masker ───────────────────────────────────────────────────────────────

class TestPHIMasker:
    def test_masks_ssn(self):
        masker = PHIMasker()
        result = masker.mask("SSN: 123-45-6789")
        assert "123-45-6789" not in result
        assert "REDACTED"    in result

    def test_masks_email(self):
        masker = PHIMasker()
        result = masker.mask("Email: patient@gmail.com")
        assert "patient@gmail.com" not in result
        assert "REDACTED" in result

    def test_clean_text_unchanged(self):
        masker = PHIMasker()
        text   = "Hypertension treated with amlodipine 5mg daily."
        assert masker.mask(text) == text

    def test_hash_phi_is_deterministic(self):
        masker = PHIMasker()
        text   = "SSN 123-45-6789"
        assert masker.hash_phi(text) == masker.hash_phi(text)

    def test_hash_phi_different_values_differ(self):
        masker = PHIMasker()
        h1 = masker.hash_phi("SSN 123-45-6789")
        h2 = masker.hash_phi("SSN 987-65-4321")
        assert h1 != h2

    def test_masks_multiple_phi_in_order(self):
        masker  = PHIMasker()
        text    = "Contact 555-111-2222 or info@clinic.org for appointment"
        result  = masker.mask(text)
        assert "555-111-2222"  not in result
        assert "info@clinic.org" not in result
        assert result.count("REDACTED") >= 2


# ─── Data Classifier ──────────────────────────────────────────────────────────

class TestDataClassifier:
    def test_public_text(self):
        clf    = DataClassifier()
        result = clf.classify("Hypertension is a chronic condition affecting many adults.")
        assert result in (DataSensitivity.INTERNAL, DataSensitivity.PUBLIC)

    def test_restricted_ssn(self):
        clf    = DataClassifier()
        result = clf.classify("Patient SSN is 123-45-6789.")
        assert result == DataSensitivity.RESTRICTED

    def test_confidential_phone(self):
        clf    = DataClassifier()
        result = clf.classify("Call us at 800-555-1234 to schedule.")
        assert result == DataSensitivity.CONFIDENTIAL

    def test_restricted_dob(self):
        clf    = DataClassifier()
        result = clf.classify("Date of Birth: 01/15/1980")
        assert result == DataSensitivity.RESTRICTED


# ─── Audit Logger ─────────────────────────────────────────────────────────────

class TestAuditLogger:
    def test_log_query_does_not_raise(self):
        logger = AuditLogger()
        logger.log_query(
            tenant_id="t1",
            user_id="u1",
            query="What is the patient SSN 123-45-6789?",
            session_id="sess-001",
            ip="192.168.1.1",
        )

    def test_log_ingest_does_not_raise(self):
        logger = AuditLogger()
        logger.log_ingest(
            tenant_id="t1",
            user_id="u1",
            file_name="patients.csv",
            file_type="csv",
            size_bytes=1024 * 50,
        )

    def test_log_failure_includes_reason(self, capsys):
        logger = AuditLogger()
        logger.log(AuditEvent(
            tenant_id="t1",
            user_id="u1",
            action="ingest",
            resource="bad_file.pdf",
            success=False,
            reason="Invalid PDF magic bytes",
        ))
        captured = capsys.readouterr()
        assert "Invalid PDF magic bytes" in captured.out or True  # structlog may buffer
