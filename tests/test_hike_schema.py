"""tests/test_hike_schema.py · Hike v2 schema v0.2 validator contract tests"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from hike_schema import (  # noqa: E402
    validate_entity,
    is_valid,
    VALID_TYPES,
    VALID_CONFIDENCE,
)


# ── Happy path ───────────────────────────────────────────────────────────────

def test_minimal_entity_valid():
    e = {"id": "alice", "type": "person", "name": "Alice"}
    assert validate_entity(e) == []
    assert is_valid(e)


def test_full_v02_entity_valid():
    e = {
        "id": "alice",
        "type": "person",
        "name": "Alice",
        "aliases": ["A.", "alice-doe"],
        "company": "Acme Corp",
        "title": "CTO",
        "definition": "founding engineer",
        "scope": "engineering",
        "confidence": "high",
        "evidence": ["meeting 2026-04-12", "email thread #42"],
        "relations": [{"type": "works_at", "target": "acme"}],
        "parent_id": "engineering-org",
        "validity_period": {"from": "2024-01-01", "to": None},
        "external_ids": {"github": "alice-doe", "did": "did:web:acme.com:alice"},
        "multilingual": {"zh": "爱丽丝", "en": "Alice"},
        "disambiguation_hint": "engineering · not Alice in finance",
    }
    assert validate_entity(e) == []


# ── Type validation ──────────────────────────────────────────────────────────

def test_unknown_type_rejected():
    e = {"id": "x", "type": "alien", "name": "X"}
    errors = validate_entity(e)
    assert any("type" in err and "valid set" in err for err in errors)


def test_v2_event_type_accepted():
    """v2 roadmap reserves event/decision/milestone/action."""
    for t in ("event", "decision", "milestone", "action"):
        e = {"id": f"x-{t}", "type": t, "name": "X"}
        assert validate_entity(e) == [], f"{t} should be valid"


def test_non_string_type_rejected():
    e = {"id": "x", "type": 42, "name": "X"}
    assert any("must be string" in err for err in validate_entity(e))


# ── Confidence enum ──────────────────────────────────────────────────────────

def test_confidence_enum():
    e = {"id": "x", "type": "person", "name": "X", "confidence": "very-high"}
    errors = validate_entity(e)
    assert any("confidence" in err for err in errors)


def test_confidence_empty_string_ok():
    """Empty confidence should be accepted as 'unset' (v0.1 default behavior)."""
    e = {"id": "x", "type": "person", "name": "X", "confidence": ""}
    assert validate_entity(e) == []


# ── validity_period ──────────────────────────────────────────────────────────

def test_validity_period_must_be_dict():
    e = {"id": "x", "type": "person", "name": "X", "validity_period": "2024"}
    errors = validate_entity(e)
    assert any("validity_period must be a dict" in err for err in errors)


def test_validity_period_iso_dates():
    e = {"id": "x", "type": "person", "name": "X",
         "validity_period": {"from": "2024-13-99", "to": "bad"}}
    errors = validate_entity(e)
    assert any("from" in err for err in errors)
    assert any("to" in err for err in errors)


def test_validity_period_to_before_from():
    e = {"id": "x", "type": "person", "name": "X",
         "validity_period": {"from": "2025-01-01", "to": "2024-01-01"}}
    errors = validate_entity(e)
    assert any(">=" in err for err in errors)


def test_validity_period_open_ended():
    """to: null = still active, valid."""
    e = {"id": "x", "type": "person", "name": "X",
         "validity_period": {"from": "2024-01-01", "to": None}}
    assert validate_entity(e) == []


# ── external_ids ─────────────────────────────────────────────────────────────

def test_external_ids_must_be_dict():
    e = {"id": "x", "type": "person", "name": "X", "external_ids": ["a", "b"]}
    errors = validate_entity(e)
    assert any("external_ids must be a dict" in err for err in errors)


def test_external_ids_did_format():
    e = {"id": "x", "type": "person", "name": "X",
         "external_ids": {"did": "not-a-did"}}
    errors = validate_entity(e)
    assert any("did" in err for err in errors)


def test_external_ids_did_format_valid():
    e = {"id": "x", "type": "person", "name": "X",
         "external_ids": {"did": "did:web:acme.com:alice"}}
    assert validate_entity(e) == []


# ── multilingual ─────────────────────────────────────────────────────────────

def test_multilingual_lang_code_validated():
    e = {"id": "x", "type": "person", "name": "X",
         "multilingual": {"zh": "张三", "klingon": "Tlhingan"}}
    errors = validate_entity(e)
    assert any("klingon" in err or "ISO 639-1" in err for err in errors)


def test_multilingual_empty_value_rejected():
    e = {"id": "x", "type": "person", "name": "X",
         "multilingual": {"zh": ""}}
    errors = validate_entity(e)
    assert any("non-empty" in err for err in errors)


# ── evidence + relations ─────────────────────────────────────────────────────

def test_evidence_must_be_list_of_strings():
    e = {"id": "x", "type": "person", "name": "X", "evidence": [None, 42]}
    errors = validate_entity(e)
    assert len([err for err in errors if "evidence" in err]) >= 2


def test_relations_require_type_and_target():
    e = {"id": "x", "type": "person", "name": "X",
         "relations": [{"type": "works_at"}]}
    errors = validate_entity(e)
    assert any("target required" in err for err in errors)


# ── strict mode ──────────────────────────────────────────────────────────────

def test_strict_mode_rejects_unknown_field():
    e = {"id": "x", "type": "person", "name": "X", "made_up_field": "value"}
    assert validate_entity(e) == []  # non-strict allows
    errors = validate_entity(e, strict=True)
    assert any("made_up_field" in err for err in errors)


# ── Real entity_registry output integration ──────────────────────────────────

def test_real_entity_registry_output_validates():
    """An entity dict produced by entity_registry should pass validation."""
    sample = {
        "id": "grace",
        "type": "person",
        "name": "Grace",
        "aliases": [],
        "tenant": "default",
        "company": "Acme",
        "title": "HR · SSC",
        "vendor": "",
        "category": "team",
        "parent": "",
        "definition": "",
        "scope": "",
        "confidence": "medium",
        "evidence": [],
        "relations": [],
        "updated_at": "",
        "parent_id": "",
        "validity_period": {},
        "external_ids": {},
        "multilingual": {},
        "disambiguation_hint": "",
    }
    assert validate_entity(sample) == []
