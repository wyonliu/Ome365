"""
Entity Registry · Enterprise Entity Graph (EEG) 核心加载器

Ome365 的一级能力：统一企业术语/人名/组织/产品的"常识层"，
让所有下游（ASR 清洗、RAG 检索、Memory、Insights、驾舱渲染）都基于同一事实源。

设计要点：
- 文件系统为真 (`Knowledge/entities/{people,organizations,products,terms}/*.md`)
- frontmatter 承载结构化事实，正文承载自由叙述
- 额外并入 `Contacts/people/*.md` 作为 people 视图（向前兼容）
- 进程内缓存 + mtime 失效（避免每次请求遍历磁盘）
- resolve(text) 用最长优先别名替换做 canonicalization

Author: — & 小安, 2026-04-17
"""

from __future__ import annotations
import re
import time
from pathlib import Path
from typing import Iterable

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover — yaml is already used elsewhere in server.py
    _yaml = None


# ── 路径 ────────────────────────────────────────
def _vault_root() -> Path:
    import os
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


def _entities_dir() -> Path:
    return _vault_root() / "Knowledge" / "entities"


def _people_compat_dir() -> Path:
    return _vault_root() / "Contacts" / "people"


ENTITY_TYPES = ("people", "organizations", "products", "terms")


# ── frontmatter 解析（与 server.py 保持同构，不引入新依赖）────
_FM_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    if _yaml is not None:
        try:
            meta = _yaml.safe_load(raw) or {}
        except Exception:
            meta = {}
    else:
        # minimal fallback: only parse key: value pairs at top level
        meta = {}
        for line in raw.splitlines():
            mm = re.match(r'^([A-Za-z_][\w\-]*)\s*:\s*(.*)$', line)
            if mm:
                meta[mm.group(1)] = mm.group(2).strip()
    return meta if isinstance(meta, dict) else {}, text[m.end():]


# ── 加载单个实体文件 ─────────────────────────────
def _load_entity_file(fp: Path, type_hint: str | None = None) -> dict | None:
    try:
        text = fp.read_text("utf-8")
    except Exception:
        return None
    meta, body = _parse_frontmatter(text)
    if not isinstance(meta, dict):
        return None

    # Accept either explicit id or slug-from-filename
    eid = (meta.get("id") or fp.stem).strip()
    etype = (meta.get("type") or type_hint or "person").strip()
    # Normalize type keys (people/person, organizations/organization, etc.)
    type_norm = {
        "person": "person", "people": "person",
        "organization": "organization", "organizations": "organization", "org": "organization",
        "product": "product", "products": "product",
        "term": "term", "terms": "term",
        "abbr": "abbr",
    }
    etype = type_norm.get(etype, etype)

    aliases = meta.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [a.strip() for a in re.split(r'[,，\n]', aliases) if a.strip()]
    aliases = [str(a).strip() for a in aliases if str(a).strip()]
    # Strip inline comments ("船长  # 口语") if any slipped through yaml
    cleaned = []
    for a in aliases:
        a = re.sub(r'\s*#.*$', '', a).strip()
        if a:
            cleaned.append(a)
    aliases = cleaned

    return {
        "id": eid,
        "type": etype,
        "name": str(meta.get("name") or fp.stem),
        "aliases": aliases,
        "tenant": meta.get("tenant", "longfor"),
        "company": meta.get("company", ""),
        "title": meta.get("title", ""),
        "vendor": meta.get("vendor", ""),
        "category": meta.get("category", ""),
        "parent": meta.get("parent", ""),
        "definition": meta.get("definition", ""),
        "scope": meta.get("scope", ""),
        "confidence": meta.get("confidence", "medium"),
        "evidence": meta.get("evidence", []) or [],
        "relations": meta.get("relations", []) or [],
        "updated_at": str(meta.get("updated_at", "")),
        "body": body.strip(),
        "_file": str(fp),
    }


# ── 全量加载（带缓存）────────────────────────────
_CACHE: dict = {"entities": None, "mtime": 0.0, "asr_rules": None}


def _dir_mtime_max(paths: Iterable[Path]) -> float:
    latest = 0.0
    for p in paths:
        if not p.exists():
            continue
        for f in p.rglob("*.md"):
            try:
                m = f.stat().st_mtime
                if m > latest:
                    latest = m
            except Exception:
                pass
    return latest


