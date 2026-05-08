"""
hike_schema.py · Hike v2 schema v0.2 validation
docs/hike.md L1·Entity · v3.6 §六 line 328 · alpha 2026-05-14 ~ 2026-05-19

The five v0.2 fields (all optional · backward compatible):
  - parent_id          — entity hierarchy (org tree / product family / term taxonomy)
  - validity_period    — {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD" | null}
  - external_ids       — cross-system IDs (dingtalk / lark / github / DID)
  - multilingual       — {"zh": "...", "en": "...", "ja": "..."}
  - disambiguation_hint — same-name disambiguation note

Plus the v0.1 base fields (also optional but recommended):
  - id / type / name / aliases / definition / scope / confidence / evidence

Returns list[str] of error messages · empty list = valid.

Usage:
  from hike_schema import validate_entity
  errors = validate_entity(entity_dict)
  if errors:
      print("validation failed:", errors)
"""
from __future__ import annotations
import re
from datetime import date, datetime
from typing import Any


# Valid entity types (v0.1 + v2 roadmap reserves event/decision/milestone/action)
VALID_TYPES = {
    "person", "organization", "product", "term", "abbr",
    # v2 roadmap (L2 Event layer · added 2026-05-14+)
    "event", "decision", "milestone", "action",
}

VALID_CONFIDENCE = {"low", "medium", "high"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DID_RE = re.compile(r"^did:[a-z0-9]+:.+")


def _is_iso_date(s: Any) -> bool:
    # YAML auto-parses dates to datetime.date · accept those as canonical
    if isinstance(s, date):
        return True
    if not isinstance(s, str):
        return False
    if not DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _date_str(s: Any) -> str:
    if isinstance(s, date):
        return s.isoformat()
    return str(s)


def _validate_validity_period(v: Any) -> list[str]:
    errors = []
    if not isinstance(v, dict):
        errors.append("validity_period must be a dict {from, to}")
        return errors
    frm = v.get("from")
    to = v.get("to")
    if frm is not None and not _is_iso_date(frm):
        errors.append(f"validity_period.from must be ISO date YYYY-MM-DD, got {frm!r}")
    if to is not None and not _is_iso_date(to):
        errors.append(f"validity_period.to must be ISO date YYYY-MM-DD or null, got {to!r}")
    if frm is not None and to is not None and _is_iso_date(frm) and _is_iso_date(to):
        if _date_str(to) < _date_str(frm):
            errors.append(f"validity_period.to ({_date_str(to)}) must be >= from ({_date_str(frm)})")
    return errors


def _validate_external_ids(v: Any) -> list[str]:
    errors = []
    if not isinstance(v, dict):
        errors.append("external_ids must be a dict {system: id}")
        return errors
    for k, val in v.items():
        if not isinstance(k, str) or not k:
            errors.append(f"external_ids key must be non-empty string, got {k!r}")
        if not isinstance(val, (str, int)):
            errors.append(f"external_ids[{k!r}] must be string/int, got {type(val).__name__}")
        if k == "did" and isinstance(val, str) and not DID_RE.match(val):
            errors.append(f"external_ids.did must match did:method:id format, got {val!r}")
    return errors


def _validate_multilingual(v: Any) -> list[str]:
    errors = []
    if not isinstance(v, dict):
        errors.append("multilingual must be a dict {lang: name}")
        return errors
    valid_langs = {"zh", "en", "ja", "ko", "fr", "de", "es", "pt", "ru", "ar"}
    for k, val in v.items():
        if not isinstance(k, str) or k not in valid_langs:
            errors.append(f"multilingual key must be ISO 639-1 ({sorted(valid_langs)}), got {k!r}")
        if not isinstance(val, str) or not val.strip():
            errors.append(f"multilingual[{k!r}] must be non-empty string")
    return errors


def _validate_evidence(v: Any) -> list[str]:
    errors = []
    if not isinstance(v, list):
        errors.append("evidence must be a list of citation strings")
        return errors
    for i, item in enumerate(v):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"evidence[{i}] must be non-empty string, got {item!r}")
    return errors


