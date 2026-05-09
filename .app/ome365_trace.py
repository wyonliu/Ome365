"""
ome365.trace · v1.1 W3 · Per-LLM-call jsonl trace + monthly rollup
[decision: 2026-05-09-trace-sdk-design]

Schema (per docs/strategy/v1.1-implementation-spec.md §四 4.5):
  {ts, actor, skill, decision_id, model, tokens_in, tokens_out, cost_usd,
   output_value_usd, value_attribution, elapsed_ms, tenant}

3 writers (all converge on append-only jsonl):
  · Python SDK:  from ome365_trace import session
  · CLI:         ./ome365 trace add --actor alice --skill X --tokens 100/50 --cost 0.01
  · cron rollup: nightly_monthly_rollup()

No external deps required (stdlib only).
"""
from __future__ import annotations

import atexit
import contextlib
import json
import os
import queue
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional


def _vault_root(vault: Optional[Path] = None) -> Path:
    if vault:
        return Path(vault).resolve()
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


# ── Append-only jsonl write ──────────────────────────────────────────────────


def log(
    *,
    actor: str,
    cost_usd: float,
    skill: Optional[str] = None,
    decision_id: Optional[str] = None,
    model: Optional[str] = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    output_value_usd: Optional[float] = None,
    value_attribution: Optional[str] = None,
    elapsed_ms: Optional[int] = None,
    tenant: str = "default",
    vault: Optional[Path] = None,
    when: Optional[datetime] = None,
) -> Path:
    """
    Append one trace line to vault/Trace/<date>.jsonl.
    Returns the file path written to.
    Schema-stable: keys must match v1.1 impl spec §四 4.5.
    """
    when = when or datetime.now(timezone.utc)
    line = {
        "ts": when.isoformat().replace("+00:00", "Z"),
        "actor": actor,
        "skill": skill,
        "decision_id": decision_id,
        "model": model,
        "tokens_in": int(tokens_in),
        "tokens_out": int(tokens_out),
        "cost_usd": float(cost_usd),
        "output_value_usd": output_value_usd,
        "value_attribution": value_attribution,
        "elapsed_ms": elapsed_ms,
        "tenant": tenant,
    }
    v = _vault_root(vault)
    trace_dir = v / "Trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    fp = trace_dir / f"{when.date().isoformat()}.jsonl"
    with fp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return fp


# ── Async write · queue + daemon thread (P2 #11) ─────────────────────────────


_async_queue: "queue.Queue[Optional[dict]]" = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def _worker_loop():
    """Background thread · drain queue · write each item to its day file."""
    while True:
        item = _async_queue.get()
        try:
            if item is None:
                return  # shutdown sentinel
            try:
                log(**item)
            except Exception:
                pass  # never crash worker
        finally:
            _async_queue.task_done()


def _ensure_worker():
    global _worker_started
    if _worker_started:
        return
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_worker_loop, daemon=True, name="ome365-trace-async")
        t.start()
        _worker_started = True
        atexit.register(_flush_async)


def _flush_async(timeout: float = 5.0):
    """Drain queue and stop worker · called at process exit."""
    if not _worker_started:
        return
    _async_queue.put(None)  # shutdown sentinel
    try:
        _async_queue.join()
    except Exception:
        pass


def log_async(**kwargs) -> None:
    """
    Non-blocking append. Same kwargs as log() · returns immediately.
    Background thread persists to vault/Trace/<date>.jsonl.

    Use under high-QPS server paths to avoid disk fsync blocking the request.
    """
    _ensure_worker()
    _async_queue.put(kwargs)


def queue_size() -> int:
    """Approx pending writes · for /metrics observability."""
    return _async_queue.qsize()


# ── Context manager · auto-time / auto-write ─────────────────────────────────


@dataclass
class _Session:
    actor: str
    skill: Optional[str] = None
    decision_id: Optional[str] = None
    model: Optional[str] = None
    tenant: str = "default"
    vault: Optional[Path] = None
    # Filled by user inside the with block:
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    output_value_usd: Optional[float] = None
    # Auto:
    _t0: float = field(default_factory=time.perf_counter)

    def record_response(self, response) -> None:
        """Auto-extract from anthropic / openai response shapes."""
        if isinstance(response, dict):
            usage = response.get("usage")
        else:
            usage = getattr(response, "usage", None)
        if not usage:
            return

        def _pick(*names: str) -> int:
            for n in names:
                v = usage.get(n) if isinstance(usage, dict) else getattr(usage, n, None)
                if v is not None:
                    return int(v)
            return 0

        self.tokens_in = _pick("input_tokens", "prompt_tokens")
        self.tokens_out = _pick("output_tokens", "completion_tokens")


