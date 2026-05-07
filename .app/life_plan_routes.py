"""
Ome365 · Life Plan routes（年度人生规划只读阅读器）

严格遵守「代码 vs 数据绝对分离」：
- 代码里**零 PII**；内容都留在外部 `plan_dir`（机器本地，gitignored）
- live 配置 life_plan_config.json（gitignored）→ 指向 plan_dir
- sample 配置 life_plan_config.sample.json → 指向 .app/life-plan-demo/（公共占位）
- 任何人 clone 这个仓库、不配 live 时，看到的是 demo 内容，不会有个人数据

Auth:
- 所有 /api/life/plan/* 路由不在 DEFAULT_PUBLIC_PATTERNS → middleware 自动门禁
  单人 solo 模式 + 127.0.0.1 监听，天然只有本人可访问

路径安全:
- `rel` 参数必须是 plan_dir 相对路径
- resolve() 后必须 is_relative_to(plan_dir)，拒 `..` / 绝对路径 / 符号链接逃逸

提供端点:
- GET /api/life/plan/hero    → 年/季/周/Day N/「最重要一件事」
- GET /api/life/plan/tree    → 文件树（分组：今日 / 本周 / 核心档 / 归档）
- GET /api/life/plan/doc?rel → 单个文件的 raw markdown + meta
- GET /api/life/plan/today   → 最新 05_今日一页_YYYY-MM-DD.md
- GET /api/life/plan/week    → 最新 06_本周一页_W*.md
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Query


# ── 配置加载（live > sample > fallback） ──────────────────────────
_APP_DIR = Path(__file__).resolve().parent
_LIVE_CFG = _APP_DIR / "life_plan_config.json"
_SAMPLE_CFG = _APP_DIR / "life_plan_config.sample.json"


def _load_config() -> dict:
    """读配置，live 优先，sample 兜底。不存在 live 也不存在 sample 则返回空 dict。"""
    for fp in (_LIVE_CFG, _SAMPLE_CFG):
        if fp.exists():
            try:
                data = json.loads(fp.read_text("utf-8"))
                data.setdefault("_source", fp.name)
                return data
            except Exception as e:
                return {"_source": "error", "_error": str(e), "enabled": False}
    return {"_source": "empty", "enabled": False}


def _resolve_plan_dir(cfg: dict) -> Optional[Path]:
    """
    从 config 取 plan_dir。支持绝对路径、`~` 展开、相对路径（相对 .app）。
    路径不存在返回 None。
    """
    raw = cfg.get("plan_dir") or ""
    if not raw:
        return None
    p = Path(os.path.expanduser(str(raw)))
    if not p.is_absolute():
        p = (_APP_DIR / p).resolve()
    else:
        p = p.resolve()
    if not p.exists() or not p.is_dir():
        return None
    return p


# ── 文件扫描 + 元信息 ────────────────────────────────────────────
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# 文件名类型识别
_TODAY_RE = re.compile(r"05_今日一页_(\d{4}-\d{2}-\d{2})")
_WEEK_RE = re.compile(r"06_本周一页_W(\d+)_(\d{4}-\d{2}-\d{2})")
_CORE_PREFIX_RE = re.compile(r"^(0[0-4])_")  # 00-04 → 核心档


def _parse_frontmatter(text: str) -> dict:
    """抽取 markdown 开头的 YAML frontmatter（简化版）。没 frontmatter 返回 {}。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    meta = {}
    for ln in m.group(1).split("\n"):
        kv = re.match(r"^(\w[\w-]*)\s*:\s*(.*)$", ln)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip("'\"")
    return meta


def _extract_title(text: str, fallback: str) -> str:
    """优先 frontmatter.title → H1 → 文件 stem。"""
    meta = _parse_frontmatter(text)
    if meta.get("title"):
        return meta["title"]
    # 去 frontmatter 后找 H1
    body = _FRONTMATTER_RE.sub("", text, count=1)
    m = _H1_RE.search(body)
    if m:
        return m.group(1).strip()
    return fallback