def _scan_all() -> list[dict]:
    out: list[dict] = []
    ed = _entities_dir()
    for sub in ENTITY_TYPES:
        d = ed / sub
        if not d.exists():
            continue
        for fp in sorted(d.glob("*.md")):
            e = _load_entity_file(fp, type_hint=sub.rstrip("s"))
            if e:
                out.append(e)

    # 向前兼容：Contacts/people/*.md 作为 people 视图并入
    compat = _people_compat_dir()
    seen_ids = {e["id"] for e in out if e["type"] == "person"}
    seen_names = {e["name"] for e in out if e["type"] == "person"}
    if compat.exists():
        for fp in sorted(compat.glob("*.md")):
            if fp.stem in seen_ids or fp.stem in seen_names:
                continue
            e = _load_entity_file(fp, type_hint="person")
            if e and e["name"] not in seen_names:
                e["type"] = "person"
                out.append(e)
    return out


def all_entities(refresh: bool = False) -> list[dict]:
    mt = _dir_mtime_max([_entities_dir(), _people_compat_dir()])
    if refresh or _CACHE["entities"] is None or mt > _CACHE["mtime"]:
        _CACHE["entities"] = _scan_all()
        _CACHE["mtime"] = mt
        _CACHE["asr_rules"] = None  # 失效
    return _CACHE["entities"]


def get_entity(eid: str) -> dict | None:
    for e in all_entities():
        if e["id"] == eid:
            return e
    return None


def search(q: str, type_filter: str | None = None, tenant: str | None = None) -> list[dict]:
    q = (q or "").strip().lower()
    hits = []
    for e in all_entities():
        if type_filter and e["type"] != type_filter:
            continue
        if tenant and e["tenant"] != tenant:
            continue
        if not q:
            hits.append(e); continue
        names = [e["name"].lower()] + [a.lower() for a in e["aliases"]]
        if any(q in n for n in names):
            hits.append(e)
    return hits


# ── ASR 规则生成 ─────────────────────────────────
def asr_rules(tenant: str | None = None) -> list[dict]:
    """
    从实体 aliases 生成 ASR 规则：alias → canonical name。
    规则按 alias 长度降序，保证最长优先匹配。
    tenant 语义：如果指定，返回该 tenant + public 的规则（public 总是生效）。
    """
    if _CACHE["asr_rules"] is not None and tenant is None:
        return _CACHE["asr_rules"]
    rules: list[dict] = []
    for e in all_entities():
        if tenant and e["tenant"] != tenant and e["tenant"] != "public":
            continue
        for a in e["aliases"]:
            if a == e["name"]:
                continue
            # 跳过纯英文大小写变体（留给程序大小写归一）
            rules.append({
                "from": a,
                "to": e["name"],
                "entity_id": e["id"],
                "entity_type": e["type"],
                "tenant": e["tenant"],
                "confidence": e.get("confidence", "medium"),
            })
    rules.sort(key=lambda r: (-len(r["from"]), r["from"]))
    if tenant is None:
        _CACHE["asr_rules"] = rules
    return rules


# ── resolve：别名 → 规范名 ─────────────────────
def resolve(text: str, tenant: str | None = None) -> dict:
    """
    扫描 text，把所有别名替换为 canonical。
    返回 { canonical: str, matches: [{from, to, entity_id, span:[start,end]}] }
    """
    if not text:
        return {"canonical": text, "matches": []}
    out = text
    matches: list[dict] = []
    for rule in asr_rules(tenant=tenant):
        a = rule["from"]
        if not a or a not in out:
            continue
        idx = 0
        while True:
            pos = out.find(a, idx)
            if pos < 0:
                break
            matches.append({
                "from": a,
                "to": rule["to"],
                "entity_id": rule["entity_id"],
                "span": [pos, pos + len(a)],
            })
            idx = pos + len(a)
        out = out.replace(a, rule["to"])
    return {"canonical": out, "matches": matches}


# ── 列表/过滤 ───────────────────────────────────
def list_entities(type_filter: str | None = None, tenant: str | None = None) -> list[dict]:
    res = all_entities()
    if type_filter:
        res = [e for e in res if e["type"] == type_filter]
    if tenant:
        res = [e for e in res if e["tenant"] == tenant]
    return res


# ── 统计 ────────────────────────────────────────
def stats() -> dict:
    es = all_entities()
    by_type: dict = {}
    by_tenant: dict = {}
    total_aliases = 0
    for e in es:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        by_tenant[e["tenant"]] = by_tenant.get(e["tenant"], 0) + 1
        total_aliases += len(e["aliases"])
    return {
        "total": len(es),
        "by_type": by_type,
        "by_tenant": by_tenant,
        "total_aliases": total_aliases,
        "asr_rules": len(asr_rules()),
        "generated_at": int(time.time()),
    }


if __name__ == "__main__":
    # 自测
    import json
    print(json.dumps(stats(), ensure_ascii=False, indent=2))
    sample = "黄阳总提了一下，让龙丽君和—去跟进下 C1 的事。考拉Code 已经用上了 Venus。"
    print(json.dumps(resolve(sample, tenant="longfor"), ensure_ascii=False, indent=2))
