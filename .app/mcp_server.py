#!/usr/bin/env python3
"""
Ome365 MCP Server — 把你的 vault 变成所有 AI agent 共享的记忆底座。

协议：JSON-RPC 2.0 over stdio，符合 Model Context Protocol 2024-11-05。
零依赖（urllib + json），Python 3.9+ 可跑。不依赖官方 mcp SDK。

对外工具（每个 agent 都能用）：
  - search_vault(query, limit)     · 全文搜索 vault
  - read_doc(path)                 · 读取指定文档
  - list_interviews()              · 列出所有访谈（含分类）
  - recall_memories(query, types)  · 查询 Ome 结构化记忆
  - append_daily(content)          · 追加到今日 Daily（速记）
  - get_dashboard()                · 读取用户今日状态 / 任务 / 日程

启动（stdio）：
  python3 .app/mcp_server.py

Claude Code 注册：
  claude mcp add ome365 -- python3 /Users/wyon/root/Ome365/.app/mcp_server.py

前提：主站 server.py 在 localhost:3650 运行（本 MCP 服务只是转发层）。
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

# ── Config ─────────────────────────────────────────────
BACKEND = os.environ.get("OME365_BACKEND", "http://127.0.0.1:3650")
VAULT = Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()
SERVER_NAME = "ome365"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


# ── HTTP helper ────────────────────────────────────────
def _http(method: str, path: str, body=None, timeout=20):
    url = BACKEND.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    # Bypass system proxy — backend is always local
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Tool implementations ───────────────────────────────
def tool_search_vault(query: str, limit: int = 10) -> str:
    try:
        r = _http("GET", f"/api/search?q={urllib.parse.quote(query)}&limit={int(limit)}")
    except Exception as e:
        return f"Search failed: {e}"
    results = r.get("results", [])
    if not results:
        return f"No matches for '{query}'."
    lines = [f"Found {r.get('total', len(results))} match(es), showing top {len(results)}:\n"]
    for i, it in enumerate(results, 1):
        lines.append(f"{i}. **{it['name']}**  ·  `{it['path']}`  (score {it['score']})")
        snip = (it.get("snippet", "") or "").replace("\n", " ")[:220]
        if snip:
            lines.append(f"   → {snip}")
    return "\n".join(lines)


def tool_read_doc(path: str) -> str:
    # Security: keep reads within the vault; reject absolute paths escaping vault.
    p = (VAULT / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
    try:
        p.relative_to(VAULT)
    except ValueError:
        return f"Refused: path '{path}' is outside the vault."
    if not p.exists() or not p.is_file():
        return f"Not found: {path}"
    try:
        content = p.read_text("utf-8")
    except Exception as e:
        return f"Read failed: {e}"
    rel = str(p.relative_to(VAULT))
    size = len(content)
    if size > 60000:
        content = content[:60000] + f"\n\n…[truncated, total {size} chars]"
    return f"# {rel}  ({size} chars)\n\n{content}"


def tool_list_interviews() -> str:
    try:
        r = _http("GET", "/api/interviews")
    except Exception as e:
        return f"Fetch failed: {e}"
    if not isinstance(r, list):
        return "Unexpected response."
    lines = [f"{len(r)} interview group(s):\n"]
    for g in r:
        files = g.get("files", [])
        lines.append(f"## {g.get('date', '?')}  ({len(files)} files)")
        for f in files[:12]:
            cat = f.get("cat", "?")
            title = f.get("title", "")[:60]
            lines.append(f"  [{cat}] {title}")
        if len(files) > 12:
            lines.append(f"  … +{len(files) - 12} more")
    return "\n".join(lines)


def tool_recall_memories(query: str = "", limit: int = 10, types: str = "") -> str:
    qs = [f"q={urllib.parse.quote(query or '最近')}", f"limit={int(limit)}"]
    if types:
        qs.append(f"types={urllib.parse.quote(types)}")
    try:
        r = _http("GET", "/api/memories?" + "&".join(qs))
    except Exception as e:
        return f"Recall failed: {e}"
    mems = r.get("memories", [])
    if not mems:
        return "No memories matched."
    lines = [f"{len(mems)} memory/memories:"]
    for m in mems:
        t = m.get("type", "?")
        content = (m.get("content") or "")[:200]
        conf = m.get("confidence", "")
        lines.append(f"• [{t}] {content}  ({conf})")
    return "\n".join(lines)


def tool_append_daily(content: str) -> str:
    if not content or not content.strip():
        return "Refused: empty content."
    try:
        # Use the Notes endpoint — goes to today's note, safe to append.
        r = _http("POST", "/api/notes", body={"text": content.strip()})
    except Exception as e:
        return f"Append failed: {e}"
    return f"Appended to today's notes: {r.get('ok', r)}"


def tool_get_dashboard() -> str:
    try:
        r = _http("GET", "/api/dashboard")
    except Exception as e:
        return f"Dashboard failed: {e}"
    today = r.get("today", {})
    tasks = today.get("tasks", [])
    done = sum(1 for t in tasks if t.get("done"))
    lines = [
        f"**{r.get('date')}** (week {r.get('week_number')}, day {r.get('day_number')})",
        f"Quarter theme: {r.get('quarter_theme', '—')}",
        f"Today: {done}/{len(tasks)} tasks done · mood={r.get('today_mood', '—')} energy={r.get('today_energy', '—')} focus={r.get('today_focus', '—')}",
        f"Plan progress: {r.get('plan_pct', 0)}%",
        f"Counts: decisions={r.get('decision_count')}  contacts={r.get('contact_count')}  memories={r.get('memory_count')}",
        "",
        "Open tasks:",
    ]
    for t in tasks[:15]:
        mark = "☑" if t.get("done") else "☐"
        lines.append(f"  {mark} {t.get('text', '').strip()[:90]}")
    return "\n".join(lines)


# ── Tool registry (schema for tools/list) ──────────────
TOOLS = [
    {
        "name": "search_vault",
        "description": "Full-text search across the Ome365 vault (all .md files: journal, decisions, reports, interviews, memories). Use this first when looking for anything the user has written or recorded.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords, space-separated"},
                "limit": {"type": "integer", "default": 10, "description": "Max results (1–50)"},
            },
            "required": ["query"],
        },
        "handler": lambda a: tool_search_vault(a["query"], a.get("limit", 10)),
    },
    {
        "name": "read_doc",
        "description": "Read a single document from the vault by its relative path (e.g. 'TicNote/2026-04-17/xxx.md' or 'Journal/Daily/2026-04-17.md').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault-relative path"},
            },
            "required": ["path"],
        },
        "handler": lambda a: tool_read_doc(a["path"]),
    },
    {
        "name": "list_interviews",
        "description": "List all recorded interviews grouped by date, with category (面试/BU/航道/管理层/外部) and title. Use to discover what interviews exist before reading.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda a: tool_list_interviews(),
    },
    {
        "name": "recall_memories",
        "description": "Query Ome's structured long-term memory (types: fact, episode, skill, relation, preference). Use this for recalling what the user has said/decided/prefers rather than document contents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language query"},
                "limit": {"type": "integer", "default": 10},
                "types": {"type": "string", "description": "Comma-separated: fact,episode,skill,relation,preference"},
            },
        },
        "handler": lambda a: tool_recall_memories(a.get("query", ""), a.get("limit", 10), a.get("types", "")),
    },
    {
        "name": "append_daily",
        "description": "Append a note/reminder/insight to today's notes in Ome365. Use to record something the user just said that they'd want to find later.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The note content (plain text)"},
            },
            "required": ["content"],
        },
        "handler": lambda a: tool_append_daily(a["content"]),
    },
    {
        "name": "get_dashboard",
        "description": "Read the user's current daily dashboard — today's tasks, mood, plan progress, and key counts. Use at the start of a session to understand current state.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda a: tool_get_dashboard(),
    },
]

TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


# ── JSON-RPC dispatch ──────────────────────────────────
def _result(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rid, "error": err}


def handle(msg: dict):
    method = msg.get("method")
    rid = msg.get("id")
    params = msg.get("params") or {}

    # Notifications (no id) — no response
    if rid is None and method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return _result(rid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method == "tools/list":
        tools_public = [
            {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
            for t in TOOLS
        ]
        return _result(rid, {"tools": tools_public})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        t = TOOL_BY_NAME.get(name)
        if not t:
            return _error(rid, -32601, f"Unknown tool: {name}")
        try:
            text = t["handler"](args)
        except KeyError as e:
            return _error(rid, -32602, f"Missing required argument: {e}")
        except Exception as e:
            text = f"Error: {type(e).__name__}: {e}"
        return _result(rid, {
            "content": [{"type": "text", "text": str(text)}],
            "isError": False,
        })

    if method == "ping":
        return _result(rid, {})

    # Unknown method
    if rid is not None:
        return _error(rid, -32601, f"Method not found: {method}")
    return None


# ── stdio loop ─────────────────────────────────────────
def main():
    # Line-delimited JSON on stdin/stdout (Claude Code stdio transport).
    sys.stderr.write(f"[ome365-mcp] started, backend={BACKEND}, vault={VAULT}\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"[ome365-mcp] bad JSON: {e}\n")
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
