"""
ome365.notify · v1.1.1 P0 #5 · webhook notifications (Slack / Lark / Teams / generic)
[decision: 2026-05-09-p0-5-notification-webhooks]

Generic webhook with per-platform formatter. stdlib only · no SDK deps.

Events:
  · decision.closed · {id, owner, outcome, value_anchors}
  · wiki.updated    · {category, decision_id, source}
  · budget.warn     · {actor, period, used_usd, budget_usd, pct}

Config (priority order):
  1. env OME365_WEBHOOKS (json string of [{platform, url}, ...])
  2. <vault>/.ome365/notify_webhooks.json (gitignored)
  3. None → silent (no-op)

Sample notify_webhooks.json:
  [
    {"platform": "slack", "url": "https://hooks.slack.com/services/...", "events": ["decision.closed"]},
    {"platform": "lark",  "url": "https://open.feishu.cn/open-apis/bot/v2/hook/..."},
    {"platform": "teams", "url": "https://outlook.office.com/webhook/..."}
  ]
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger("ome365.notify")


# ── Per-platform formatters ──────────────────────────────────────────────────


def _fmt_slack(event: str, payload: dict) -> dict:
    if event == "decision.closed":
        anchors = " ".join(f"`{a}`" for a in (payload.get("value_anchors") or []))
        return {"text": (
            f":white_check_mark: *Decision closed* — `{payload.get('id')}`\n"
            f"_owner: {payload.get('owner')}_  {anchors}\n"
            f">{payload.get('outcome', '')[:200]}"
        )}
    if event == "wiki.updated":
        return {"text": (
            f":books: *Wiki updated* — category `{payload.get('category')}`\n"
            f"distilled from `{payload.get('decision_id')}`"
        )}
    if event == "budget.warn":
        pct = payload.get("pct", 0)
        return {"text": (
            f":warning: *Budget warning* — actor `{payload.get('actor')}` at "
            f"{pct:.0%} of {payload.get('period')} budget "
            f"(${payload.get('used_usd', 0):.2f} / ${payload.get('budget_usd', 0):.2f})"
        )}
    return {"text": f"[{event}] {json.dumps(payload, ensure_ascii=False)}"}


def _fmt_lark(event: str, payload: dict) -> dict:
    """Lark/飞书 simple text format."""
    if event == "decision.closed":
        anchors = ", ".join(payload.get("value_anchors") or [])
        text = (
            f"✅ Decision closed · {payload.get('id')}\n"
            f"owner: {payload.get('owner')} · anchors: {anchors}\n"
            f"{payload.get('outcome', '')}"
        )
    elif event == "wiki.updated":
        text = (
            f"📚 Wiki updated · {payload.get('category')}\n"
            f"distilled from {payload.get('decision_id')}"
        )
    elif event == "budget.warn":
        text = (
            f"⚠ Budget warn · {payload.get('actor')} at "
            f"{payload.get('pct', 0):.0%} of {payload.get('period')} budget"
        )
    else:
        text = f"[{event}] {json.dumps(payload, ensure_ascii=False)}"
    return {"msg_type": "text", "content": {"text": text}}


def _fmt_teams(event: str, payload: dict) -> dict:
    if event == "decision.closed":
        return {"text": (
            f"✅ **Decision closed** — `{payload.get('id')}`  \n"
            f"owner: {payload.get('owner')}  \n"
            f"{payload.get('outcome', '')}"
        )}
    if event == "wiki.updated":
        return {"text": f"📚 **Wiki updated** — category `{payload.get('category')}`"}
    if event == "budget.warn":
        return {"text": (
            f"⚠ **Budget warn** — `{payload.get('actor')}` at "
            f"{payload.get('pct', 0):.0%} of {payload.get('period')} budget"
        )}
    return {"text": f"[{event}] {json.dumps(payload, ensure_ascii=False)}"}


def _fmt_generic(event: str, payload: dict) -> dict:
    """Generic JSON · for custom integrations."""
    return {"event": event, "payload": payload, "source": "ome365"}


FORMATTERS = {
    "slack": _fmt_slack,
    "lark": _fmt_lark,
    "feishu": _fmt_lark,
    "teams": _fmt_teams,
    "generic": _fmt_generic,
}


# ── Config loader ────────────────────────────────────────────────────────────


def _load_webhooks(vault: Optional[Path] = None) -> list[dict]:
    """Returns list of {platform, url, events?} configs · empty list = silent."""
    env_val = os.environ.get("OME365_WEBHOOKS", "").strip()
    if env_val:
        try:
            return json.loads(env_val)
        except json.JSONDecodeError:
            logger.warning("OME365_WEBHOOKS env is not valid JSON · ignored")

    v = Path(vault).resolve() if vault else Path(os.environ.get(
        "OME365_VAULT", Path(__file__).parent.parent
    )).resolve()
    cfg = v / ".ome365" / "notify_webhooks.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text("utf-8"))
            if isinstance(data, list):
                return data
        except (OSError, json.JSONDecodeError):
            logger.warning(f"{cfg} unreadable · ignored")
    return []


# ── Public API · notify(event, payload) fires all matching webhooks ──────────


def notify(
    event: str,
    payload: dict,
    *,
    vault: Optional[Path] = None,
    timeout: float = 3.0,
) -> dict:
    """
    Fire all configured webhooks matching `event`. Non-blocking-style: errors are
    logged and counted, but never raise (so notify is safe in any code path).

    Returns: {"sent": N, "failed": N, "skipped": N, "results": [...]}
    """
    webhooks = _load_webhooks(vault)
    out = {"sent": 0, "failed": 0, "skipped": 0, "results": []}

    for cfg in webhooks:
        platform = (cfg.get("platform") or "generic").lower()
        url = cfg.get("url")
        events_filter = cfg.get("events")  # optional list-allowlist
        if not url:
            out["skipped"] += 1
            continue
        if events_filter and event not in events_filter:
            out["skipped"] += 1
            continue

        formatter = FORMATTERS.get(platform, _fmt_generic)
        body = json.dumps(formatter(event, payload), ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "ome365-notify/1.1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status = r.status
            out["sent"] += 1
            out["results"].append({"platform": platform, "status": status, "url_host": _host(url)})
        except urllib.error.URLError as e:
            out["failed"] += 1
            out["results"].append({"platform": platform, "error": str(e), "url_host": _host(url)})
            logger.warning(f"webhook {platform} ({_host(url)}) failed: {e}")
        except Exception as e:  # noqa: BLE001 - never raise from notify()
            out["failed"] += 1
            out["results"].append({"platform": platform, "error": repr(e), "url_host": _host(url)})
            logger.warning(f"webhook {platform} ({_host(url)}) crashed: {e!r}")
    return out


def _host(url: str) -> str:
    """Strip path/query for log readability."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or "?"
    except Exception:
        return "?"


__all__ = ["notify", "FORMATTERS"]