def _classify(name: str) -> tuple[str, int]:
    """
    按文件名分类，返回 (group, sort_order)：
      - "today" (0): 05_今日一页_*
      - "week"  (1): 06_本周一页_*
      - "core"  (2): 00-04_ 开头
      - "archive" (3): 其他
    """
    if _TODAY_RE.match(name):
        return ("today", 0)
    if _WEEK_RE.match(name):
        return ("week", 1)
    if _CORE_PREFIX_RE.match(name):
        return ("core", 2)
    return ("archive", 3)


def _safe_rel(plan_dir: Path, rel: str) -> Path:
    """
    把 rel 解成 plan_dir 内部的绝对路径。拒越权：
    - 绝对路径 → 403
    - `..` 解出 plan_dir 外 → 403
    - 符号链接指向外部 → 403
    """
    if not rel or ".." in rel.split("/"):
        raise HTTPException(400, "Invalid rel path")
    p = Path(rel)
    if p.is_absolute():
        raise HTTPException(400, "rel must be relative")
    full = (plan_dir / p).resolve()
    # is_relative_to Python 3.9+
    try:
        full.relative_to(plan_dir.resolve())
    except ValueError:
        raise HTTPException(403, "Path escapes plan_dir")
    return full


def _latest_match(plan_dir: Path, pattern: re.Pattern, date_group: int = 1) -> Optional[Path]:
    """
    在 plan_dir 递归扫描匹配 pattern 的文件，返回 date_group 捕获值字典序最大的那个（= 最新日期）。
    """
    best: tuple[str, Path] | None = None
    for md in plan_dir.rglob("*.md"):
        if md.name.startswith(".") or md.name.startswith("_"):
            continue
        m = pattern.search(md.name)
        if not m:
            continue
        key = m.group(date_group)
        if best is None or key > best[0]:
            best = (key, md)
    return best[1] if best else None


# ── Dashboard 解析器：把 05_今日一页.md 变结构化 ──────────────────
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _split_h2_sections(text: str) -> dict:
    """返回 {h2_heading: body_text}，去 frontmatter。"""
    body = _FRONTMATTER_RE.sub("", text, count=1)
    sections: dict[str, str] = {}
    cur_key: str | None = None
    cur_buf: list[str] = []
    for ln in body.split("\n"):
        m = re.match(r"^##\s+(.+?)\s*$", ln)
        if m:
            if cur_key is not None:
                sections[cur_key] = "\n".join(cur_buf).strip()
            cur_key = m.group(1).strip()
            cur_buf = []
        elif cur_key is not None:
            cur_buf.append(ln)
    if cur_key is not None:
        sections[cur_key] = "\n".join(cur_buf).strip()
    return sections


def _find_section(sections: dict, *keywords: str) -> str:
    """在 sections 里找标题含任一 keyword 的段。"""
    for key, body in sections.items():
        for kw in keywords:
            if kw in key:
                return body
    return ""


def _parse_core_three(text: str) -> list[dict]:
    """从 '## 今日核心 3 件事' 抽 1./2./3. 列表。"""
    sections = _split_h2_sections(text)
    body = _find_section(sections, "核心 3", "核心3", "今日核心", "3 件事")
    if not body:
        return []
    items = []
    for m in re.finditer(r"^\s*(\d+)[\.、]\s+(.+?)$", body, re.MULTILINE):
        items.append({"idx": int(m.group(1)), "text": m.group(2).strip()})
    return items[:3]


_TIME_ROW_RE = re.compile(r"^\|\s*([\d]{1,2}:[\d]{2}(?:-[\d]{1,2}:[\d]{2})?)\s*\|\s*(.+?)\s*\|\s*(☐|☑|✅|)\s*\|\s*$")


