"""
Tenant Router · 从 HTTP 请求中解析出 tenant_id

优先级（高→低）：
  1. header `X-Ome-Tenant: acme`（API / 调试 / 反代注入）
  2. subdomain：acme.ome.example.com → "acme"
     （过滤保留子域：www/api/ome/static/auth）
  3. path 前缀：/t/acme/... → "acme"（sub-directory 部署场景）
  4. env OME365_DEFAULT_TENANT
  5. 字面量 "default"

subdomain 解析只在 hostname 有 ≥3 段时生效（a.b.c 形式）。
localhost / 127.0.0.1 / IP 地址 跳过 subdomain 解析。
"""
from __future__ import annotations

import os
import re
from typing import Optional


_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_RESERVED_SUBDOMAINS = {"www", "api", "ome", "ome365", "static", "auth", "share", "app"}
_IP_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
_PATH_TENANT_RE = re.compile(r"^/t/([a-z][a-z0-9_-]{1,31})(/|$)")


def resolve_tenant_id(request) -> str:
    """从 starlette Request 里解析 tenant_id。"""
    # 1. header
    try:
        h = request.headers.get("x-ome-tenant")
    except Exception:
        h = None
    if h and _SLUG_RE.match(h):
        return h

    # 2. subdomain
    try:
        host = (request.url.hostname or "").lower()
    except Exception:
        host = ""
    if host and not _IP_RE.match(host) and host not in ("localhost",):
        parts = host.split(".")
        if len(parts) >= 3:
            sub = parts[0]
            if _SLUG_RE.match(sub) and sub not in _RESERVED_SUBDOMAINS:
                return sub

    # 3. path prefix /t/{tid}/
    try:
        path = request.url.path or ""
    except Exception:
        path = ""
    m = _PATH_TENANT_RE.match(path)
    if m:
        return m.group(1)

    # 4. env default
    return os.environ.get("OME365_DEFAULT_TENANT", "default")


def strip_tenant_path(path: str, tid: str) -> str:
    """如果用 path-prefix 模式，把 /t/{tid} 从前缀剥掉再路由。"""
    prefix = f"/t/{tid}"
    if path == prefix:
        return "/"
    if path.startswith(prefix + "/"):
        return path[len(prefix):]
    return path
