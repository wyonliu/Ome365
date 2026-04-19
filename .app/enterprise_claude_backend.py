"""EnterpriseClaudeBackend — Ome365's tenant-scoped implementation of the
Mindos `ModelBackend` abstract defined in:

    packages/mindos/src/mindos/harness/models/base.py  (upstream)

Why this file exists (see Omnity NOTICE 2026-04-19, §3.3):

    Ome365 企业版可以自己实现 EnterpriseClaudeBackend（带 LiteLLM 网关 /
    OpenRouter / 私有部署），只要满足 ModelBackend 抽象即可无缝接入。
    CompletionResult.cache_ttl_used 必须 log —— 不然未来 Anthropic 再动默认
    TTL 你会无感出血。

Design:
- **Tenant-aware audit log.** Every `complete()` call is appended to
  `.app/audit/claude_<tenant>.ndjson` with `cache_ttl_used` + token stats +
  stop_reason. This is the enterprise compliance panel's source of truth.
- **Default TTL = "1h"** to beat Anthropic's 2026-03-06 regression (they
  silently flipped the default from 1h back to 5m).
- **Injectable transport / base URL.** Enterprise installs commonly route
  through LiteLLM / OpenRouter / an internal proxy.
- **Works standalone.** If `mindos.harness` is not importable (pre-W15
  adoption), we fall back to a local shim so this file stays runnable and
  unit-testable. Once Ome365 pins `mindos>=0.x` per Track 3 #15, the shim
  silently drops in favour of the real base classes — no API change.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("ome365.enterprise_claude")

# ---------------------------------------------------------------------------
# Import the real ModelBackend contract from upstream Mindos when available.
# Fall back to a local shim with the exact same shape so Ome365 builds before
# the W15 `mindos.harness` dependency lands.
# ---------------------------------------------------------------------------

try:
    from mindos.harness.models.base import (  # type: ignore[import-not-found]
        CompletionResult,
        ModelBackend,
        TokenStats,
        ToolCallRequest,
    )
    _UPSTREAM_AVAILABLE = True
except ImportError:
    _UPSTREAM_AVAILABLE = False

    @dataclass
    class TokenStats:  # type: ignore[no-redef]
        input: int = 0
        output: int = 0
        cached_read: int = 0
        cached_write: int = 0

        @property
        def total(self) -> int:
            return self.input + self.output

        def add(self, other: "TokenStats") -> None:
            self.input += other.input
            self.output += other.output
            self.cached_read += other.cached_read
            self.cached_write += other.cached_write

    @dataclass
    class ToolCallRequest:  # type: ignore[no-redef]
        id: str
        name: str
        arguments: dict = field(default_factory=dict)

    @dataclass
    class CompletionResult:  # type: ignore[no-redef]
        text: str = ""
        tool_calls: list = field(default_factory=list)
        tokens: TokenStats = field(default_factory=TokenStats)
        stop_reason: str = "end_turn"
        model: str = ""
        cache_ttl_used: str = ""
        raw: dict = field(default_factory=dict)

    class ModelBackend:  # type: ignore[no-redef]
        name: str = "abstract"
        supports_cache: bool = False
        default_cache_ttl: str = "none"

        def complete(
            self,
            *,
            system: str,
            messages: list,
            tools: Optional[list] = None,
            cache_ttl: Optional[str] = None,
            max_tokens: int = 4096,
            temperature: float = 0.7,
        ) -> CompletionResult:
            raise NotImplementedError


# ---------------------------------------------------------------------------
# Enterprise backend
# ---------------------------------------------------------------------------

_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-opus-4-6"


class EnterpriseClaudeBackend(ModelBackend):
    """Ome365 tenant-scoped Claude backend with compliance-grade audit.

    Args:
        api_key: Anthropic key (or gateway key). Falls back to env.
        tenant_id: Tenant slug used for audit log partitioning. Required.
        model: Anthropic model id (default: claude-opus-4-6).
        url: API URL. Override for LiteLLM / OpenRouter / internal gateway.
        env_var: Env var name to read the key from (default ANTHROPIC_API_KEY).
        transport: Test hook `fn(url, payload, headers) -> dict`.
        audit_dir: Directory for ndjson audit logs (default `.app/audit/`).
        default_ttl: Cache TTL sent on every request that doesn't override.
            Defaults to "1h" to beat the 2026-03-06 default-TTL regression.
    """

    name = "enterprise_claude"
    supports_cache = True
    default_cache_ttl = "1h"

    def __init__(
        self,
        *,
        tenant_id: str,
        api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
        url: str = _DEFAULT_URL,
        env_var: str = "ANTHROPIC_API_KEY",
        transport: Optional[Callable[[str, dict, dict], dict]] = None,
        audit_dir: Optional[Path] = None,
        default_ttl: str = "1h",
    ):
        if not tenant_id:
            raise ValueError("tenant_id is required for audit partitioning")
        self.tenant_id = tenant_id
        self.api_key = api_key or os.environ.get(env_var, "")
        self.model = model
        self.url = url
        self._transport = transport
        self.default_cache_ttl = default_ttl
        self._audit_dir = Path(audit_dir) if audit_dir else _default_audit_dir()

    # -- public ----------------------------------------------------------

    def complete(
        self,
        *,
        system: str,
        messages: list,
        tools: Optional[list] = None,
        cache_ttl: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> CompletionResult:
        ttl = cache_ttl or self.default_cache_ttl
        if ttl not in ("none", "5m", "1h"):
            log.warning("unrecognised cache_ttl=%r, falling back to 5m", ttl)
            ttl = "5m"

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": _system_blocks(system, ttl),
            "messages": _normalise_messages(messages),
        }
        if tools:
            payload["tools"] = _tools_with_cache(tools, ttl)

        started = time.time()
        try:
            raw = self._post(payload)
            result = _parse_response(raw, model=self.model, cache_ttl=ttl)
            self._audit(ttl=ttl, result=result, elapsed_ms=_ms(started))
            return result
        except Exception as e:
            # Still audit the failure so panels see cost/failure signals
            err_result = CompletionResult(
                text="",
                stop_reason="error",
                model=self.model,
                cache_ttl_used=ttl,
                raw={"error": str(e), "type": type(e).__name__},
            )
            self._audit(ttl=ttl, result=err_result, elapsed_ms=_ms(started))
            raise

    # -- transport -------------------------------------------------------

    def _post(self, payload: dict) -> dict:
        if self._transport is not None:
            return self._transport(self.url, payload, self._headers())
        if not self.api_key:
            raise RuntimeError(
                "EnterpriseClaudeBackend has no api_key and no injected "
                "transport; set ANTHROPIC_API_KEY or pass transport=...",
            )
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.error("anthropic HTTP %s (tenant=%s): %s",
                      e.code, self.tenant_id, body[:400])
            raise

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    # -- audit -----------------------------------------------------------

    def _audit(self, *, ttl: str, result: CompletionResult, elapsed_ms: int) -> None:
        """Append one line of NDJSON per completion. Never raises."""
        try:
            self._audit_dir.mkdir(parents=True, exist_ok=True)
            path = self._audit_dir / f"claude_{_safe_slug(self.tenant_id)}.ndjson"
            entry = {
                "ts": int(time.time()),
                "tenant": self.tenant_id,
                "model": result.model or self.model,
                "cache_ttl_used": result.cache_ttl_used or ttl,
                "stop_reason": result.stop_reason,
                "elapsed_ms": elapsed_ms,
                "tokens": {
                    "in": result.tokens.input,
                    "out": result.tokens.output,
                    "cached_read": result.tokens.cached_read,
                    "cached_write": result.tokens.cached_write,
                },
            }
            if result.stop_reason == "error":
                entry["error"] = result.raw.get("error")
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:  # audit must never break the request path
            log.debug("audit write failed (tenant=%s): %s", self.tenant_id, e)


# ---------------------------------------------------------------------------
# Helpers — mirror upstream mindos.harness.models.claude so behaviour matches
# ---------------------------------------------------------------------------

def _system_blocks(system: str, ttl: str) -> list[dict]:
    block: dict = {"type": "text", "text": system or ""}
    if ttl != "none":
        block["cache_control"] = {"type": "ephemeral", "ttl": ttl}
    return [block]


def _tools_with_cache(tools: list[dict], ttl: str) -> list[dict]:
    if not tools:
        return tools
    out = [dict(t) for t in tools]
    if ttl != "none":
        out[-1] = dict(out[-1])
        out[-1]["cache_control"] = {"type": "ephemeral", "ttl": ttl}
    return out


def _normalise_messages(messages: list[dict]) -> list[dict]:
    return [dict(m) for m in messages]


def _parse_response(raw: dict, *, model: str, cache_ttl: str) -> CompletionResult:
    text_parts: list[str] = []
    tool_calls: list = []
    for block in raw.get("content", []) or []:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append(ToolCallRequest(
                id=block.get("id", ""),
                name=block.get("name", ""),
                arguments=block.get("input", {}) or {},
            ))

    usage = raw.get("usage", {}) or {}
    tokens = TokenStats(
        input=int(usage.get("input_tokens", 0) or 0),
        output=int(usage.get("output_tokens", 0) or 0),
        cached_read=int(usage.get("cache_read_input_tokens", 0) or 0),
        cached_write=int(usage.get("cache_creation_input_tokens", 0) or 0),
    )

    return CompletionResult(
        text="".join(text_parts),
        tool_calls=tool_calls,
        tokens=tokens,
        stop_reason=raw.get("stop_reason", "end_turn") or "end_turn",
        model=raw.get("model", model),
        cache_ttl_used=cache_ttl,
        raw=raw,
    )


def _default_audit_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here / "audit"


_ALLOWED_SLUG = set("abcdefghijklmnopqrstuvwxyz0123456789-_")


def _safe_slug(s: str) -> str:
    out = []
    for ch in (s or "").strip().lower():
        if ch in _ALLOWED_SLUG:
            out.append(ch)
        elif ch in (" ", ".", "/", ":"):
            out.append("-")
    return ("".join(out).strip("-_") or "unknown")[:64]


def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


# ---------------------------------------------------------------------------
# Smoke test — `python3 enterprise_claude_backend.py`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    def _fake_transport(url: str, payload: dict, headers: dict) -> dict:
        assert payload["system"][0]["cache_control"]["ttl"] == "1h", \
            "expected explicit 1h TTL to beat 03-06 regression"
        return {
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "model": payload["model"],
            "usage": {
                "input_tokens": 12, "output_tokens": 4,
                "cache_read_input_tokens": 0, "cache_creation_input_tokens": 12,
            },
        }

    be = EnterpriseClaudeBackend(
        tenant_id="demo-tenant",
        api_key="sk-fake",
        transport=_fake_transport,
    )
    r = be.complete(system="you are a helpful assistant.", messages=[
        {"role": "user", "content": [{"type": "text", "text": "hi"}]},
    ])
    assert r.text == "ok"
    assert r.cache_ttl_used == "1h"
    assert r.tokens.input == 12
    print(f"ok · upstream_available={_UPSTREAM_AVAILABLE} · "
          f"cache_ttl_used={r.cache_ttl_used} · stop={r.stop_reason}")