def _validate_relations(v: Any) -> list[str]:
    errors = []
    if not isinstance(v, list):
        errors.append("relations must be a list")
        return errors
    for i, item in enumerate(v):
        if not isinstance(item, dict):
            errors.append(f"relations[{i}] must be a dict")
            continue
        if not item.get("type"):
            errors.append(f"relations[{i}].type required")
        if not item.get("target"):
            errors.append(f"relations[{i}].target required")
    return errors


def validate_entity(entity: dict, *, strict: bool = False) -> list[str]:
    """
    Validate a Hike v2 entity dict against schema v0.2.

    Returns list of error messages · empty = valid.

    Args:
      entity: dict from entity_registry._load_entity_file (or hand-built)
      strict: if True, reject unknown top-level keys (default False · forward-compat)
    """
    errors: list[str] = []

    if not isinstance(entity, dict):
        return ["entity must be a dict"]

    # ── Required-ish: id + type + name (warn if missing · empty allowed for v0.1 compat)
    eid = entity.get("id")
    if eid is not None and (not isinstance(eid, str) or not eid.strip()):
        errors.append("id must be non-empty string when present")

    etype = entity.get("type")
    if etype is not None:
        if not isinstance(etype, str):
            errors.append(f"type must be string, got {type(etype).__name__}")
        elif etype not in VALID_TYPES:
            errors.append(f"type {etype!r} not in valid set {sorted(VALID_TYPES)}")

    name = entity.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        errors.append("name must be non-empty string when present")

    # ── Aliases (list of strings)
    aliases = entity.get("aliases", [])
    if aliases and not isinstance(aliases, list):
        errors.append("aliases must be a list")
    elif isinstance(aliases, list):
        for i, a in enumerate(aliases):
            if not isinstance(a, str):
                errors.append(f"aliases[{i}] must be string, got {type(a).__name__}")

    # ── Confidence (enum)
    conf = entity.get("confidence")
    if conf is not None and conf != "" and conf not in VALID_CONFIDENCE:
        errors.append(f"confidence {conf!r} must be one of {sorted(VALID_CONFIDENCE)}")

    # ── Definition / scope (free-form strings · just type-check)
    for key in ("definition", "scope", "company", "title", "vendor", "category", "parent",
                "disambiguation_hint", "updated_at"):
        v = entity.get(key)
        if v is not None and not isinstance(v, str):
            errors.append(f"{key} must be string, got {type(v).__name__}")

    # ── Evidence (list[str])
    if "evidence" in entity and entity["evidence"]:
        errors.extend(_validate_evidence(entity["evidence"]))

    # ── Relations (list[{type, target, ...}])
    if "relations" in entity and entity["relations"]:
        errors.extend(_validate_relations(entity["relations"]))

    # ── v0.2 五字段 ──────────────────────────────────────────────────────────
    if entity.get("parent_id"):
        if not isinstance(entity["parent_id"], str):
            errors.append("parent_id must be string")

    if entity.get("validity_period"):
        errors.extend(_validate_validity_period(entity["validity_period"]))

    if entity.get("external_ids"):
        errors.extend(_validate_external_ids(entity["external_ids"]))

    if entity.get("multilingual"):
        errors.extend(_validate_multilingual(entity["multilingual"]))

    # ── Strict mode: warn on unknown fields
    if strict:
        known = {
            "id", "type", "name", "aliases", "tenant", "company", "title", "vendor",
            "category", "parent", "definition", "scope", "confidence", "evidence",
            "relations", "updated_at", "parent_id", "validity_period", "external_ids",
            "multilingual", "disambiguation_hint", "body", "_file",
        }
        for k in entity.keys():
            if k not in known:
                errors.append(f"strict: unknown field {k!r}")

    return errors


def is_valid(entity: dict) -> bool:
    """Convenience boolean: True if validate_entity returns empty list."""
    return len(validate_entity(entity)) == 0
