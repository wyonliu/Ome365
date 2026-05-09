"""tests/test_ome365_notify.py · P0 #5 · webhook notify with mock httpd
[decision: 2026-05-09-p0-5-notification-webhooks]
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_notify import (  # noqa: E402
    FORMATTERS,
    _fmt_generic,
    _fmt_lark,
    _fmt_slack,
    _fmt_teams,
    cli_main as notify_cli,
    notify,
)


# ── Per-platform formatter tests ─────────────────────────────────────────────


def test_slack_formatter_decision_closed():
    body = _fmt_slack("decision.closed", {
        "id": "d-1", "owner": "alice", "outcome": "shipped",
        "value_anchors": ["P", "L"],
    })
    assert "Decision closed" in body["text"]
    assert "alice" in body["text"]
    assert "P" in body["text"] and "L" in body["text"]


def test_lark_formatter_msg_type():
    body = _fmt_lark("decision.closed", {"id": "d-2", "owner": "bob", "value_anchors": ["P"]})
    assert body["msg_type"] == "text"
    assert "bob" in body["content"]["text"]


def test_teams_formatter_text_field():
    body = _fmt_teams("decision.closed", {"id": "d-3", "owner": "carol"})
    assert "text" in body
    assert "carol" in body["text"]


def test_generic_formatter_passthrough():
    body = _fmt_generic("custom.event", {"x": 1})
    assert body["event"] == "custom.event"
    assert body["payload"] == {"x": 1}
    assert body["source"] == "ome365"


def test_formatters_have_all_3_events():
    """Each platform must format all 3 supported events without crashing."""
    for plat in ("slack", "lark", "feishu", "teams", "generic"):
        formatter = FORMATTERS[plat]
        for event, payload in [
            ("decision.closed", {"id": "x", "owner": "a", "value_anchors": ["P"]}),
            ("wiki.updated", {"category": "infra", "decision_id": "x"}),
            ("budget.warn", {"actor": "a", "period": "2026-05", "pct": 0.85,
                             "used_usd": 8.5, "budget_usd": 10}),
        ]:
            body = formatter(event, payload)
            assert isinstance(body, dict)
            assert any(k in body for k in ("text", "msg_type", "event"))


# ── Mock HTTP server for end-to-end notify ──────────────────────────────────


class _Capture(BaseHTTPRequestHandler):
    received: list[dict] = []
    status_code: int = 200

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {"_raw": raw.decode("utf-8", errors="replace")}
        _Capture.received.append({"path": self.path, "body": body,
                                  "headers": dict(self.headers)})
        self.send_response(_Capture.status_code)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args, **_kwargs):
        pass


@pytest.fixture
def mock_httpd():
    _Capture.received = []
    _Capture.status_code = 200
    server = HTTPServer(("127.0.0.1", 0), _Capture)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"url": f"http://127.0.0.1:{port}/hook", "server": server}
    server.shutdown()
    server.server_close()


def test_notify_silent_when_no_webhooks(tmp_path, monkeypatch):
    monkeypatch.delenv("OME365_WEBHOOKS", raising=False)
    out = notify("decision.closed", {"id": "d-1"}, vault=tmp_path)
    assert out == {"sent": 0, "failed": 0, "skipped": 0, "results": []}


def test_notify_via_env_config(mock_httpd, monkeypatch, tmp_path):
    cfg = json.dumps([{"platform": "generic", "url": mock_httpd["url"]}])
    monkeypatch.setenv("OME365_WEBHOOKS", cfg)
    out = notify("decision.closed", {"id": "d-x", "owner": "alice", "value_anchors": ["P"]},
                 vault=tmp_path)
    assert out["sent"] == 1
    assert out["failed"] == 0
    assert len(_Capture.received) == 1
    assert _Capture.received[0]["body"]["event"] == "decision.closed"


def test_notify_via_file_config(mock_httpd, tmp_path, monkeypatch):
    monkeypatch.delenv("OME365_WEBHOOKS", raising=False)
    cfg_dir = tmp_path / ".ome365"
    cfg_dir.mkdir()
    (cfg_dir / "notify_webhooks.json").write_text(
        json.dumps([{"platform": "slack", "url": mock_httpd["url"]}]), "utf-8",
    )
    out = notify("decision.closed", {"id": "d-y", "owner": "bob", "value_anchors": ["L"]},
                 vault=tmp_path)
    assert out["sent"] == 1
    assert "Decision closed" in _Capture.received[0]["body"]["text"]


def test_notify_event_filter(mock_httpd, monkeypatch, tmp_path):
    """webhook with `events: ["wiki.updated"]` should skip decision.closed."""
    cfg = json.dumps([{
        "platform": "generic", "url": mock_httpd["url"],
        "events": ["wiki.updated"],
    }])
    monkeypatch.setenv("OME365_WEBHOOKS", cfg)

    out = notify("decision.closed", {"id": "x"}, vault=tmp_path)
    assert out["sent"] == 0
    assert out["skipped"] == 1

    out2 = notify("wiki.updated", {"category": "infra", "decision_id": "x"}, vault=tmp_path)
    assert out2["sent"] == 1


def test_notify_handles_server_500(mock_httpd, monkeypatch, tmp_path):
    """Server returns 500 · notify must record failure but not raise."""
    _Capture.status_code = 500
    cfg = json.dumps([{"platform": "generic", "url": mock_httpd["url"]}])
    monkeypatch.setenv("OME365_WEBHOOKS", cfg)
    out = notify("decision.closed", {"id": "d-fail"}, vault=tmp_path)
    assert out["sent"] == 0
    assert out["failed"] == 1


def test_notify_handles_unreachable(monkeypatch, tmp_path):
    """Bad URL · must fail-silent."""
    cfg = json.dumps([{"platform": "generic", "url": "http://127.0.0.1:1/dead"}])
    monkeypatch.setenv("OME365_WEBHOOKS", cfg)
    out = notify("decision.closed", {"id": "d-1"}, vault=tmp_path, timeout=0.5)
    assert out["sent"] == 0
    assert out["failed"] == 1


def test_notify_invalid_env_json_silent(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("OME365_WEBHOOKS", "{not json")
    out = notify("decision.closed", {"id": "x"}, vault=tmp_path)
    assert out["sent"] == 0
    assert out["failed"] == 0


def test_notify_skips_missing_url(monkeypatch, tmp_path):
    monkeypatch.setenv("OME365_WEBHOOKS", json.dumps([{"platform": "slack"}]))
    out = notify("decision.closed", {"id": "x"}, vault=tmp_path)
    assert out["skipped"] == 1


def test_decision_close_fires_webhook(mock_httpd, monkeypatch, tmp_path):
    """End-to-end: close_decision() should trigger webhook."""
    pytest.importorskip("yaml")
    cfg = json.dumps([{"platform": "generic", "url": mock_httpd["url"]}])
    monkeypatch.setenv("OME365_WEBHOOKS", cfg)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))
    from ome365_decisions import close_decision, create_decision

    create_decision(tmp_path, "Pick X", "alice")
    p = list((tmp_path / "Decisions").glob("*.md"))[0]
    close_decision(tmp_path, p.stem, outcome="shipped", value_anchors=["P", "L"])

    # Webhook should have fired
    decision_events = [r for r in _Capture.received if r["body"].get("event") == "decision.closed"]
    assert len(decision_events) >= 1
    assert decision_events[0]["body"]["payload"]["outcome"] == "shipped"


# ── v1.1.24 notify CLI · list / test ────────────────────────────────────────


def test_notify_cli_help(capsys):
    rc = notify_cli([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ome365 notify" in out
    assert "list" in out and "test" in out


def test_notify_cli_list_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OME365_WEBHOOKS", raising=False)
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = notify_cli(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no webhooks" in out


def test_notify_cli_list_shows_host_only(tmp_path, monkeypatch, capsys):
    """`notify list` must NOT print full URL — security/PII concern."""
    cfg = json.dumps([{"platform": "slack",
                        "url": "https://hooks.slack.com/services/SECRET/TOKEN/HERE"}])
    monkeypatch.setenv("OME365_WEBHOOKS", cfg)
    rc = notify_cli(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "hooks.slack.com" in out
    assert "SECRET" not in out  # full path/token must NOT leak
    assert "TOKEN" not in out


def test_notify_cli_test_fires_event(mock_httpd, monkeypatch, capsys):
    cfg = json.dumps([{"platform": "generic", "url": mock_httpd["url"]}])
    monkeypatch.setenv("OME365_WEBHOOKS", cfg)
    rc = notify_cli(["test", "--event", "decision.close"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"sent": 1' in out
    # Verify the mock server received the event
    assert any(r["body"].get("event") == "decision.close" for r in _Capture.received)


def test_notify_cli_test_when_no_webhooks(tmp_path, monkeypatch, capsys):
    """Empty config returns sent=0 with note · scripts can rely on this."""
    monkeypatch.delenv("OME365_WEBHOOKS", raising=False)
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = notify_cli(["test"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["sent"] == 0
    assert "note" in parsed