def _parse_time_blocks(text: str) -> list[dict]:
    """从 '## 时间块' 表格抽行 (time, action)。"""
    sections = _split_h2_sections(text)
    body = _find_section(sections, "时间块", "时间表")
    if not body:
        return []
    blocks = []
    for ln in body.split("\n"):
        m = _TIME_ROW_RE.match(ln.strip())
        if m:
            time = m.group(1).strip()
            action = m.group(2).strip()
            # 跳过表头 "时间" 行
            if time in ("时间",) or action in ("动作",):
                continue
            blocks.append({
                "time": time,
                "action": action,
                "key": f"block_{time}",
            })
    return blocks


def _parse_bullet_list(body: str, prefixes: tuple[str, ...] = ("- ", "* ")) -> list[str]:
    items = []
    for ln in body.split("\n"):
        s = ln.strip()
        for p in prefixes:
            if s.startswith(p):
                items.append(s[len(p):].strip())
                break
    return items


def _parse_redlines(text: str) -> list[str]:
    """'## 红线 · 今日不做' → list of strings。"""
    sections = _split_h2_sections(text)
    body = _find_section(sections, "红线", "不做", "禁忌")
    if not body:
        return []
    return _parse_bullet_list(body)


def _parse_penalties(text: str) -> list[dict]:
    """'## 若破线' → [{trigger, penalty}]，按 '→' 分。"""
    sections = _split_h2_sections(text)
    body = _find_section(sections, "破线", "触发")
    if not body:
        return []
    out = []
    for item in _parse_bullet_list(body):
        if "→" in item:
            trig, pen = item.split("→", 1)
            out.append({"trigger": trig.strip(), "penalty": pen.strip()})
        elif "->" in item:
            trig, pen = item.split("->", 1)
            out.append({"trigger": trig.strip(), "penalty": pen.strip()})
    return out


def _parse_today_theme(text: str) -> str:
    sections = _split_h2_sections(text)
    body = _find_section(sections, "今日主题", "一句话今日", "主题")
    if not body:
        return ""
    # 取第一段非空行
    for ln in body.split("\n"):
        s = ln.strip().lstrip("*").strip()
        if s:
            return s.strip("*").strip()
    return ""


# ── 找指定日期的 05 文件 ──
def _find_today_md_by_date(plan_dir: Path, date_str: str) -> Optional[Path]:
    pattern = re.compile(rf"^05_今日一页_{re.escape(date_str)}\.md$")
    for md in plan_dir.rglob("*.md"):
        if pattern.match(md.name):
            return md
    return None


# ── Progress sidecar（不污染原 md） ──
def _progress_root(plan_dir: Path) -> Path:
    return plan_dir / ".progress"


def _progress_path(plan_dir: Path, date_str: str) -> Path:
    year = date_str[:4]
    return _progress_root(plan_dir) / year / f"{date_str}.json"


def _empty_progress_skeleton(date_str: str) -> dict:
    return {
        "date": date_str,
        "checks": {},        # {"core_0": true, "block_07:30": true, ...}
        "counters": {
            "scan_am": 0, "scan_pm": 0, "scan_eve": 0,
            "active": 0, "touch_head": 0,
        },
        "overrides": {},     # {"block_07:30": {"skip": true} or {"shift": 30}}
        "review": {
            "scores": {
                "rhythm": None, "body": None, "mind": None,
                "work": None, "relation": None, "family": None,
            },
            "answers": {
                "done_today": "",
                "learned": "",
                "tomorrow_one_thing": "",
                "fulfilled_moment": "",
                "proactive_moment": "",
            },
            "submitted_at": None,
        },
    }


def _load_progress(plan_dir: Path, date_str: str) -> dict:
    fp = _progress_path(plan_dir, date_str)
    if not fp.exists():
        return _empty_progress_skeleton(date_str)
    try:
        data = json.loads(fp.read_text("utf-8"))
        # merge 骨架以补齐缺字段
        skel = _empty_progress_skeleton(date_str)
        for k, v in skel.items():
            data.setdefault(k, v)
            if isinstance(v, dict) and isinstance(data.get(k), dict):
                for kk, vv in v.items():
                    data[k].setdefault(kk, vv)
        return data
    except Exception:
        return _empty_progress_skeleton(date_str)


