"""tests/test_v1_1_2_final.py · v1.1.2 final batch
[decision: 2026-05-09-v1-1-2-final-batch]

Covers: P0 #4 whoami/actors · P1 #7 RBAC · P3 #15 LLM wiki gate · P3 #17 ed25519 sign
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))


# ── P0 #4 · whoami / actors ──────────────────────────────────────────────────


def test_whoami_env_override(tmp_path, monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_eval import router

    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    monkeypatch.setenv("OME365_ACTOR", "wonderwoman")

    app = fastapi.FastAPI()
    app.include_router(router)
    client = TestClient(app)
    r = client.get("/api/eval/whoami")
    assert r.status_code == 200
    assert r.json() == {"actor": "wonderwoman", "source": "env"}


def test_whoami_falls_back_to_default(tmp_path, monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_eval import router

    monkeypatch.delenv("OME365_ACTOR", raising=False)
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))

    app = fastapi.FastAPI()
    app.include_router(router)
    client = TestClient(app)
    r = client.get("/api/eval/whoami")
    assert r.status_code == 200
    assert r.json()["actor"] == "alice"
    assert r.json()["source"] == "default"


def test_actors_endpoint_aggregates_owners(tmp_path, monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_eval import router

    decisions = tmp_path / "Decisions"
    decisions.mkdir()
    for owner in ("alice", "bob", "carol"):
        (decisions / f"{owner}-d.md").write_text(
            f"---\nid: {owner}-d\nstatus: closed\nowner: {owner}\n"
            f"opened: 2026-04-01T00:00:00Z\nclosed: 2026-04-02T00:00:00Z\n---\n",
            "utf-8",
        )
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))

    app = fastapi.FastAPI()
    app.include_router(router)
    r = TestClient(app).get("/api/eval/actors")
    assert r.status_code == 200
    data = r.json()
    assert set(data["actors"]) >= {"alice", "bob", "carol"}
    assert data["count"] >= 3


# ── P1 #7 · RBAC ─────────────────────────────────────────────────────────────


def test_rbac_default_role_contributor(tmp_path):
    from ome365_rbac import role_of, can
    assert role_of("anyone", vault=tmp_path) == "contributor"
    assert can("anyone", "read", vault=tmp_path)
    assert can("anyone", "write", vault=tmp_path)
    assert not can("anyone", "delete", vault=tmp_path)
    assert not can("anyone", "admin", vault=tmp_path)


def test_rbac_owner_can_all(tmp_path):
    pytest.importorskip("yaml")
    from ome365_rbac import can, role_of, require
    cfg = tmp_path / ".ome365"
    cfg.mkdir()
    (cfg / "roles.yml").write_text(
        "default_role: 'viewer'\nmembers:\n  alice: 'owner'\n", "utf-8",
    )
    assert role_of("alice", vault=tmp_path) == "owner"
    for action in ("read", "write", "delete", "admin"):
        assert can("alice", action, vault=tmp_path)
    require("alice", "admin", vault=tmp_path)  # no raise


def test_rbac_viewer_cannot_write(tmp_path):
    pytest.importorskip("yaml")
    from ome365_rbac import can, require
    cfg = tmp_path / ".ome365"
    cfg.mkdir()
    (cfg / "roles.yml").write_text(
        "default_role: 'contributor'\nmembers:\n  carol: 'viewer'\n", "utf-8",
    )
    assert can("carol", "read", vault=tmp_path)
    assert not can("carol", "write", vault=tmp_path)
    with pytest.raises(PermissionError, match="cannot write"):
        require("carol", "write", vault=tmp_path)


def test_rbac_unknown_role_falls_to_contributor(tmp_path):
    pytest.importorskip("yaml")
    from ome365_rbac import role_of
    cfg = tmp_path / ".ome365"
    cfg.mkdir()
    (cfg / "roles.yml").write_text(
        "default_role: 'contributor'\nmembers:\n  weirdo: 'godmode'\n", "utf-8",
    )
    assert role_of("weirdo", vault=tmp_path) == "contributor"


# ── v1.1.25 · RBAC CLI ──────────────────────────────────────────────────────


def test_rbac_cli_help(capsys):
    from ome365_rbac import cli_main as rbac_cli
    rc = rbac_cli([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ome365 rbac" in out
    assert "who" in out and "list" in out and "check" in out


def test_rbac_cli_who(tmp_path, monkeypatch, capsys):
    import json as _json
    pytest.importorskip("yaml")
    from ome365_rbac import cli_main as rbac_cli
    cfg = tmp_path / ".ome365"
    cfg.mkdir()
    (cfg / "roles.yml").write_text(
        "default_role: 'viewer'\nmembers:\n  alice: 'owner'\n", "utf-8",
    )
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = rbac_cli(["who", "alice"])
    assert rc == 0
    parsed = _json.loads(capsys.readouterr().out)
    assert parsed["actor"] == "alice"
    assert parsed["role"] == "owner"
    assert set(parsed["permissions"]) == {"read", "write", "delete", "admin"}


def test_rbac_cli_check_allow_and_deny(tmp_path, monkeypatch, capsys):
    pytest.importorskip("yaml")
    from ome365_rbac import cli_main as rbac_cli
    cfg = tmp_path / ".ome365"
    cfg.mkdir()
    (cfg / "roles.yml").write_text(
        "default_role: 'contributor'\nmembers:\n  carol: 'viewer'\n", "utf-8",
    )
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    # Allow case
    rc = rbac_cli(["check", "carol", "read"])
    assert rc == 0
    assert "allow" in capsys.readouterr().out
    # Deny case (viewer cannot write)
    rc = rbac_cli(["check", "carol", "write"])
    assert rc == 1
    assert "deny" in capsys.readouterr().out


def test_rbac_cli_list_dumps_members(tmp_path, monkeypatch, capsys):
    import json as _json
    pytest.importorskip("yaml")
    from ome365_rbac import cli_main as rbac_cli
    cfg = tmp_path / ".ome365"
    cfg.mkdir()
    (cfg / "roles.yml").write_text(
        "default_role: 'contributor'\nmembers:\n  alice: 'owner'\n  bob: 'viewer'\n",
        "utf-8",
    )
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = rbac_cli(["list"])
    assert rc == 0
    parsed = _json.loads(capsys.readouterr().out)
    assert parsed["default_role"] == "contributor"
    assert parsed["members"] == {"alice": "owner", "bob": "viewer"}


def test_rbac_cli_check_invalid_action(capsys):
    from ome365_rbac import cli_main as rbac_cli
    rc = rbac_cli(["check", "alice", "godmode"])
    assert rc == 2
    assert "action must be" in capsys.readouterr().out


# ── P3 #15 · LLM wiki gate ──────────────────────────────────────────────────


def test_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OME365_WIKI_LLM", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from ome365_wiki import _llm_enabled
    assert _llm_enabled() is False


def test_llm_needs_both_env_and_key(monkeypatch):
    from ome365_wiki import _llm_enabled
    monkeypatch.setenv("OME365_WIKI_LLM", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert _llm_enabled() is False  # opt-in but no key
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    assert _llm_enabled() is True


def test_distill_falls_back_on_no_keys(tmp_path, monkeypatch):
    """Even when LLM enabled, no working SDK → falls back to outcome string."""
    pytest.importorskip("yaml")
    from ome365_eval import DecisionRow
    from ome365_wiki import _distill_claim

    monkeypatch.setenv("OME365_WIKI_LLM", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    fp = tmp_path / "d.md"
    fp.write_text("# fake decision body", "utf-8")
    d = DecisionRow(id="d1", owner="a", status="closed", outcome="shipped X")
    out = _distill_claim(d, fp)
    assert out == "shipped X"  # fell back to outcome


# ── P3 #17 · ed25519 signing ────────────────────────────────────────────────


def test_signing_roundtrip(tmp_path):
    pytest.importorskip("cryptography")
    from ome365_signing import sign, verify
    payload = {"name": "Ome365", "version": "1.1.2", "capabilities": ["a", "b"]}
    signed = sign(payload, vault=tmp_path)
    assert "signature" in signed
    assert signed["signing_alg"] == "ed25519"
    assert "signing_pubkey_b64" in signed
    assert verify(signed) is True


def test_signing_detects_tamper(tmp_path):
    pytest.importorskip("cryptography")
    from ome365_signing import sign, verify
    payload = {"name": "Ome365", "version": "1.1.2"}
    signed = sign(payload, vault=tmp_path)
    # Tamper one field
    signed["version"] = "9.9.9"
    assert verify(signed) is False


def test_signing_key_persisted(tmp_path):
    pytest.importorskip("cryptography")
    from ome365_signing import public_key_b64
    pk1 = public_key_b64(vault=tmp_path)
    pk2 = public_key_b64(vault=tmp_path)
    assert pk1 == pk2  # same key on subsequent calls
    assert (tmp_path / ".ome365" / "keys" / "agent-card.ed25519").exists()


def test_agent_card_endpoint_is_signed(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_a2a import well_known_router
    from ome365_signing import verify

    monkeypatch.setenv("OME365_VAULT", str(tmp_path))

    app = fastapi.FastAPI()
    app.include_router(well_known_router)
    client = TestClient(app)
    r = client.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    card = r.json()
    assert card["signing_alg"] == "ed25519"
    assert card["signature"]
    assert verify(card) is True


# ── v1.1.10 audit endpoint (untested at ship · adding now) ──────────────────


def test_audit_recent_endpoint_empty_vault(tmp_path, monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_eval import router

    monkeypatch.setenv("OME365_VAULT", str(tmp_path))

    app = fastapi.FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/api/eval/audit/recent?days=7&limit=20")
    assert r.status_code == 200
    assert r.json()["events"] == []


def test_audit_recent_endpoint_with_events(tmp_path, monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_audit import log as _audit_log
    from ome365_eval import router

    # Seed audit events
    for action in ("decision.close", "wiki.update", "backup.create"):
        _audit_log(actor="alice", action=action, target_id=f"target-{action}",
                   vault=tmp_path)
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))

    app = fastapi.FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/api/eval/audit/recent?days=1&limit=10")
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) == 3
    actions = {e["action"] for e in events}
    assert actions == {"decision.close", "wiki.update", "backup.create"}


def test_audit_recent_endpoint_respects_limit(tmp_path, monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_audit import log as _audit_log
    from ome365_eval import router

    for i in range(15):
        _audit_log(actor="alice", action="decision.close", target_id=f"d{i}",
                   vault=tmp_path)
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))

    app = fastapi.FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/api/eval/audit/recent?days=1&limit=5")
    assert r.status_code == 200
    assert len(r.json()["events"]) == 5