@contextlib.contextmanager
def session(
    actor: str,
    *,
    skill: Optional[str] = None,
    decision_id: Optional[str] = None,
    model: Optional[str] = None,
    tenant: str = "default",
    vault: Optional[Path] = None,
):
    """
    Context manager · auto-time + auto-write on exit.
    Usage:
        with trace.session("alice", skill="meeting-summarize", decision_id="...") as t:
            response = anthropic.messages.create(...)
            t.record_response(response)
            t.cost_usd = 0.012  # or compute from model + usage
    """
    s = _Session(actor=actor, skill=skill, decision_id=decision_id,
                 model=model, tenant=tenant, vault=vault)
    try:
        yield s
    finally:
        elapsed_ms = int((time.perf_counter() - s._t0) * 1000)
        log(
            actor=s.actor, skill=s.skill, decision_id=s.decision_id, model=s.model,
            tokens_in=s.tokens_in, tokens_out=s.tokens_out, cost_usd=s.cost_usd,
            output_value_usd=s.output_value_usd, elapsed_ms=elapsed_ms,
            tenant=s.tenant, vault=s.vault,
        )


# ── Query (CLI helper) ────────────────────────────────────────────────────────


def query(
    *,
    actor: Optional[str] = None,
    skill: Optional[str] = None,
    decision_id: Optional[str] = None,
    since: Optional[date] = None,
    limit: Optional[int] = None,
    vault: Optional[Path] = None,
) -> list[dict]:
    """grep-style filter over Trace/*.jsonl · returns matching dicts.

    limit=N: keep only the last N matches (newest by ts). Useful for tail-like
    recent inspection. Default None = unlimited.
    """
    v = _vault_root(vault)
    trace_dir = v / "Trace"
    if not trace_dir.exists():
        return []
    out: list[dict] = []
    for fp in sorted(trace_dir.glob("*.jsonl")):
        # Skip monthly summary subfolder
        if fp.parent.name == "monthly":
            continue
        for line in fp.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            if actor and j.get("actor") != actor:
                continue
            if skill is not None and j.get("skill") != skill:
                continue
            if decision_id and j.get("decision_id") != decision_id:
                continue
            if since:
                ts_str = j.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).date()
                except (ValueError, TypeError):
                    continue
                if ts < since:
                    continue
            out.append(j)
    if limit is not None and limit > 0:
        # Sort by ts descending, take newest N, return in chronological order
        try:
            out.sort(key=lambda j: j.get("ts", ""), reverse=True)
        except TypeError:
            pass
        out = list(reversed(out[:limit]))
    return out


# ── Monthly rollup (nightly job) ──────────────────────────────────────────────