def _save_progress(plan_dir: Path, date_str: str, data: dict) -> None:
    fp = _progress_path(plan_dir, date_str)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_progress(existing: dict, patch: dict) -> dict:
    """Deep merge patch into existing，只覆盖传了的字段。"""
    for k, v in patch.items():
        if k in ("checks", "counters", "overrides") and isinstance(v, dict):
            existing.setdefault(k, {})
            existing[k].update(v)
        elif k == "review" and isinstance(v, dict):
            existing.setdefault("review", _empty_progress_skeleton(existing.get("date", ""))["review"])
            if "scores" in v and isinstance(v["scores"], dict):
                existing["review"]["scores"].update(v["scores"])
            if "answers" in v and isinstance(v["answers"], dict):
                existing["review"]["answers"].update(v["answers"])
            if "submitted_at" in v:
                existing["review"]["submitted_at"] = v["submitted_at"]
        else:
            existing[k] = v
    return existing


# ── Router factory ─────────────────────────────────────────────────
def build_router() -> APIRouter:
    r = APIRouter(prefix="/api/life/plan", tags=["life-plan"])

    # ── /config · 让前端知道当前是 live 还是 demo ──
    @r.get("/config")
    async def cfg_endpoint():
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        return {
            "source": cfg.get("_source", "empty"),
            "enabled": bool(cfg.get("enabled", plan_dir is not None)),
            "plan_dir_exists": plan_dir is not None,
            "plan_start": cfg.get("plan_start"),
            "plan_days": cfg.get("plan_days", 365),
            "label": cfg.get("label", "一年规划"),
        }

    # ── /hero · Day N + 最重要一件事 + 四枚直达 ──
    @r.get("/hero")
    async def hero_endpoint():
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)

        plan_start_str = cfg.get("plan_start")  # "YYYY-MM-DD"
        plan_days = int(cfg.get("plan_days", 365))
        day_num = None
        days_left = None
        progress_pct = None
        if plan_start_str:
            try:
                start = date.fromisoformat(plan_start_str)
                today = date.today()
                day_num = (today - start).days + 1
                days_left = plan_days - day_num
                progress_pct = max(0, min(100, round(day_num / plan_days * 100)))
            except ValueError:
                pass

        # 年 / 季 / 周 / 季度主题
        today = date.today()
        year = today.year
        quarter = (today.month - 1) // 3 + 1
        week_iso = today.isocalendar().week
        quarter_theme = cfg.get("quarter_themes", {}).get(f"Q{quarter}", "")

        # 「最重要一件事」—— 从 02_一年目标.md 第一行 > quote 或 ## 一 下第一段抽取
        most_important = ""
        if plan_dir:
            goals = plan_dir.rglob("02_一年目标*.md")
            goal_file = next(iter(goals), None)
            if goal_file:
                try:
                    raw = goal_file.read_text("utf-8")[:2000]
                    # 优先 frontmatter.one_thing
                    meta = _parse_frontmatter(raw)
                    if meta.get("one_thing"):
                        most_important = meta["one_thing"]
                    else:
                        # 找第一个 > 引言
                        m = re.search(r"^>\s*(.+)$", raw, re.MULTILINE)
                        if m:
                            most_important = m.group(1).strip()
                except Exception:
                    pass

        return {
            "year": year,
            "quarter": quarter,
            "quarter_theme": quarter_theme,
            "week_iso": week_iso,
            "day_num": day_num,
            "days_left": days_left,
            "plan_days": plan_days,
            "progress_pct": progress_pct,
            "most_important": most_important,
            "label": cfg.get("label", "一年规划"),
            "source": cfg.get("_source", "empty"),
        }

    # ── /tree · 分组文件树 ──
    @r.get("/tree")
    async def tree_endpoint():
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            return {"source": cfg.get("_source"), "enabled": False, "groups": {}}

        groups: dict[str, list] = {"today": [], "week": [], "core": [], "archive": []}
        for md in plan_dir.rglob("*.md"):
            if md.name.startswith(".") or md.name.startswith("_"):
                continue
            rel = md.relative_to(plan_dir)
            group, sort_order = _classify(md.name)
            try:
                raw = md.read_text("utf-8")[:1200]
            except Exception:
                raw = ""
            title = _extract_title(raw, md.stem)
            stat = md.stat()
            groups[group].append({
                "rel": str(rel),
                "name": md.name,
                "title": title,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "size": stat.st_size,
            })
        # 各组内：today/week 按 name 倒序（日期最新在前），core 按 name 正序，archive 按 mtime 倒
        groups["today"].sort(key=lambda x: x["name"], reverse=True)
        groups["week"].sort(key=lambda x: x["name"], reverse=True)
        groups["core"].sort(key=lambda x: x["name"])
        groups["archive"].sort(key=lambda x: x["mtime"], reverse=True)

        return {
            "source": cfg.get("_source"),
            "enabled": True,
            "plan_dir_name": plan_dir.name,
            "groups": groups,
        }

    # ── /doc · 读单文件 ──
    @r.get("/doc")
    async def doc_endpoint(rel: str = Query(..., description="plan_dir 内相对路径")):
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            raise HTTPException(404, "Plan dir not configured or missing")
        full = _safe_rel(plan_dir, rel)
        if not full.exists() or not full.is_file():
            raise HTTPException(404, "File not found")
        if full.suffix.lower() != ".md":
            raise HTTPException(400, "Only .md files are readable")
        raw = full.read_text("utf-8")
        meta = _parse_frontmatter(raw)
        title = _extract_title(raw, full.stem)
        return {
            "rel": rel,
            "title": title,
            "meta": meta,
            "raw": raw,
            "mtime": datetime.fromtimestamp(full.stat().st_mtime).isoformat(timespec="seconds"),
        }

    # ── /today · 自动定位最新今日一页 ──
    @r.get("/today")
    async def today_endpoint():
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            raise HTTPException(404, "Plan dir not configured or missing")
        fp = _latest_match(plan_dir, _TODAY_RE)
        if not fp:
            raise HTTPException(404, "No 今日一页 file found (expect 05_今日一页_YYYY-MM-DD.md)")
        rel = str(fp.relative_to(plan_dir))
        raw = fp.read_text("utf-8")
        return {
            "rel": rel,
            "title": _extract_title(raw, fp.stem),
            "raw": raw,
            "mtime": datetime.fromtimestamp(fp.stat().st_mtime).isoformat(timespec="seconds"),
        }

    # ── /week · 自动定位最新本周一页 ──
    @r.get("/week")
    async def week_endpoint():
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            raise HTTPException(404, "Plan dir not configured or missing")
        # 按 W 后的日期排序（date_group=2 是起始日期）
        fp = _latest_match(plan_dir, _WEEK_RE, date_group=2)
        if not fp:
            raise HTTPException(404, "No 本周一页 file found (expect 06_本周一页_W*_YYYY-MM-DD_至_MM-DD.md)")
        rel = str(fp.relative_to(plan_dir))
        raw = fp.read_text("utf-8")
        return {
            "rel": rel,
            "title": _extract_title(raw, fp.stem),
            "raw": raw,
            "mtime": datetime.fromtimestamp(fp.stat().st_mtime).isoformat(timespec="seconds"),
        }

    # ── /snippet · 拉指定文件的某个 H2 小节（供"女儿"/"健康"tab 微升级用） ──
    @r.get("/snippet")
    async def snippet_endpoint(
        rel: str = Query(...),
        heading: str = Query(..., description="H2 标题精确匹配，带'## '"),
        max_lines: int = Query(8, ge=1, le=40),
    ):
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            raise HTTPException(404, "Plan dir not configured or missing")
        full = _safe_rel(plan_dir, rel)
        if not full.exists() or not full.is_file():
            raise HTTPException(404, "File not found")
        raw = full.read_text("utf-8")
        # 拆 H2 段
        lines = raw.split("\n")
        target = heading.strip()
        capture = []
        capturing = False
        for ln in lines:
            s = ln.strip()
            if s.startswith("## "):
                if capturing:
                    break
                # 支持模糊：去掉 "## " 前缀，按 "、" "·" 前取第一段比较
                hdr = s[3:].strip()
                hdr_key = re.split(r"[·、:：]", hdr)[0].strip()
                target_key = re.split(r"[·、:：]", target.lstrip("# ").strip())[0].strip()
                if hdr == target or hdr_key == target_key:
                    capturing = True
                    capture.append(ln)
                continue
            if capturing:
                capture.append(ln)
                if len([x for x in capture if x.strip()]) >= max_lines + 1:
                    break
        if not capture:
            raise HTTPException(404, f"Heading not found: {heading}")
        return {"rel": rel, "heading": heading, "snippet": "\n".join(capture).strip()}

    # ── /dashboard · 把今日 05 md 解析成结构化看板数据 ──
    @r.get("/dashboard")
    async def dashboard_endpoint(date: Optional[str] = Query(None, description="YYYY-MM-DD，不传则用今天")):
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            raise HTTPException(404, "Plan dir not configured or missing")

        date_str = date or datetime.now().strftime("%Y-%m-%d")
        # 校验日期格式
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Invalid date format, expect YYYY-MM-DD")

        md_fp = _find_today_md_by_date(plan_dir, date_str)
        source_rel: Optional[str] = None
        raw = ""
        title = ""
        fallback = False
        if md_fp:
            raw = md_fp.read_text("utf-8")
            title = _extract_title(raw, md_fp.stem)
            source_rel = str(md_fp.relative_to(plan_dir))
        else:
            # fallback：取目录里日期字典序最大的 05，作为"上一份"参考
            latest = _latest_match(plan_dir, _TODAY_RE)
            if latest:
                raw = latest.read_text("utf-8")
                title = _extract_title(raw, latest.stem)
                source_rel = str(latest.relative_to(plan_dir))
                fallback = True

        core_three = _parse_core_three(raw) if raw else []
        blocks = _parse_time_blocks(raw) if raw else []
        redlines = _parse_redlines(raw) if raw else []
        penalties = _parse_penalties(raw) if raw else []
        theme = _parse_today_theme(raw) if raw else ""

        # Day N / 进度
        plan_start_str = cfg.get("plan_start")
        plan_days = int(cfg.get("plan_days", 365))
        day_num = None
        progress_pct = None
        if plan_start_str:
            try:
                start = date_obj = datetime.strptime(plan_start_str, "%Y-%m-%d").date()
                day_num = (d - start).days + 1
                progress_pct = max(0, min(100, round(day_num / plan_days * 100)))
            except ValueError:
                pass

        return {
            "date": date_str,
            "day_num": day_num,
            "plan_days": plan_days,
            "progress_pct": progress_pct,
            "weekday": d.isoweekday(),  # 1=Mon..7=Sun
            "source_rel": source_rel,
            "source_title": title,
            "fallback": fallback,       # True 表示 05 不是今天的
            "theme": theme,
            "core_three": core_three,
            "blocks": blocks,
            "redlines": redlines,
            "penalties": penalties,
        }

    # ── /progress GET ──
    @r.get("/progress")
    async def progress_get(date: Optional[str] = Query(None)):
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            raise HTTPException(404, "Plan dir not configured or missing")
        date_str = date or datetime.now().strftime("%Y-%m-%d")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Invalid date format")
        return _load_progress(plan_dir, date_str)

    # ── /progress POST · 增量 merge 更新 ──
    @r.post("/progress")
    async def progress_post(payload: dict):
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            raise HTTPException(404, "Plan dir not configured or missing")
        date_str = (payload or {}).get("date") or datetime.now().strftime("%Y-%m-%d")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Invalid date format")
        existing = _load_progress(plan_dir, date_str)
        merged = _merge_progress(existing, payload)
        merged["date"] = date_str
        _save_progress(plan_dir, date_str, merged)
        return {"ok": True, "data": merged}

    # ── /review/submit · 提交日复盘 + 追加到 Ome365 Journal ──
    @r.post("/review/submit")
    async def review_submit(payload: dict):
        cfg = _load_config()
        plan_dir = _resolve_plan_dir(cfg)
        if not plan_dir:
            raise HTTPException(404, "Plan dir not configured or missing")
        date_str = (payload or {}).get("date") or datetime.now().strftime("%Y-%m-%d")
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Invalid date format")

        review = (payload or {}).get("review") or {}
        # 补 submitted_at
        if "submitted_at" not in review:
            review["submitted_at"] = datetime.now().isoformat(timespec="seconds")

        existing = _load_progress(plan_dir, date_str)
        merged = _merge_progress(existing, {"date": date_str, "review": review})
        _save_progress(plan_dir, date_str, merged)

        # 追加到 Ome365 Journal（vault 根 / Journal / YYYY / YYYY-MM-DD.md）
        vault_root = Path(os.environ.get("OME365_VAULT") or _APP_DIR.parent)
        journal_dir = vault_root / "Journal" / str(d.year)
        journal_fp = journal_dir / f"{date_str}.md"
        journal_appended = False
        try:
            journal_dir.mkdir(parents=True, exist_ok=True)
            # 渲染追加段
            scores = merged["review"].get("scores", {})
            answers = merged["review"].get("answers", {})
            counters = merged.get("counters", {})
            lines = [
                "",
                "---",
                "",
                f"## 📖 一年规划 · 日复盘 · {date_str}",
                "",
                "### 打分 (1-5)",
                f"- 节律 rhythm: {scores.get('rhythm') or '—'}",
                f"- 体感 body: {scores.get('body') or '—'}",
                f"- 心理 mind: {scores.get('mind') or '—'}",
                f"- 主业 work: {scores.get('work') or '—'}",
                f"- 关系 relation: {scores.get('relation') or '—'}",
                f"- 家庭 family: {scores.get('family') or '—'}",
                "",
                "### 四问",
                f"- 今天做了什么：{answers.get('done_today') or '—'}",
                f"- 学到/体感：{answers.get('learned') or '—'}",
                f"- 明天最重要：{answers.get('tomorrow_one_thing') or '—'}",
                f"- 达成感瞬间：{answers.get('fulfilled_moment') or '—'}",
                f"- 主动瞬间：{answers.get('proactive_moment') or '—'}",
                "",
                "### 底层心理计数",
                f"- 身体扫描：晨 {counters.get('scan_am', 0)} · 午 {counters.get('scan_pm', 0)} · 晚 {counters.get('scan_eve', 0)}",
                f"- 主动次数：{counters.get('active', 0)}",
                f"- 摸头次数：{counters.get('touch_head', 0)}",
                f"",
                f"_submitted at {review['submitted_at']}_",
                "",
            ]
            text = "\n".join(lines)
            if journal_fp.exists():
                old = journal_fp.read_text("utf-8")
                # 幂等：如果已经有同一 submitted_at 的日复盘段就不再追加
                if review["submitted_at"] not in old:
                    journal_fp.write_text(old.rstrip() + "\n" + text, encoding="utf-8")
                    journal_appended = True
            else:
                header = f"# {date_str}\n"
                journal_fp.write_text(header + text, encoding="utf-8")
                journal_appended = True
        except Exception as e:
            return {"ok": True, "data": merged, "journal_appended": False, "journal_error": str(e)}

        # 明日看板入口（提示前端是否已生成明日 05）
        from datetime import timedelta
        tomorrow = d + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        tomorrow_md = _find_today_md_by_date(plan_dir, tomorrow_str)
        return {
            "ok": True,
            "data": merged,
            "journal_appended": journal_appended,
            "journal_path": str(journal_fp),
            "tomorrow_date": tomorrow_str,
            "tomorrow_md_exists": tomorrow_md is not None,
        }

    return r