def monthly_rollup(
    period: Optional[str] = None,
    *,
    vault: Optional[Path] = None,
) -> Optional[Path]:
    """
    Roll up Trace/<period-YYYY-MM-*.jsonl into Trace/monthly/<period>.summary.json.
    period: 'YYYY-MM' (default = previous month).
    Returns the summary path written, or None if no data.

    Schema:
      {
        period: 'YYYY-MM',
        by_actor: {alice: {requests, cost_usd, value_usd, ...}},
        by_skill: {meeting-summarize: {...}},
        by_decision: {<decision_id>: {...}},
        totals: {requests, cost_usd, value_usd},
        generated_at: ISO,
      }
    """
    v = _vault_root(vault)
    trace_dir = v / "Trace"
    if not trace_dir.exists():
        return None

    if period is None:
        today = date.today()
        if today.month == 1:
            period = f"{today.year - 1}-12"
        else:
            period = f"{today.year}-{today.month - 1:02d}"

    target_files = sorted(trace_dir.glob(f"{period}-*.jsonl"))
    if not target_files:
        return None

    by_actor: dict = defaultdict(lambda: {"requests": 0, "cost_usd": 0.0, "value_usd": 0.0,
                                           "tokens_in": 0, "tokens_out": 0})
    by_skill: dict = defaultdict(lambda: {"requests": 0, "cost_usd": 0.0, "value_usd": 0.0})
    by_decision: dict = defaultdict(lambda: {"requests": 0, "cost_usd": 0.0, "value_usd": 0.0})
    totals = {"requests": 0, "cost_usd": 0.0, "value_usd": 0.0,
              "tokens_in": 0, "tokens_out": 0}

    for fp in target_files:
        for line in fp.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            cost = float(j.get("cost_usd", 0))
            value = float(j.get("output_value_usd") or 0)
            ti, to = int(j.get("tokens_in", 0)), int(j.get("tokens_out", 0))

            actor = j.get("actor") or "(none)"
            by_actor[actor]["requests"] += 1
            by_actor[actor]["cost_usd"] += cost
            by_actor[actor]["value_usd"] += value
            by_actor[actor]["tokens_in"] += ti
            by_actor[actor]["tokens_out"] += to

            skill = j.get("skill") or "(none)"
            by_skill[skill]["requests"] += 1
            by_skill[skill]["cost_usd"] += cost
            by_skill[skill]["value_usd"] += value

            did = j.get("decision_id") or "(none)"
            by_decision[did]["requests"] += 1
            by_decision[did]["cost_usd"] += cost
            by_decision[did]["value_usd"] += value

            totals["requests"] += 1
            totals["cost_usd"] += cost
            totals["value_usd"] += value
            totals["tokens_in"] += ti
            totals["tokens_out"] += to

    summary = {
        "period": period,
        "by_actor": dict(by_actor),
        "by_skill": dict(by_skill),
        "by_decision": dict(by_decision),
        "totals": totals,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    monthly_dir = trace_dir / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)
    out_path = monthly_dir / f"{period}.summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


# ── CLI helper for `./ome365 trace …` ────────────────────────────────────────


def cli_main(argv: list[str]) -> int:
    """`./ome365 trace add | query | rollup` entry point (called from ome365 launcher)."""
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "usage:\n"
            "  ome365 trace add --actor X --cost 0.01 [--skill S] [--decision-id D]\n"
            "                     [--tokens IN/OUT] [--model M] [--tenant T]\n"
            "  ome365 trace query [--actor X] [--skill S] [--decision-id D]\n"
            "                     [--since YYYY-MM-DD] [--limit N]\n"
            "  ome365 trace rollup [--period YYYY-MM]\n"
        )
        return 0

    cmd = argv[0]
    args = {k.lstrip("-").replace("-", "_"): v
            for k, v in zip(argv[1::2], argv[2::2])
            if k.startswith("--")}

    if cmd == "add":
        if "actor" not in args or "cost" not in args:
            print("ERROR: --actor and --cost required", flush=True)
            return 2
        ti, to = 0, 0
        if "tokens" in args and "/" in args["tokens"]:
            ti_s, to_s = args["tokens"].split("/", 1)
            ti, to = int(ti_s), int(to_s)
        path = log(
            actor=args["actor"],
            cost_usd=float(args["cost"]),
            skill=args.get("skill"),
            decision_id=args.get("decision_id"),
            model=args.get("model"),
            tokens_in=ti, tokens_out=to,
            tenant=args.get("tenant", "default"),
        )
        print(f"appended → {path}")
        return 0

    if cmd == "query":
        since = date.fromisoformat(args["since"]) if "since" in args else None
        limit = int(args["limit"]) if "limit" in args else None
        rows = query(
            actor=args.get("actor"),
            skill=args.get("skill"),
            decision_id=args.get("decision_id"),
            since=since,
            limit=limit,
        )
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        print(f"--- {len(rows)} rows", flush=True)
        return 0

    if cmd == "rollup":
        period = args.get("period")
        out = monthly_rollup(period=period)
        if out:
            print(f"rolled up → {out}")
        else:
            print("no data to roll up")
        return 0

    print(f"ERROR: unknown subcommand '{cmd}' (try add | query | rollup)", flush=True)
    return 2


__all__ = ["log", "log_async", "queue_size", "session", "query",
           "monthly_rollup", "cli_main"]
