"""
Ome365 v0.6 — 个人超级助手 + Ome 智能体
启动: cd .app && python3 server.py
"""

import os, re, json, glob, socket, subprocess, shutil, uuid, threading, logging, asyncio
from datetime import datetime, date, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

# Suppress noisy Mindos warnings (commit_digest etc.)
logging.getLogger("mindos").setLevel(logging.ERROR)

VAULT = Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()
MEDIA = Path(__file__).parent / "media"
PORT = 3650
WEEKDAYS = ["周一","周二","周三","周四","周五","周六","周日"]
DIMS = ["职业产出","创作事业","能力提升","社会影响力","生活品质","AI集成"]
DIM_ICONS = {"职业产出":"💼","创作事业":"✍️","能力提升":"📚","社会影响力":"📢","生活品质":"🥊","AI集成":"🤖"}
DIM_COLORS = {"职业产出":"#60a5fa","创作事业":"#c8a96e","能力提升":"#a78bfa","社会影响力":"#f472b6","生活品质":"#34d399","AI集成":"#38bdf8"}

CAT_COLORS = {
    "职业产出":"#60a5fa","创作事业":"#c8a96e","能力提升":"#a78bfa",
    "社会影响力":"#f472b6","生活品质":"#34d399","AI集成":"#38bdf8",
    "未分类":"#666"
}

# Contact category config — now loaded from categories file
DEFAULT_CONTACT_CATS = [
    {"id":"industry","name":"行业","color":"#60a5fa","icon":"🏢"},
    {"id":"investor","name":"投资人","color":"#34d399","icon":"💰"},
    {"id":"talent","name":"人才","color":"#fbbf24","icon":"⭐"},
    {"id":"partner","name":"合作伙伴","color":"#a78bfa","icon":"🤝"},
    {"id":"friend","name":"朋友","color":"#f472b6","icon":"❤️"},
    {"id":"mentor","name":"导师","color":"#c8a96e","icon":"🧭"},
    {"id":"team","name":"团队","color":"#38bdf8","icon":"👥"},
]
TIER_SIZES = {"A":8,"B":4,"C":2}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Settings ──────────────────────────────────────────
SETTINGS_FILE = Path(__file__).parent / "settings.json"

SETTINGS_DEFAULTS = {
    "user_name": "",
    "main_goal": "365天个人执行计划",
    "start_date": "2026-04-08",
    "plan_days": 365,
    "ai_mode": "none",        # "api" | "ollama" | "none"
    "api_base_url": "",        # e.g. https://api.openai.com/v1 or https://api.anthropic.com/v1
    "api_key": "",
    "api_model": "",           # e.g. gpt-4o, claude-sonnet-4-20250514
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3.1",
    "use_proxy": True,
    "notification_enabled": True,
    "notification_sound": "chime",  # "chime" | "bell" | "pop" | "none"
    "proactive_enabled": True,
}

def _safe_json_load(fp: Path, default=None):
    """Load JSON file with corruption protection."""
    if not fp.exists():
        return default
    try:
        return json.loads(fp.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Backup corrupted file, return default
        bak = fp.with_suffix(fp.suffix + ".bak")
        fp.rename(bak)
        return default

def load_settings() -> dict:
    saved = _safe_json_load(SETTINGS_FILE, {})
    return {**SETTINGS_DEFAULTS, **saved}

def save_settings(settings: dict):
    # Only save known keys (merge with defaults to avoid losing new keys)
    merged = {**SETTINGS_DEFAULTS, **settings}
    SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")

def _proxy_kwargs() -> dict:
    """Return proxy kwargs for requests. Bypass proxy when use_proxy is off."""
    if load_settings().get("use_proxy", True):
        return {}  # let system proxy through
    return {"proxies": {"http": "", "https": ""}}

def get_start() -> date:
    """Get the configured start date from settings, with backward compat fallback."""
    s = load_settings()
    try:
        return date.fromisoformat(s.get("start_date", "2026-04-08"))
    except Exception:
        return date(2026, 4, 8)


# ── Ome 智能体 ────────────────────────────────────────
OME_HOME = Path.home() / ".ome" / "ome365"
_ome_instance = None
_ome_lock = threading.Lock()

def _init_ome():
    """Initialize or load the Ome instance. Sets up API key from settings."""
    global _ome_instance
    settings = load_settings()
    # Propagate API key to env for Ome's ModelRouter
    if settings.get("api_key"):
        base = settings.get("api_base_url", "")
        if "openrouter" in base:
            os.environ.setdefault("OPENROUTER_API_KEY", settings["api_key"])
        elif "deepseek" in base:
            os.environ.setdefault("DEEPSEEK_API_KEY", settings["api_key"])
        else:
            os.environ.setdefault("OPENAI_API_KEY", settings["api_key"])
    try:
        from ome import Ome
        if OME_HOME.exists():
            _ome_instance = Ome.load(OME_HOME)
        else:
            _ome_instance = Ome.create(str(OME_HOME), name="小灵", traits=["执行导向", "温暖", "犀利"])
            # Write correct config.yaml matching user's API settings
            _write_ome_config(settings)
            _ome_instance = Ome.load(OME_HOME)
        print(f"  Ome 智能体: ✅ {_ome_instance.name} (from {OME_HOME})")
    except ImportError:
        print("  Ome 智能体: ⚠️ omnity-ome 未安装，AI功能降级为直连模式")
    except Exception as e:
        print(f"  Ome 智能体: ❌ 初始化失败 ({e})")

def _write_ome_config(settings: dict):
    """Write config.yaml for Ome based on Ome365 settings."""
    base = settings.get("api_base_url", "").rstrip("/")
    model = settings.get("api_model", "deepseek-chat")
    if "openrouter" in base:
        provider_name, key_env = "openrouter", "OPENROUTER_API_KEY"
    elif "deepseek" in base:
        provider_name, key_env = "deepseek", "DEEPSEEK_API_KEY"
        base = "https://api.deepseek.com"
    else:
        provider_name, key_env = "custom", "OPENAI_API_KEY"
    cfg = f"""models:
- name: {provider_name}
  type: openai_compatible
  base_url: {base}
  api_key_env: {key_env}
  model: {model}
  priority: 1
  for: [chat, commit_digest, reflection, reasoning, creation, deep_reasoning, complex_creation]
fallback: {provider_name}
hydrate:
  default_max_tokens: 2000
  include_relations: true
  include_capabilities: true
commit:
  use_llm: true
  fallback_to_rules: true
reflection:
  trigger_every_n_commits: 20
  enabled: true
"""
    (OME_HOME / "config.yaml").write_text(cfg, "utf-8")

def get_ome():
    """Get the Ome instance (thread-safe). Returns None if unavailable."""
    return _ome_instance


# ── MD Parsing ────────────────────────────────────────
def parse_md(fp: Path) -> dict:
    if not fp.exists():
        return {"meta":{},"content":"","raw":"","tasks":[],"sections":{}}
    text = fp.read_text("utf-8")
    meta, content = {}, text
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if m:
        for line in m.group(1).split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip()
        content = text[m.end():]
    tasks = []
    for i, line in enumerate(content.split('\n')):
        cm = re.match(r'^(\s*)-\s*\[([ xX])\]\s*(.+)', line)
        if cm:
            tasks.append({"line":i,"done":cm.group(2).lower()=='x',"text":cm.group(3).strip(),"indent":len(cm.group(1))})
    return {"meta":meta,"content":content,"raw":text,"tasks":tasks}


def parse_yaml_meta(text: str) -> dict:
    """Parse YAML-like frontmatter, handling arrays."""
    meta = {}
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m: return meta
    for line in m.group(1).split('\n'):
        line = line.strip()
        if not line or line.startswith('#'): continue
        if ':' in line:
            k, v = line.split(':', 1)
            k = k.strip(); v = v.strip()
            if v.startswith('[') and v.endswith(']'):
                v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(',') if x.strip()]
            meta[k] = v
    return meta


def write_md(fp: Path, meta: dict, content: str):
    fp.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            lines.append(f"{k}: {v}")
    lines += ["---","",content]
    fp.write_text('\n'.join(lines), "utf-8")

def toggle_task(fp: Path, text: str) -> bool:
    if not fp.exists(): return False
    raw = fp.read_text("utf-8"); lines = raw.split('\n')
    for i, line in enumerate(lines):
        m = re.match(r'^(\s*-\s*\[)([ xX])(\]\s*)(.*)', line)
        if m and m.group(4).strip() == text.strip():
            lines[i] = f"{m.group(1)}{'x' if m.group(2)==' ' else ' '}{m.group(3)}{m.group(4)}"
            fp.write_text('\n'.join(lines), "utf-8"); return True
    return False


def parse_time_blocks(fp: Path) -> list:
    """Parse the ## 时间块 / ## 日程 / ## 日程安排 table from a daily markdown file."""
    if not fp.exists(): return []
    raw = fp.read_text("utf-8")
    # Find the 时间块/日程/日程安排 section
    m = re.search(r'## (?:时间块|日程安排|日程)\s*\n\|.*\|\s*\n\|[-| ]+\|\s*\n((?:\|.*\|\s*\n?)*)', raw)
    if not m: return []
    blocks = []
    for i, line in enumerate(m.group(1).strip().split('\n')):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 2:
            blocks.append({"idx": i, "time": cells[0], "item": cells[1] if len(cells) > 1 else "", "dim": cells[2] if len(cells) > 2 else ""})
    return blocks


def update_time_blocks(fp: Path, blocks: list):
    """Rewrite the ## 时间块/日程/日程安排 table in the daily markdown file."""
    if not fp.exists(): return False
    raw = fp.read_text("utf-8")
    header = "## 日程\n| 时间 | 事项 | 维度 |\n|------|------|------|\n"
    rows = "\n".join(f"| {b.get('time','')} | {b.get('item','')} | {b.get('dim','')} |" for b in blocks) + "\n" if blocks else ""
    new_section = header + rows
    # Replace existing section (match any of the three names)
    pattern = r'## (?:时间块|日程安排|日程)\s*\n\|.*\|\s*\n\|[-| ]+\|\s*\n(?:\|.*\|\s*\n?)*'
    if re.search(pattern, raw):
        raw = re.sub(pattern, new_section, raw, count=1)
    else:
        # No existing section, insert before ## 会议纪要 or append
        if '## 会议纪要' in raw:
            raw = raw.replace('## 会议纪要', new_section + '\n## 会议纪要')
        else:
            raw += '\n' + new_section
    fp.write_text(raw, "utf-8")
    return True


def edit_task_in_file(fp: Path, old_text: str, new_text: str, description: str = None) -> bool:
    """Edit a task's text and optionally add/update a description line below it."""
    if not fp.exists(): return False
    raw = fp.read_text("utf-8"); lines = raw.split('\n')
    for i, line in enumerate(lines):
        m = re.match(r'^(\s*-\s*\[[ xX]\]\s*)(.*)', line)
        if m and m.group(2).strip() == old_text.strip():
            # Update the task text
            lines[i] = f"{m.group(1)}{new_text}"
            # Handle description: check if next line is indented description
            desc_prefix = "    > "
            has_desc = (i + 1 < len(lines) and lines[i+1].strip().startswith('>'))
            if description is not None:
                if description.strip():
                    desc_line = f"{desc_prefix}{description}"
                    if has_desc:
                        lines[i+1] = desc_line
                    else:
                        lines.insert(i+1, desc_line)
                elif has_desc:
                    # Remove existing description
                    lines.pop(i+1)
            fp.write_text('\n'.join(lines), "utf-8")
            return True
    return False


def delete_task_in_file(fp: Path, task_text: str) -> bool:
    """Delete a task line (and its description if any) from a markdown file."""
    if not fp.exists(): return False
    raw = fp.read_text("utf-8"); lines = raw.split('\n')
    for i, line in enumerate(lines):
        m = re.match(r'^(\s*-\s*\[[ xX]\]\s*)(.*)', line)
        if m and m.group(2).strip() == task_text.strip():
            # Check if next line is indented description
            has_desc = (i + 1 < len(lines) and lines[i+1].strip().startswith('>'))
            if has_desc:
                lines.pop(i+1)
            lines.pop(i)
            fp.write_text('\n'.join(lines), "utf-8")
            return True
    return False


def get_task_description(fp: Path, text: str) -> str:
    """Get the description line below a task."""
    if not fp.exists(): return ""
    raw = fp.read_text("utf-8"); lines = raw.split('\n')
    for i, line in enumerate(lines):
        m = re.match(r'^(\s*-\s*\[[ xX]\]\s*)(.*)', line)
        if m and m.group(2).strip() == text.strip():
            if i + 1 < len(lines):
                desc_line = lines[i+1].strip()
                if desc_line.startswith('>'):
                    return desc_line.lstrip('> ').strip()
    return ""


# ── Helpers ───────────────────────────────────────────
def today_s(): return date.today().isoformat()
def week_n():
    START = get_start()
    d = (date.today() - START).days
    return max(0, d // 7 + 1) if d >= 0 else 0
def quarter_n():
    w = week_n()
    return min(4, max(1, (w - 1) // 12 + 1)) if w > 0 else 1
def day_n():
    START = get_start()
    d = (date.today() - START).days
    return d + 1 if d >= 0 else 0

def find_daily(d=None): return VAULT/"Journal"/"Daily"/f"{d or today_s()}.md"
def find_weekly(w=None):
    if w is None: w = week_n()
    p = str(VAULT/"Journal"/"Weekly"/f"W{w:02d}-*.md")
    ms = glob.glob(p)
    if ms: return Path(ms[0])
    START = get_start()
    mon = START + timedelta(weeks=max(0,w-1))
    return VAULT/"Journal"/"Weekly"/f"W{w:02d}-{mon.isoformat()}.md"

def ensure_weekly():
    fp = find_weekly()
    if fp.exists(): return
    fp.parent.mkdir(parents=True, exist_ok=True)
    START = get_start()
    w = week_n(); mon = START + timedelta(weeks=max(0,w-1))
    meta = {"week": f"W{w:02d}", "start": mon.isoformat(), "quarter": f"Q{quarter_n()}"}
    content = f"""# W{w:02d} · {mon.isoformat()} 起

## 本周关键动作
- [ ]

## 周回顾
**做得好的：**

**需改进的：**

**下周重点：**
"""
    write_md(fp, meta, content)
def find_quarterly(q=None):
    if q is None: q = quarter_n()
    return VAULT/"Journal"/"Quarterly"/f"Q{q}-2026.md"

def count_tasks(tasks):
    t = len(tasks); d = sum(1 for x in tasks if x["done"])
    return {"total":t,"done":d,"pct":round(d/t*100) if t else 0}

def task_already_in_today(lines: list, task_text: str) -> bool:
    """Check if a task with the given text already exists in checkbox lines only.
    Avoids false positives from diary/notes sections containing the same words."""
    for line in lines:
        # Only match actual checkbox lines, not prose text
        m = re.match(r'^\s*-\s*\[([ xX])\]\s*(.*)', line)
        if m:
            checkbox_text = m.group(2).strip()
            # Strip time prefix [HH:MM] if present before comparing
            core = re.sub(r'^\[\d{2}:\d{2}\]\s*', '', checkbox_text).strip()
            core_no_tag = re.sub(r'\s*#\S+\s*$', '', core).strip()
            task_core = re.sub(r'^\[\d{2}:\d{2}\]\s*', '', task_text).strip()
            task_core_no_tag = re.sub(r'\s*#\S+\s*$', '', task_core).strip()
            if core == task_text or core_no_tag == task_text or \
               core == task_core or core_no_tag == task_core_no_tag:
                return True
    return False

def ensure_today():
    fp = find_daily()
    created = not fp.exists()
    if created:
        fp.parent.mkdir(parents=True, exist_ok=True)
        d = date.today(); wd = WEEKDAYS[d.weekday()]; dn = day_n()
        settings = load_settings()
        meta = {"date":today_s(),"week":f"W{week_n()}","mood":"","energy":"","focus":"","tags":"[]"}
        content = f"""# {today_s()} · {wd} · Day {dn}

## 今日最重要的3件事
- [ ]
- [ ]
- [ ]

## 时间块
| 时间 | 事项 | 维度 |
|------|------|------|
| 09-12 | | |
| 14-18 | | |
| 20-22 | | |

## 会议纪要


## 日记
**做了什么：**

**学到什么：**

## 反思
**今日一句：**

**明天最重要的1件事：**
"""
        write_md(fp, meta, content)

    # Inject daily repeat tasks if not already present
    repeats = load_task_repeats()
    daily_repeats = [r for r in repeats if r.get("repeat") == "daily"]
    if not daily_repeats:
        return
    raw = fp.read_text("utf-8")
    lines = raw.split('\n')
    changed = False
    for r in daily_repeats:
        task_text = r["text"]
        # Use smarter check: only look in checkbox lines, not diary/notes sections
        if task_already_in_today(lines, task_text):
            continue
        time_prefix = f"[{r['time']}] " if r.get("time") else ""
        task_line = f"- [ ] {time_prefix}{task_text}"
        # Insert after "今日最重要" section
        inserted = False
        for i, line in enumerate(lines):
            if line.startswith('## 今日') and '件事' in line:
                j = i + 1
                while j < len(lines) and (lines[j].strip().startswith('- [') or lines[j].strip().startswith('>') or lines[j].strip() == ''):
                    j += 1
                lines.insert(j, task_line)
                inserted = True; break
        if not inserted:
            lines.append(task_line)
        changed = True
    if changed:
        fp.write_text('\n'.join(lines), "utf-8")


# ── Task Repeats ────────────────────────────────────
TASK_REPEATS_FILE = Path(__file__).parent / "task_repeats.json"

def load_task_repeats():
    return _safe_json_load(TASK_REPEATS_FILE, [])

def save_task_repeats(repeats):
    TASK_REPEATS_FILE.write_text(json.dumps(repeats, ensure_ascii=False, indent=2), "utf-8")


# ── Special Days ────────────────────────────────────
SPECIAL_DAYS_FILE = Path(__file__).parent / "special_days.json"

def load_special_days():
    return _safe_json_load(SPECIAL_DAYS_FILE, [])

def save_special_days(days):
    SPECIAL_DAYS_FILE.write_text(json.dumps(days, ensure_ascii=False, indent=2), "utf-8")

def compute_next_occurrence(day_entry):
    """Compute next occurrence and countdown for a special day."""
    d_str = day_entry.get("date","")
    repeat = day_entry.get("repeat","none")
    today = date.today()
    try:
        if repeat == "yearly" and len(d_str) == 5:  # MM-DD
            m, d = int(d_str[:2]), int(d_str[3:])
            this_year = date(today.year, m, d)
            if this_year < today:
                nxt = date(today.year + 1, m, d)
            else:
                nxt = this_year
        elif repeat == "monthly" and len(d_str) <= 2:  # DD
            d = int(d_str)
            this_month = date(today.year, today.month, min(d, 28))
            if this_month < today:
                nm = today.month + 1
                ny = today.year
                if nm > 12: nm = 1; ny += 1
                nxt = date(ny, nm, min(d, 28))
            else:
                nxt = this_month
        else:
            nxt = date.fromisoformat(d_str)
    except:
        return None, None
    countdown = (nxt - today).days
    return nxt.isoformat(), countdown


# ── Categories ───────────────────────────────────────
CATEGORIES_FILE = Path(__file__).parent / "categories.json"

def load_categories() -> list:
    data = _safe_json_load(CATEGORIES_FILE)
    if data is not None:
        return data
    default = [
        {"id":"career","name":"职业产出","color":"#60a5fa","icon":"💼"},
        {"id":"create","name":"创作事业","color":"#c8a96e","icon":"✍️"},
        {"id":"growth","name":"能力提升","color":"#a78bfa","icon":"📚"},
        {"id":"influence","name":"社会影响力","color":"#f472b6","icon":"📢"},
        {"id":"life","name":"生活品质","color":"#34d399","icon":"🥊"},
        {"id":"ai","name":"AI集成","color":"#38bdf8","icon":"🤖"},
        {"id":"uncategorized","name":"未分类","color":"#666","icon":"📌"},
    ]
    CATEGORIES_FILE.write_text(json.dumps(default, ensure_ascii=False, indent=2), "utf-8")
    return default

def save_categories(cats: list):
    CATEGORIES_FILE.write_text(json.dumps(cats, ensure_ascii=False, indent=2), "utf-8")


# ── Contact Categories ───────────────────────────────
CONTACT_CATS_FILE = Path(__file__).parent / "contact_categories.json"

def load_contact_categories() -> list:
    data = _safe_json_load(CONTACT_CATS_FILE)
    if data is not None:
        return data
    CONTACT_CATS_FILE.write_text(json.dumps(DEFAULT_CONTACT_CATS, ensure_ascii=False, indent=2), "utf-8")
    return DEFAULT_CONTACT_CATS

def save_contact_categories(cats: list):
    CONTACT_CATS_FILE.write_text(json.dumps(cats, ensure_ascii=False, indent=2), "utf-8")

def contact_cat_map() -> dict:
    """Return {id: {name, color, icon}} map."""
    return {c["id"]: c for c in load_contact_categories()}


# ── Plan Parsing (structured) ─────────────────────────
def parse_plan():
    fp = VAULT / "000-365-PLAN.md"
    if not fp.exists(): return {"quarters":[], "milestones":[], "overview":{"total":0,"done":0,"pct":0}}
    text = fp.read_text("utf-8")
    m = re.match(r'^---.*?---\s*\n', text, re.DOTALL)
    if m: text = text[m.end():]

    quarters = []
    milestones = []
    current_q = None
    current_dim = None

    for line in text.split('\n'):
        qm = re.match(r'^## Q(\d)\s*·\s*(.+?)(?:（|$)', line)
        if qm:
            current_q = {
                "id": int(qm.group(1)),
                "theme": qm.group(2).strip(),
                "dimensions": [],
                "summary": line.strip('# '),
            }
            quarters.append(current_q)
            current_dim = None
            continue

        if current_q and line.startswith('### '):
            dim_name = line[4:].strip()
            dim_name = re.sub(r'（.*?）', '', dim_name).strip()
            if dim_name in DIMS or any(d in dim_name for d in DIMS):
                matched = next((d for d in DIMS if d in dim_name), dim_name)
                current_dim = {
                    "name": matched,
                    "icon": DIM_ICONS.get(matched, "📌"),
                    "color": DIM_COLORS.get(matched, "#c8a96e"),
                    "tasks": []
                }
                current_q["dimensions"].append(current_dim)
            continue

        if current_dim:
            tm = re.match(r'^- \[([ xX])\]\s*(.+)', line)
            if tm:
                current_dim["tasks"].append({
                    "done": tm.group(1).lower() == 'x',
                    "text": tm.group(2).strip()
                })

        if '关键里程碑' in line:
            continue
        mm = re.match(r'^\|\s*\*?\*?(\d{4}-\d{2}-\d{2})\*?\*?\s*\|\s*\*?\*?(.*?)\*?\*?\s*\|', line)
        if mm:
            d_str = mm.group(1)
            past = False
            countdown = 0
            try:
                md = date.fromisoformat(d_str)
                past = md <= date.today()
                countdown = (md - date.today()).days
            except: pass
            label = mm.group(2).strip()
            # Infer category from label keywords
            ms_cat = "其他"
            ms_color = "#666"
            label_lower = label.lower()
            if any(k in label_lower for k in ["入职","摸底","报告","组织","团队","架构"]):
                ms_cat = "职业产出"; ms_color = "#60a5fa"
            elif any(k in label_lower for k in ["神临","山海","写作","发布","故事","创作"]):
                ms_cat = "创作事业"; ms_color = "#c8a96e"
            elif any(k in label_lower for k in ["学习","认证","课程","技术","论文","开源"]):
                ms_cat = "能力提升"; ms_color = "#a78bfa"
            elif any(k in label_lower for k in ["演讲","分享","社区","影响","品牌"]):
                ms_cat = "社会影响力"; ms_color = "#f472b6"
            elif any(k in label_lower for k in ["健身","搏击","生日","旅行","生活","运动"]):
                ms_cat = "生活品质"; ms_color = "#34d399"
            elif any(k in label_lower for k in ["ai","模型","agent","rag","llm"]):
                ms_cat = "AI集成"; ms_color = "#38bdf8"
            milestones.append({"date":d_str,"label":label,"past":past,"countdown":countdown,"category":ms_cat,"color":ms_color})

    for q in quarters:
        total = sum(len(d["tasks"]) for d in q["dimensions"])
        done = sum(sum(1 for t in d["tasks"] if t["done"]) for d in q["dimensions"])
        q["stats"] = {"total":total,"done":done,"pct":round(done/total*100) if total else 0}
        for d in q["dimensions"]:
            dt = len(d["tasks"]); dd = sum(1 for t in d["tasks"] if t["done"])
            d["stats"] = {"total":dt,"done":dd,"pct":round(dd/dt*100) if dt else 0}

    all_total = sum(q["stats"]["total"] for q in quarters)
    all_done = sum(q["stats"]["done"] for q in quarters)
    overview = {"total":all_total,"done":all_done,"pct":round(all_done/all_total*100) if all_total else 0}

    return {"quarters":quarters,"milestones":milestones,"overview":overview}


# ── API: Dashboard ────────────────────────────────────
@app.get("/api/dashboard")
async def dashboard():
    START = get_start()
    ensure_today()
    daily = parse_md(find_daily())
    weekly = parse_md(find_weekly())
    quarterly = parse_md(find_quarterly())
    plan = parse_plan()
    dec_dir = VAULT/"Decisions"
    dec_count = len(list(dec_dir.glob("*.md"))) if dec_dir.exists() else 0
    notes_dir = VAULT/"Notes"
    notes_count = 0
    nfp = notes_dir / f"{today_s()}.md"
    if nfp.exists():
        notes_count = nfp.read_text("utf-8").count("\n- [")
    ppl_dir = VAULT/"Contacts"/"people"
    contact_count = len(list(ppl_dir.glob("*.md"))) if ppl_dir.exists() else 0
    # Prefer Ome structured-memory store (fact/episode/skill/…) over legacy Memory/*.md files.
    # Legacy count kept as fallback for when Ome isn't initialized yet.
    _ome = get_ome()
    if _ome:
        try:
            with _ome_lock:
                memory_count = _ome.memory_stats().get("total", 0)
        except Exception:
            memory_count = 0
    else:
        memory_count = len(list((VAULT/"Memory").glob("*.md"))) - 1 if (VAULT/"Memory").exists() else 0  # -1 for MEMORY.md

    # Today's mood/energy/focus
    today_meta = daily["meta"]

    return {
        "date":today_s(),"weekday":WEEKDAYS[date.today().weekday()],
        "day_number":day_n(),"week_number":week_n(),
        "quarter":quarter_n(),
        "quarter_theme":quarterly["meta"].get("theme",""),
        "days_to_start":max(0,(START-date.today()).days),
        "today":{"tasks":[t for t in daily["tasks"] if t["text"].strip()],"content":daily["content"],"meta":daily["meta"]},
        "week":{"tasks":[t for t in weekly["tasks"] if t["text"].strip()],"meta":weekly["meta"]},
        "plan_overview":plan["overview"],
        "plan_pct":plan["overview"]["pct"],
        "milestones":plan["milestones"],
        "decision_count":dec_count,
        "notes_count":notes_count,
        "contact_count":contact_count,
        "memory_count":max(0, memory_count),
        "today_mood":today_meta.get("mood",""),
        "today_energy":today_meta.get("energy",""),
        "today_focus":today_meta.get("focus",""),
    }


# ── API: Categories ──────────────────────────────────
@app.get("/api/categories")
async def get_categories():
    return load_categories()

@app.post("/api/categories")
async def create_category(body:dict):
    cats = load_categories()
    cid = body.get("id") or re.sub(r'[^\w]','',body.get("name",""))[:20].lower() or uuid.uuid4().hex[:8]
    cats.append({"id":cid,"name":body["name"],"color":body.get("color","#888"),"icon":body.get("icon","📌")})
    save_categories(cats)
    return {"ok":True,"id":cid}

@app.delete("/api/categories/{cat_id}")
async def delete_category(cat_id:str):
    cats = load_categories()
    cats = [c for c in cats if c["id"] != cat_id]
    save_categories(cats)
    return {"ok":True}


# ── API: Contact Categories ──────────────────────────
@app.get("/api/contact-categories")
async def get_contact_categories():
    return load_contact_categories()

@app.post("/api/contact-categories")
async def create_contact_category(body:dict):
    cats = load_contact_categories()
    cid = body.get("id") or re.sub(r'[^\w]','',body.get("name",""))[:20].lower() or uuid.uuid4().hex[:8]
    cats.append({"id":cid,"name":body["name"],"color":body.get("color","#888"),"icon":body.get("icon","🏷")})
    save_contact_categories(cats)
    return {"ok":True,"id":cid}

@app.delete("/api/contact-categories/{cat_id}")
async def delete_contact_category(cat_id:str):
    cats = load_contact_categories()
    cats = [c for c in cats if c["id"] != cat_id]
    save_contact_categories(cats)
    return {"ok":True}


# ── API: Plan ─────────────────────────────────────────
@app.get("/api/plan")
async def get_plan():
    return parse_plan()

@app.get("/api/plan/raw")
async def get_plan_raw():
    return parse_md(VAULT / "000-365-PLAN.md")

@app.post("/api/plan/toggle")
async def toggle_plan_task(body: dict):
    return {"ok": toggle_task(VAULT/"000-365-PLAN.md", body.get("text",""))}

@app.put("/api/plan/milestone")
async def update_milestone(body: dict):
    fp = VAULT / "000-365-PLAN.md"
    if not fp.exists(): return {"error": "计划文件不存在"}
    orig_date = body.get("original_date","")
    orig_label = body.get("original_label","")
    new_date = body.get("date", orig_date)
    new_label = body.get("label", orig_label)
    text = fp.read_text("utf-8")
    lines = text.split('\n')
    found = False
    for i, line in enumerate(lines):
        mm = re.match(r'^\|\s*\*?\*?(\d{4}-\d{2}-\d{2})\*?\*?\s*\|\s*\*?\*?(.*?)\*?\*?\s*\|', line)
        if mm and mm.group(1) == orig_date and orig_label in mm.group(2):
            # Rebuild the milestone line
            lines[i] = f"| **{new_date}** | **{new_label}** |"
            found = True
            break
    if not found:
        return {"error": "未找到匹配的里程碑"}
    fp.write_text('\n'.join(lines), "utf-8")
    return {"ok": True}


# ── API: Today/Week/Quarter ───────────────────────────
@app.get("/api/today")
async def get_today():
    ensure_today(); fp = find_daily()
    data = parse_md(fp)
    data["tasks"] = [t for t in data["tasks"] if t["text"].strip()]
    # Add descriptions and repeat info to tasks
    repeats = load_task_repeats()
    repeat_texts = {r["text"]: r["repeat"] for r in repeats}
    for t in data["tasks"]:
        t["description"] = get_task_description(fp, t["text"])
        # Check if this task matches any repeat (strip time prefix for matching)
        core = re.sub(r'^\[\d{2}:\d{2}\]\s*', '', t["text"]).strip()
        core_no_tag = re.sub(r'\s*#\S+$', '', core).strip()
        t["repeat"] = repeat_texts.get(core, repeat_texts.get(core_no_tag, ""))
    data["time_blocks"] = parse_time_blocks(fp)
    return {"path":str(fp.relative_to(VAULT)), **data}

@app.get("/api/today/timeblocks")
async def get_time_blocks():
    ensure_today()
    return {"ok": True, "blocks": parse_time_blocks(find_daily())}

@app.put("/api/today/timeblocks")
async def save_time_blocks(body: dict):
    """Save the full time blocks list (replaces all blocks)."""
    ensure_today()
    blocks = body.get("blocks", [])
    update_time_blocks(find_daily(), blocks)
    return {"ok": True, "blocks": parse_time_blocks(find_daily())}

@app.post("/api/today/toggle")
async def toggle_today(body:dict):
    target_date = body.get("date","").strip()
    fp = find_daily(target_date) if target_date else find_daily()
    return {"ok":toggle_task(fp, body.get("text",""))}

@app.put("/api/today/content")
async def save_today(body:dict):
    find_daily().write_text(body.get("raw",""),"utf-8")
    return {"ok":True}

@app.post("/api/today/add")
async def add_today_task(body:dict):
    text = body.get("text","").strip()
    cat = body.get("category","")
    time_str = body.get("time","").strip()
    repeat = body.get("repeat","none")
    if not text: raise HTTPException(400, "Empty task")
    fp = find_daily(); raw = fp.read_text("utf-8")
    tag = f" #{cat}" if cat and cat != "uncategorized" else ""
    time_prefix = f"[{time_str}] " if time_str else ""
    task_line = f"- [ ] {time_prefix}{text}{tag}"
    lines = raw.split('\n'); inserted = False
    for i, line in enumerate(lines):
        if line.startswith('## 今日') and '件事' in line:
            j = i + 1
            while j < len(lines) and (lines[j].strip().startswith('- [') or lines[j].strip().startswith('>') or lines[j].strip() == ''):
                j += 1
            lines.insert(j, task_line)
            inserted = True; break
    if not inserted:
        for i, line in enumerate(lines):
            if line.startswith('## ') and i > 0:
                lines.insert(i, task_line); inserted = True; break
    if not inserted: lines.append(task_line)
    fp.write_text('\n'.join(lines), "utf-8")
    # Save repeat config
    if repeat and repeat != "none":
        repeats = load_task_repeats()
        # Remove duplicate if exists
        repeats = [r for r in repeats if r["text"] != text]
        repeats.append({"text": text, "repeat": repeat, "time": time_str, "scope": "today", "created": today_s()})
        save_task_repeats(repeats)
    _auto_growth()
    return {"ok":True}

@app.put("/api/today/task")
async def edit_today_task(body:dict):
    old_text = body.get("old_text","").strip()
    new_text = body.get("new_text","").strip()
    description = body.get("description", None)
    if not old_text: raise HTTPException(400, "Missing old_text")
    if not new_text: new_text = old_text
    ok = edit_task_in_file(find_daily(), old_text, new_text, description)
    return {"ok":ok}

@app.delete("/api/today/task")
async def delete_today_task(body:dict):
    text = body.get("text","").strip()
    if not text: raise HTTPException(400, "Missing text")
    target_date = body.get("date","").strip()
    fp = find_daily(target_date) if target_date else find_daily()
    ok = delete_task_in_file(fp, text)
    return {"ok":ok}

@app.post("/api/week/add")
async def add_week_task(body:dict):
    text = body.get("text","").strip()
    cat = body.get("category","")
    if not text: raise HTTPException(400, "Empty task")
    time_str = body.get("time","").strip()
    repeat = body.get("repeat","none")
    target_date = body.get("target_date","").strip()  # YYYY-MM-DD to route to specific day

    # If target_date given, add to that day's daily file instead of weekly
    if target_date:
        fp = find_daily(target_date)
        if not fp.exists():
            fp.parent.mkdir(parents=True, exist_ok=True)
            wd = WEEKDAYS[date.fromisoformat(target_date).weekday()]
            fp.write_text(f"# {target_date} {wd}\n\n## 任务\n\n## 日记\n", "utf-8")
        raw = fp.read_text("utf-8")
        tag = f" #{cat}" if cat and cat != "uncategorized" else ""
        time_prefix = f"[{time_str}] " if time_str else ""
        task_line = f"- [ ] {time_prefix}{text}{tag}"
        if "## 任务" in raw:
            raw = raw.replace("## 任务\n", f"## 任务\n{task_line}\n", 1)
        else:
            raw += f"\n## 任务\n{task_line}\n"
        fp.write_text(raw, "utf-8")
        return {"ok":True, "target":"daily", "date":target_date}

    ensure_weekly()
    fp = find_weekly(); raw = fp.read_text("utf-8")
    tag = f" #{cat}" if cat and cat != "uncategorized" else ""
    time_prefix = f"[{time_str}] " if time_str else ""
    task_line = f"- [ ] {time_prefix}{text}{tag}"
    lines = raw.split('\n')
    last_cb = -1
    for i, line in enumerate(lines):
        if re.match(r'^\s*-\s*\[', line): last_cb = i
        if last_cb >= 0 and i == last_cb + 1 and line.strip().startswith('>'): last_cb = i
    if last_cb >= 0:
        lines.insert(last_cb + 1, task_line)
    else:
        lines.append(task_line)
    fp.write_text('\n'.join(lines), "utf-8")
    if repeat and repeat != "none":
        repeats = load_task_repeats()
        repeats = [r for r in repeats if r["text"] != text]
        repeats.append({"text": text, "repeat": repeat, "time": time_str, "scope": "week", "created": today_s()})
        save_task_repeats(repeats)
    _auto_growth()
    return {"ok":True}

@app.get("/api/week")
async def get_week(w:int=None):
    if w is None: ensure_weekly()
    fp = find_weekly(w); data = parse_md(fp)
    data["tasks"] = [t for t in data["tasks"] if t["text"].strip()]
    repeats = load_task_repeats()
    repeat_texts = {r["text"]: r["repeat"] for r in repeats}
    for t in data["tasks"]:
        t["description"] = get_task_description(fp, t["text"])
        core = re.sub(r'^\[\d{2}:\d{2}\]\s*', '', t["text"]).strip()
        core_no_tag = re.sub(r'\s*#\S+$', '', core).strip()
        t["repeat"] = repeat_texts.get(core, repeat_texts.get(core_no_tag, ""))
    return {"path":str(fp.relative_to(VAULT)), **data}

@app.post("/api/week/toggle")
async def toggle_week(body:dict):
    return {"ok":toggle_task(find_weekly(body.get("week",week_n())), body.get("text",""))}

@app.put("/api/week/task")
async def edit_week_task(body:dict):
    old_text = body.get("old_text","").strip()
    new_text = body.get("new_text","").strip()
    description = body.get("description", None)
    if not old_text: raise HTTPException(400, "Missing old_text")
    if not new_text: new_text = old_text
    ok = edit_task_in_file(find_weekly(), old_text, new_text, description)
    return {"ok":ok}

@app.delete("/api/week/task")
async def delete_week_task(body:dict):
    text = body.get("text","").strip()
    if not text: raise HTTPException(400, "Missing text")
    ok = delete_task_in_file(find_weekly(), text)
    return {"ok":ok}

@app.get("/api/quarter")
async def get_quarter(q:int=None):
    fp = find_quarterly(q); data = parse_md(fp)
    data["tasks"] = [t for t in data["tasks"] if t["text"].strip()]
    return {"path":str(fp.relative_to(VAULT)), **data}


# ── API: Decisions ────────────────────────────────────
@app.get("/api/decisions")
async def list_decisions():
    d = VAULT/"Decisions"
    if not d.exists(): return []
    out = []
    for f in sorted(d.glob("*.md"), reverse=True):
        if f.name == "README.md": continue
        data = parse_md(f); title = ""
        for line in data["content"].split('\n'):
            if line.startswith('# '):
                title = line[2:].strip()
                if title.startswith('决策：'): title = title[3:]
                break
        out.append({"file":f.name,"date":data["meta"].get("date",""),"scope":data["meta"].get("scope",""),
                     "impact":data["meta"].get("impact",""),"status":data["meta"].get("status","待验证"),
                     "title":title,"content":data["content"]})
    return out

class DecisionCreate(BaseModel):
    title:str; scope:str="架构"; impact:str="中"; background:str=""

@app.post("/api/decisions")
async def create_decision(body:DecisionCreate):
    d = VAULT/"Decisions"; d.mkdir(exist_ok=True)
    slug = re.sub(r'[^\w\u4e00-\u9fff]','-',body.title)[:30].strip('-')
    fn = f"{today_s()}-{slug}.md"; fp = d/fn
    vd = (date.today()+timedelta(days=30)).isoformat()
    meta = {"date":today_s(),"scope":body.scope,"impact":body.impact,"status":"待验证","verify_by":vd}
    content = f"""# 决策：{body.title}\n\n## 背景\n{body.background or '（待补充）'}\n\n## 备选方案\n1. **方案A**：\n2. **方案B**：\n\n## 最终选择\n（待补充）\n\n## 验证记录\n> {vd} 回来填写\n"""
    write_md(fp, meta, content)
    _auto_growth()
    return {"ok":True,"file":fn}

@app.get("/api/decisions/{filename}")
async def get_decision(filename:str):
    fp = VAULT/"Decisions"/filename
    if not fp.exists(): raise HTTPException(404)
    data = parse_md(fp)
    return {"file":filename,"raw":data["raw"],"content":data["content"],"meta":data["meta"]}

@app.post("/api/decisions/toggle-status")
async def toggle_dec_status(body:dict):
    fp = VAULT/"Decisions"/body.get("file","")
    if not fp.exists(): raise HTTPException(404)
    text = fp.read_text("utf-8")
    cycle = ["待验证","已验证","需修正"]
    cur = next((s for s in cycle if f"status: {s}" in text), "待验证")
    nxt = cycle[(cycle.index(cur)+1)%3]
    fp.write_text(text.replace(f"status: {cur}",f"status: {nxt}"),"utf-8")
    return {"ok":True,"new_status":nxt}


# ── API: Notes (Speed Notes / 速记) ──────────────────
NOTE_ENTRY_RE = re.compile(r'^- \[(\d{2}:\d{2})\]\s*(?:#(\S+)\s+)?(.*)')

def _parse_notes_file(fp) -> list:
    """Parse a notes .md file into entries.
    Rule: a new entry starts on any `- [HH:MM] ...` line; every subsequent line
    (including blank lines and unindented continuations) belongs to that entry
    until the next `- [HH:MM]` or EOF. Indented continuations (2-space prefix)
    are unindented on read. Trailing blank lines are trimmed per entry.
    """
    items = []
    cur = None  # dict being built
    cur_lines = []  # continuation lines
    for raw in fp.read_text("utf-8").split('\n'):
        m = NOTE_ENTRY_RE.match(raw)
        if m:
            if cur is not None:
                while cur_lines and cur_lines[-1] == '':
                    cur_lines.pop()
                if cur_lines:
                    cur["text"] = (cur["text"] + '\n' + '\n'.join(cur_lines)).rstrip()
                items.append(cur)
            cur = {"time": m.group(1), "category": m.group(2) or "", "text": m.group(3)}
            cur_lines = []
        else:
            # Skip file header line
            if cur is None:
                continue
            # Strip one level of 2-space indent if present
            if raw.startswith('  '):
                cur_lines.append(raw[2:])
            else:
                cur_lines.append(raw)
    if cur is not None:
        while cur_lines and cur_lines[-1] == '':
            cur_lines.pop()
        if cur_lines:
            cur["text"] = (cur["text"] + '\n' + '\n'.join(cur_lines)).rstrip()
        items.append(cur)
    return items


def _format_note_entry(time_s: str, category: str, text: str) -> str:
    """Format a note entry for the .md file, indenting continuation lines."""
    tag = f" #{category}" if category and category != "uncategorized" else ""
    lines = text.split('\n')
    first = lines[0] if lines else ''
    out = f"- [{time_s}]{tag} {first}\n"
    for cont in lines[1:]:
        # Indent continuation lines (blank lines stay blank for readability)
        out += (f"  {cont}\n" if cont else "\n")
    return out


@app.post("/api/notes")
async def create_note(body:dict):
    d = VAULT/"Notes"; d.mkdir(exist_ok=True)
    fp = d/f"{today_s()}.md"
    now = datetime.now().strftime("%H:%M")
    cat = body.get("category","")
    entry = _format_note_entry(now, cat, body['text'])
    if fp.exists():
        fp.write_text(fp.read_text("utf-8")+entry,"utf-8")
    else:
        fp.write_text(f"# {today_s()} 速记\n\n{entry}","utf-8")
    _auto_growth()
    return {"ok":True,"time":now}

@app.get("/api/notes")
async def get_notes(category:str=None):
    d = VAULT/"Notes"
    if not d.exists(): return []
    results = []
    for fp in sorted(d.glob("*.md"), reverse=True):
        items = _parse_notes_file(fp)
        if category and category != "all":
            items = [it for it in items if it["category"] == category]
        if items: results.append({"date":fp.stem,"items":items,"path":str(fp.relative_to(VAULT))})
    return results

@app.get("/api/notes/file/{date_str}")
async def get_note_file(date_str:str):
    fp = VAULT/"Notes"/f"{date_str}.md"
    if not fp.exists(): raise HTTPException(404)
    return {"path":str(fp.relative_to(VAULT)),"raw":fp.read_text("utf-8")}

@app.delete("/api/notes/{date_str}/{idx}")
async def delete_note_item(date_str:str, idx:int):
    """Delete a note entry (including its continuation lines) by date+index."""
    fp = VAULT/"Notes"/f"{date_str}.md"
    if not fp.exists(): raise HTTPException(404)
    lines = fp.read_text("utf-8").split('\n')
    entry_starts = [i for i, l in enumerate(lines) if NOTE_ENTRY_RE.match(l)]
    if idx < 0 or idx >= len(entry_starts):
        raise HTTPException(400, "Index out of range")
    start = entry_starts[idx]
    end = entry_starts[idx+1] if idx+1 < len(entry_starts) else len(lines)
    del lines[start:end]
    # Trim trailing blank lines
    while lines and lines[-1] == '':
        lines.pop()
    remaining = [l for l in lines if NOTE_ENTRY_RE.match(l)]
    if not remaining:
        fp.unlink()
    else:
        fp.write_text('\n'.join(lines) + '\n', "utf-8")
    return {"ok": True}


# ── API: Media Upload (voice/image) ──────────────────
MEDIA.mkdir(exist_ok=True)
MAX_UPLOAD_MB = 50

@app.post("/api/media/upload")
async def upload_media(file: UploadFile = File(...)):
    ext = Path(file.filename or "file").suffix or ".bin"
    if ext.lower() not in ('.webm','.mp3','.wav','.ogg','.m4a','.png','.jpg','.jpeg','.gif','.webp','.heic'):
        raise HTTPException(400, "Unsupported file type")
    uid = uuid.uuid4().hex[:8]
    fname = f"{today_s()}_{uid}{ext}"
    fp = MEDIA / fname
    size = 0
    with open(fp, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                f.close(); fp.unlink(missing_ok=True)
                raise HTTPException(413, f"文件超过 {MAX_UPLOAD_MB}MB 限制")
            f.write(chunk)
    return {"ok":True,"filename":fname,"url":f"/media/{fname}","size":fp.stat().st_size}

app.mount("/media", StaticFiles(directory=str(MEDIA)), name="media")


# ── API: AI (multi-provider) ──────────────────────────
@app.post("/api/ai")
async def ai_ask(body:dict):
    prompt = body.get("prompt","")
    context = body.get("context","")
    full_prompt = f"Context:\n{context}\n\n{prompt}" if context else prompt

    ome = get_ome()
    if ome:
        # Inject today's context as a remember so Ome has it
        daily_fp = find_daily()
        day_ctx = f"今天是 {today_s()}, Day {day_n()}, W{week_n()}, Q{quarter_n()}"
        try:
            with _ome_lock:
                result = ome.chat_rich(f"{day_ctx}\n{full_prompt}")
            _auto_growth()
            return {
                "ok": True,
                "response": result.get("reply", ""),
                "provider": "ome",
                "memories_recalled": result.get("memories_recalled", []),
                "emotion": result.get("emotion"),
                "bond": result.get("bond"),
                "evolution_pending": result.get("evolution_pending", False),
                "phase": result.get("phase"),
                "follow_ups": result.get("follow_ups", []),
                "memory_impact": result.get("memory_impact"),
            }
        except Exception as e:
            return {"ok": False, "error": f"Ome error: {e}"}

    # Fallback: direct API call (legacy, when omnity-ome not installed)
    import requests as req
    settings = load_settings()
    mode = settings.get("ai_mode", "none")
    if mode == "none":
        return {"ok":False, "error":"请在设置中配置AI服务"}
    system_msg = f"你是 Ome365 AI 助手。今天是 {today_s()}, Day {day_n()}, W{week_n()}, Q{quarter_n()}。请用简洁有力的中文回答。"

    def _do_ask_sync():
        if mode == "api":
            base_url = settings.get("api_base_url","").rstrip("/")
            api_key = settings.get("api_key","")
            model_name = settings.get("api_model","")
            if not all([base_url, api_key, model_name]):
                return {"ok":False, "error":"请在设置中填写完整的 API 配置"}
            try:
                headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}
                payload = {"model":model_name,"max_tokens":1024,"messages":[
                    {"role":"system","content":system_msg},{"role":"user","content":full_prompt}]}
                resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120, **_proxy_kwargs())
                resp.raise_for_status()
                return {"ok":True, "response":resp.json()["choices"][0]["message"]["content"], "provider":"api"}
            except Exception as e:
                return {"ok":False, "error":str(e)}
        return {"ok":False, "error":f"未知模式: {mode}"}

    return await asyncio.to_thread(_do_ask_sync)

@app.get("/api/ai/session")
async def ai_session_info():
    settings = load_settings()
    return {"session_id": "sdk", "name": "Ome365", "provider": settings.get("ai_mode","none")}

# ── 速记中的"改名意图"识别：跳过 LLM，直连 EEG rename pipeline ──
# 支持格式：
#   — → —       / — -> —        / —=>—
#   — 是 —      / — 就是 —      / — = —
#   — 改成 —    / — 改叫 —      / 把—改成—
_RENAME_RE = re.compile(
    r'^\s*(?:把\s*)?(\S{1,30}?)\s*(?:→|->|=>|=|就是|是|改成|改为|改叫|应该叫)\s*(\S{1,30}?)\s*[。.!！]?\s*$'
)


def _detect_rename_intent(text: str):
    """如果是简洁的 X→Y 语句，返回 (old, new)；否则 None。"""
    if not text or '\n' in text.strip():
        # 多行输入不走快路径，交给 LLM
        return None
    m = _RENAME_RE.match(text.strip())
    if not m:
        return None
    old, new = m.group(1).strip(), m.group(2).strip()
    if not old or not new or old == new or len(old) < 1 or len(new) < 1:
        return None
    # 明显不像改名的 stop words
    if old in {"今天", "明天", "我", "他", "她", "这"} or new in {"今天", "明天"}:
        return None
    return old, new


@app.post("/api/ai/smart-input")
async def ai_smart_input(body: dict):
    """AI分析非结构化输入，提取联系人/事件/待办/笔记等结构化数据。"""
    import requests as req
    text = body.get("text", "").strip()
    if not text:
        return {"ok": False, "error": "请输入内容"}

    # —— 快路径：检测到改名意图，跳过 LLM，直接 scan vault ——
    intent = _detect_rename_intent(text)
    if intent and _EEG_OK:
        old, new = intent
        preview = _eeg_scan(old, limit=500)
        return {
            "ok": True,
            "data": {
                "type": "rename",
                "old": old,
                "new": new,
                "total_files": preview["total_files"],
                "total_matches": preview["total_matches"],
                "hits": preview["hits"][:20],  # UI 预览最多 20 个文件
                "summary": f"检测到改名指令：{old} → {new}（命中 {preview['total_files']} 个文件 / {preview['total_matches']} 处）",
            }
        }

    settings = load_settings()
    if settings.get("ai_mode", "none") == "none":
        return {"ok": False, "error": "请先在设置中配置AI"}

    # Gather existing contacts for matching
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    existing_contacts = []
    for fp in sorted(PEOPLE_DIR.glob("*.md")):
        c = parse_contact(fp)
        existing_contacts.append({"name": c["name"], "slug": c["slug"], "company": c.get("company",""), "title": c.get("title","")})

    # Only send names+slugs of existing contacts (save tokens)
    contact_names = [{"name":c["name"],"slug":c["slug"]} for c in existing_contacts]

    prompt = f"""从以下用户输入中提取结构化数据。今天：{today_s()}

已有联系人（用于匹配action为update还是new）：
{json.dumps(contact_names, ensure_ascii=False)[:1500]}

输出JSON：
{{"contacts":[{{"action":"new"|"update","slug":"匹配到的slug或空","name":"姓名","company":"公司","title":"职位","category":"industry|friend|partner|team|mentor|talent|investor","met_context":"认识场景","info":"关键信息"}}],
"interactions":[{{"contact_name":"联系人姓名","method":"微信|电话|面聊|其他","summary":"互动摘要（一句话）"}}],
"todos":[{{"text":"待办内容","time":"HH:MM或空","date":"YYYY-MM-DD或空（明天及以后的任务填日期）","priority":"high|normal"}}],
"notes":[{{"text":"值得记录的信息或洞察（每条独立主题，加#标签前缀）","category":"标签名"}}],
"summary":"一句话总结"}}

规则：
- **带时间的事件（如"9:30 开会"、"下午3点见客户"）必须提取为todos**，time填HH:MM格式，text填事件内容
- 日程、会议、约见、电话等时间相关的都算todos，不要放进notes
- notes的每条要聚焦单一主题，category用简短中文标签（如 业务数据/产品与技术/团队与挑战/战略方向/人物洞察）
- 联系人只提取有明确姓名的，不要把泛指的人算进去
- todos只排除已完成的事项，未来要做的（含日程会议）都要提取
- interactions按人分条，同一个人多次互动可以合并
- 只输出JSON

用户输入：
{text}"""

    def _do_smart_input_sync():
        try:
            if settings.get("ai_mode") == "api":
                base_url = settings.get("api_base_url","").rstrip("/")
                api_key = settings.get("api_key","")
                model_name = settings.get("api_model","")
                headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json",
                           "HTTP-Referer":"https://ome365.app","X-Title":"Ome365"}
                payload = {"model":model_name,"max_tokens":2000,"temperature":0,"messages":[
                    {"role":"system","content":"你是结构化信息提取器。只输出合法JSON，不要输出任何其他文字。"},
                    {"role":"user","content":prompt}
                ]}
                resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120, **_proxy_kwargs())
                resp.raise_for_status()
                ai_text = resp.json()["choices"][0]["message"]["content"].strip()
            elif settings.get("ai_mode") == "ollama":
                ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
                payload = {"model":settings.get("ollama_model","llama3.1"),"temperature":0,"messages":[
                    {"role":"system","content":"你是结构化信息提取器。只输出合法JSON，不要输出任何其他文字。"},
                    {"role":"user","content":prompt}
                ],"stream":False}
                resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=120, **_proxy_kwargs())
                resp.raise_for_status()
                ai_text = resp.json().get("message",{}).get("content","").strip()
            else:
                return {"ok":False, "error":f"未知AI模式: {settings.get('ai_mode')}"}

            # Parse JSON from AI response (handle markdown code blocks)
            cleaned = re.sub(r'^```(?:json)?\s*', '', ai_text)
            cleaned = re.sub(r'\s*```\s*$', '', cleaned)
            cleaned = cleaned.strip()
            result = json.loads(cleaned)

            # Store extracted summary in Ome memory (not raw text)
            ome = get_ome()
            if ome and result.get("summary"):
                try:
                    with _ome_lock:
                        ome.remember(result["summary"], source="smart_input")
                except:
                    pass

            return {"ok": True, "data": result}
        except json.JSONDecodeError:
            return {"ok": False, "error": "AI返回格式异常，请重试", "raw": ai_text[:500] if 'ai_text' in dir() else ''}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return await asyncio.to_thread(_do_smart_input_sync)

@app.post("/api/ai/smart-input/apply")
async def ai_smart_input_apply(body: dict):
    """Apply extracted structured data: create/update contacts, add todos, add notes, add interactions.
    特殊路径：data.type=='rename' 走 EEG vault 批量改名。"""
    results = {"contacts_created":0, "contacts_updated":0, "interactions_added":0,
               "todos_added":0, "notes_added":0,
               "files_renamed":0, "replacements":0}
    data = body.get("data", {})

    # —— 改名快路径 ——
    if data.get("type") == "rename" and _EEG_OK:
        old = (data.get("old") or "").strip()
        new = (data.get("new") or "").strip()
        if not old or not new or old == new:
            return {"ok": False, "error": "old/new 不合法"}
        # 1. 批量内容替换
        r = _eeg_rename(old, new, dry_run=False, file_filter=None)
        results["files_renamed"] = len(r.get("changed", []))
        results["replacements"] = r.get("total", 0)
        # 2. 如果 Contacts/people/{old}.md 存在，重命名该文件并更新 frontmatter.name
        old_fp = PEOPLE_DIR / f"{old}.md"
        new_fp = PEOPLE_DIR / f"{new}.md"
        if old_fp.exists() and not new_fp.exists():
            try:
                raw = old_fp.read_text("utf-8")
                raw = re.sub(r'^(name:\s*).*$', f'\\g<1>{new}', raw, count=1, flags=re.MULTILINE)
                new_fp.write_text(raw, "utf-8")
                old_fp.unlink()
                results["contacts_updated"] += 1
            except Exception as e:
                results["contact_rename_error"] = str(e)
        # 3. 追加到 EEG：如 new 已是实体，把 old 加入 aliases；否则新建 people 实体
        try:
            alias_res = _eeg_add_alias(new, old)
            if not alias_res.get("ok"):
                # 实体不存在 → 新建
                ed = Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve() / "Knowledge" / "entities" / "people"
                ed.mkdir(parents=True, exist_ok=True)
                slug = re.sub(r'[^\w\u4e00-\u9fff]', '_', new).strip('_').lower() or new
                fp = ed / f"{slug}.md"
                if not fp.exists():
                    fp.write_text(
                        f"---\nid: {slug}\ntype: person\nname: {new}\naliases:\n  - {old}\ntenant: longfor\nconfidence: medium\nevidence:\n  - 速记改名: {today_s()}\nupdated_at: {today_s()}\n---\n\n# {new}\n\n速记改名自动建档：{old} → {new}，{today_s()}。\n",
                        "utf-8"
                    )
                    results["entity_created"] = new
                else:
                    # 再试一次 alias（可能之前没刷新缓存）
                    _eeg_add_alias(new, old)
            else:
                results["entity_alias_added"] = f"{old} → {new}"
        except Exception as e:
            results["entity_error"] = str(e)
        return {"ok": True, "results": results, "rename_detail": r.get("changed", [])[:50]}


    # 1. Process contacts
    for c in data.get("contacts", []):
        name = c.get("name","").strip()
        if not name:
            continue
        if c.get("action") == "update" and c.get("slug"):
            # Update existing contact
            fp = PEOPLE_DIR / f"{c['slug']}.md"
            if fp.exists():
                meta = parse_yaml_meta(fp.read_text("utf-8"))
                raw = fp.read_text("utf-8")
                m = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw, re.DOTALL)
                if m:
                    content = raw[m.end():]
                    if c.get("company"): meta["company"] = c["company"]
                    if c.get("title"): meta["title"] = c["title"]
                    if c.get("info"):
                        content = content.rstrip() + f"\n\n## 补充信息\n{c['info']}\n"
                    write_md(fp, meta, content)
                    results["contacts_updated"] += 1
        else:
            # Create new contact
            slug = re.sub(r'[^\w\u4e00-\u9fff]','-', name)[:30].strip('-').lower()
            fp = PEOPLE_DIR / f"{slug}.md"
            if fp.exists():
                continue  # Already exists, skip
            PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
            meta = {
                "name": name,
                "company": c.get("company",""),
                "title": c.get("title",""),
                "category": c.get("category","industry"),
                "tier": "B",
                "tags": [],
                "location": "",
                "wechat": "",
                "phone": "",
                "email": "",
                "met_date": today_s(),
                "met_context": c.get("met_context",""),
                "last_contact": today_s(),
                "next_followup": (date.today()+timedelta(days=14)).isoformat(),
            }
            content = f"""# {name} · {c.get('title','')}

## 关系背景
{c.get('info','（待补充）')}

## 联系记录
| 日期 | 方式 | 内容摘要 |
|------|------|---------|
| {today_s()} | 初识 | {c.get('met_context','')} |

## 备注
"""
            write_md(fp, meta, content)
            results["contacts_created"] += 1

    # 2. Process interactions
    for inter in data.get("interactions", []):
        contact_name = inter.get("contact_name","").strip()
        if not contact_name:
            continue
        # Find matching contact by name
        for fp in PEOPLE_DIR.glob("*.md"):
            c = parse_contact(fp)
            if c["name"] == contact_name:
                raw = fp.read_text("utf-8")
                m_meta = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw, re.DOTALL)
                if m_meta:
                    meta = parse_yaml_meta(raw)
                    content = raw[m_meta.end():]
                    row = f"| {today_s()} | {inter.get('method','微信')} | {inter.get('summary','')} |"
                    content = content.replace("## 备注", f"{row}\n\n## 备注")
                    meta["last_contact"] = today_s()
                    write_md(fp, meta, content)
                    results["interactions_added"] += 1
                break

    # 3. Process todos
    for todo in data.get("todos", []):
        text = todo.get("text","").strip()
        if not text:
            continue
        time_str = todo.get("time","").strip()
        target_date = todo.get("date","").strip()  # AI may extract a future date
        # Determine which day's file to write to
        if target_date and target_date > today_s():
            fp = find_daily(target_date)
        else:
            fp = find_daily()
        if time_str and re.match(r'\d{2}:\d{2}', time_str):
            text = f"[{time_str}] {text}"
        if not fp.exists():
            ds = target_date or today_s()
            wd_idx = date.fromisoformat(ds).weekday()
            fp.write_text(f"# {ds} {WEEKDAYS[wd_idx]}\n\n## 任务\n- [ ] {text}\n", "utf-8")
        else:
            raw = fp.read_text("utf-8")
            if "## 任务" in raw:
                raw = raw.replace("## 任务\n", f"## 任务\n- [ ] {text}\n", 1)
            else:
                raw += f"\n## 任务\n- [ ] {text}\n"
            fp.write_text(raw, "utf-8")
        results["todos_added"] += 1

    # 4. Process notes
    for note in data.get("notes", []):
        text = note.get("text","").strip()
        if not text:
            continue
        d = VAULT / "Notes"
        d.mkdir(exist_ok=True)
        fp = d / f"{today_s()}.md"
        now = datetime.now().strftime("%H:%M")
        cat = note.get("category","")
        tag = f" #{cat}" if cat else ""
        entry = f"- [{now}]{tag} {text}\n"
        if fp.exists():
            fp.write_text(fp.read_text("utf-8")+entry, "utf-8")
        else:
            fp.write_text(f"# {today_s()} 速记\n\n{entry}", "utf-8")
        results["notes_added"] += 1

    total_ops = results["contacts_created"] + results["todos_added"] + results["notes_added"] + results["interactions_added"]
    if total_ops > 0:
        _auto_growth(total_ops)
    return {"ok": True, "results": results}

@app.post("/api/ai/reset")
async def ai_reset_session():
    return {"ok": True}


# ── API: Settings ─────────────────────────────────────
def mask_key(key: str) -> str:
    """Mask API key — show only last 4 chars for security."""
    if not key or len(key) < 8:
        return key
    return "••••••••" + key[-4:]

@app.get("/api/settings")
async def get_settings():
    settings = load_settings()
    masked = dict(settings)
    # Mask sensitive keys
    for field in ("api_key",):
        if masked.get(field):
            masked[field] = mask_key(masked[field])
    return masked

@app.put("/api/settings")
async def update_settings(body: dict):
    settings = load_settings()
    # For API key fields: if the incoming value looks like a masked value (starts with ••),
    # keep the existing stored key instead of overwriting with the masked display value.
    sensitive_fields = ("api_key",)
    for k, v in body.items():
        if k in sensitive_fields and isinstance(v, str) and v.startswith("••"):
            # Don't overwrite — keep existing key
            continue
        settings[k] = v
    save_settings(settings)
    return {"ok": True}

@app.post("/api/settings/test-ai")
async def test_ai_connection():
    import requests as req
    settings = load_settings()
    mode = settings.get("ai_mode","none")
    test_prompt = "请回复「连接成功」四个字。"

    if mode == "none":
        return {"ok":False, "error":"请先选择AI模式"}

    elif mode == "api":
        base_url = settings.get("api_base_url","").rstrip("/")
        api_key = settings.get("api_key","")
        model = settings.get("api_model","")
        if not base_url or not api_key or not model:
            return {"ok":False, "error":"请填写完整的 API 地址、密钥和模型"}
        try:
            headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json",
                       "HTTP-Referer":"https://ome365.app","X-Title":"Ome365"}
            payload = {"model":model,"max_tokens":64,"messages":[{"role":"user","content":test_prompt}]}
            resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=30, **_proxy_kwargs())
            if resp.status_code == 403:
                body_text = resp.text[:300]
                if "region" in body_text.lower():
                    return {"ok":False, "error":f"该模型在当前地区不可用，请换一个模型（如 deepseek/deepseek-chat）。当前: {model}"}
                if "terms of service" in body_text.lower() or "prohibited" in body_text.lower():
                    return {"ok":False, "error":f"该模型的提供商拒绝了请求（可能因地区/代理限制）。建议：换用 deepseek/deepseek-chat，或关闭右上角代理开关后重试。当前: {model}"}
                return {"ok":False, "error":f"API 拒绝访问 (403)，请检查 Key 和模型名。当前: {model}"}
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            return {"ok":True, "response":text}
        except req.exceptions.HTTPError as e:
            return {"ok":False, "error":f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            return {"ok":False, "error":str(e)}

    elif mode == "ollama":
        ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
        model = settings.get("ollama_model","llama3.1")
        try:
            payload = {"model":model,"messages":[{"role":"user","content":test_prompt}],"stream":False}
            resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=60, **_proxy_kwargs())
            resp.raise_for_status()
            text = resp.json().get("message",{}).get("content","")
            return {"ok":True, "response":text}
        except Exception as e:
            return {"ok":False, "error":str(e)}

    return {"ok":False, "error":f"未知模式: {mode}"}


# ── API: Whisper STT ───────────────────────────────────
@app.post("/api/whisper")
async def whisper_transcribe(file: UploadFile = File(...)):
    """
    Accept an audio file upload and transcribe using local Whisper.
    Requires: pip install openai-whisper  OR  pip install faster-whisper
    """
    ext = Path(file.filename or "audio").suffix or ".webm"
    uid = uuid.uuid4().hex[:8]
    tmp_path = MEDIA / f"whisper_{uid}{ext}"
    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Try faster-whisper first (faster, lower memory)
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, info = model.transcribe(str(tmp_path), beam_size=5)
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return {"ok": True, "text": text, "backend": "faster-whisper"}
        except ImportError:
            pass  # Fall through to openai-whisper

        # Try openai-whisper
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(str(tmp_path))
            text = result.get("text","").strip()
            return {"ok": True, "text": text, "backend": "openai-whisper"}
        except ImportError:
            pass

        # Neither available
        return {
            "ok": False,
            "error": "本地 Whisper 未安装。请安装其中之一：\n  pip install faster-whisper\n  pip install openai-whisper"
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ── API: OCR — extract text from image ────────────────
@app.post("/api/ocr")
async def ocr_image(file: UploadFile = File(...)):
    """Extract text from an uploaded image using AI vision or local OCR."""
    import requests as req
    ext = Path(file.filename or "img").suffix or ".png"
    uid = uuid.uuid4().hex[:8]
    tmp_path = MEDIA / f"ocr_{uid}{ext}"
    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Read image as base64 for AI vision
        import base64
        with open(tmp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        _mime_map = {".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".gif":"image/gif",".webp":"image/webp",".bmp":"image/bmp",".heic":"image/heic",".heif":"image/heif"}
        mime = _mime_map.get(ext.lower(), "image/png")

        settings = load_settings()
        mode = settings.get("ai_mode", "none")

        # Strategy 1: Use configured AI with vision capability
        if mode == "api":
            base_url = settings.get("api_base_url","").rstrip("/")
            api_key = settings.get("api_key","")
            model = settings.get("api_model","")
            if all([base_url, api_key, model]):
                headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json",
                           "HTTP-Referer":"https://ome365.app","X-Title":"Ome365"}
                payload = {"model":model,"max_tokens":2000,"messages":[
                    {"role":"user","content":[
                        {"type":"text","text":"请提取这张图片中的所有文字内容。只输出提取到的文字，不要添加额外说明。如果图片没有文字，回复：图片中没有识别到文字。"},
                        {"type":"image_url","image_url":{"url":f"data:{mime};base64,{img_b64}"}}
                    ]}
                ]}
                try:
                    resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60, **_proxy_kwargs())
                    resp.raise_for_status()
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                    return {"ok": True, "text": text, "backend": "ai-vision"}
                except Exception as e:
                    pass  # Fall through to local OCR

        # Strategy 2: Local OCR via pytesseract
        try:
            from PIL import Image
            import pytesseract
            img = Image.open(tmp_path)
            text = pytesseract.image_to_string(img, lang="chi_sim+eng").strip()
            if text:
                return {"ok": True, "text": text, "backend": "tesseract"}
            return {"ok": False, "error": "未识别到文字"}
        except ImportError:
            pass

        return {"ok": False, "error": "请配置 AI（设置中选择支持图片的模型）或安装 pytesseract"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ── API: Contacts / Relationships ─────────────────────
PEOPLE_DIR = VAULT / "Contacts" / "people"

def parse_contact(fp: Path) -> dict:
    """Parse a contact markdown file into structured data."""
    text = fp.read_text("utf-8")
    meta = parse_yaml_meta(text)
    m = re.match(r'^---\s*\n.*?\n---\s*\n', text, re.DOTALL)
    content = text[m.end():] if m else text

    interactions = []
    in_notes = False
    for line in content.split('\n'):
        if re.match(r'^##\s*(Notes|联系记录|互动)', line):
            in_notes = True; continue
        if in_notes and line.startswith('## '):
            in_notes = False; continue
        if in_notes:
            im = re.match(r'^###\s*(\d{4}-\d{2}-\d{2})\s*[—–-]\s*(.*)', line)
            if im:
                interactions.append({"date":im.group(1),"summary":im.group(2).strip()})
            tm = re.match(r'^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\S+)\s*\|\s*(.*?)\s*\|', line)
            if tm:
                interactions.append({"date":tm.group(1),"method":tm.group(2),"summary":tm.group(3)})

    rels = []
    if isinstance(meta.get("relationship_to"), list):
        rels = meta["relationship_to"]
    for line in content.split('\n'):
        rm = re.match(r'^-\s*→\s*\[(.+?)\]\s*[:：]\s*(.+)', line)
        if rm:
            rels.append({"name":rm.group(1).strip(),"type":rm.group(2).strip()})

    last = meta.get("last_contact","")
    days_cold = None
    if last:
        try:
            days_cold = (date.today() - date.fromisoformat(last)).days
        except: pass

    return {
        "file": fp.name,
        "slug": fp.stem,
        "name": meta.get("name", fp.stem),
        "company": meta.get("company", meta.get("org","")),
        "title": meta.get("title", meta.get("role","")),
        "category": meta.get("category", meta.get("field","industry")),
        "tier": meta.get("tier", meta.get("priority","C")),
        "tags": meta.get("tags", []),
        "wechat": meta.get("wechat",""),
        "phone": meta.get("phone",""),
        "email": meta.get("email",""),
        "location": meta.get("location",""),
        "met_date": meta.get("met_date",""),
        "met_context": meta.get("met_context",""),
        "last_contact": last,
        "next_followup": meta.get("next_followup", meta.get("next_contact","")),
        "days_cold": days_cold,
        "relationships": rels,
        "interactions": interactions[-10:],
        "interaction_count": len(interactions),
        "content": content,
    }

# ── ENTERPRISE ENTITY GRAPH (EEG) ─────────────────────
# 统一企业术语/人名/组织/产品的"常识层"。见 docs/EEG.md
try:
    from entity_registry import (
        all_entities as _eeg_all,
        get_entity as _eeg_get,
        list_entities as _eeg_list,
        search as _eeg_search,
        asr_rules as _eeg_asr_rules,
        resolve as _eeg_resolve,
        stats as _eeg_stats,
        scan_vault as _eeg_scan,
        rename_in_vault as _eeg_rename,
        add_alias_to_entity as _eeg_add_alias,
    )
    _EEG_OK = True
except Exception as _e:
    _EEG_OK = False
    _EEG_ERR = str(_e)


def _require_eeg():
    if not _EEG_OK:
        raise HTTPException(500, f"entity_registry unavailable: {_EEG_ERR}")


@app.get("/api/entities")
async def eeg_list(type: str = None, tenant: str = None, q: str = None):
    """列表：支持 type / tenant / q 过滤。"""
    _require_eeg()
    if q:
        res = _eeg_search(q, type_filter=type, tenant=tenant)
    else:
        res = _eeg_list(type_filter=type, tenant=tenant)
    return {"entities": res, "count": len(res)}


@app.get("/api/entities/stats")
async def eeg_stats_api():
    _require_eeg()
    return _eeg_stats()


@app.get("/api/entities/asr")
async def eeg_asr(tenant: str = "longfor"):
    """返回 ASR 规则字典（app.js 启动时热加载）。"""
    _require_eeg()
    return {"rules": _eeg_asr_rules(tenant=tenant), "tenant": tenant}


@app.post("/api/entities/resolve")
async def eeg_resolve_api(body: dict):
    """别名 → 规范名；所有送进 LLM / 检索前的文本都应该过一遍。"""
    _require_eeg()
    text = body.get("text", "") or ""
    tenant = body.get("tenant") or "longfor"
    return _eeg_resolve(text, tenant=tenant)


@app.post("/api/entities/scan")
async def eeg_scan_api(body: dict):
    """全 vault 搜索一个字符串，返回所有文件 + 行号。
    用于"—→—"的第 1 步：先看这个名字到底出现在哪些文件里。"""
    _require_eeg()
    needle = (body.get("needle") or body.get("text") or "").strip()
    limit = int(body.get("limit") or 200)
    if not needle:
        raise HTTPException(400, "needle required")
    return _eeg_scan(needle, limit=limit)


@app.post("/api/entities/rename")
async def eeg_rename_api(body: dict):
    """批量替换 old→new。
    Body: { old: "—", new: "—", dry_run: true/false, files: ["a.md",...]? , add_alias: bool }
    - dry_run=True（默认）：只返回将改动的文件 + 命中数
    - dry_run=False：真正写回磁盘
    - add_alias=True：同时把 old 加到 EEG 中 new 的 aliases 里（下次 ASR 自动修正）
    """
    _require_eeg()
    old = (body.get("old") or "").strip()
    new = (body.get("new") or "").strip()
    dry_run = bool(body.get("dry_run", True))
    files = body.get("files")
    add_alias = bool(body.get("add_alias", False))
    if not old or not new:
        raise HTTPException(400, "old and new required")
    result = _eeg_rename(old, new, dry_run=dry_run, file_filter=files)
    if not dry_run and add_alias:
        alias_result = _eeg_add_alias(new, old)
        result["alias_added"] = alias_result
    return result


@app.post("/api/entities/alias")
async def eeg_add_alias_api(body: dict):
    """给某个已有实体追加一条别名（落到 frontmatter）。"""
    _require_eeg()
    entity = (body.get("entity") or body.get("name") or "").strip()
    alias = (body.get("alias") or "").strip()
    if not entity or not alias:
        raise HTTPException(400, "entity and alias required")
    return _eeg_add_alias(entity, alias)


@app.get("/api/entities/{type}/{id}")
async def eeg_get(type: str, id: str):
    _require_eeg()
    e = _eeg_get(id)
    if not e:
        raise HTTPException(404, f"entity {id} not found")
    # Normalize type ("people" vs "person")
    type_norm = type.rstrip("s")
    if e["type"] != type_norm and type_norm not in ("*", "any"):
        raise HTTPException(404, f"entity {id} exists but type={e['type']} not {type_norm}")
    return e


@app.get("/api/cockpit/config")
async def get_cockpit_config():
    """驾舱可视化配置（SECTION_TAXONOMY / orgTree / PERSON_DISPLAY_MAP / ASR_FIXES / KNOWN_SPEAKER_MAPS）。
    优先读 .app/cockpit_config.json（本地真实数据，gitignored）；不存在则读 .app/cockpit_config.sample.json（代码仓 sample）。
    """
    app_dir = Path(__file__).parent
    live = app_dir / "cockpit_config.json"
    sample = app_dir / "cockpit_config.sample.json"
    target = live if live.exists() else sample
    if not target.exists():
        return {"_source": "empty", "SECTION_TAXONOMY": [], "PERSON_DISPLAY_MAP": {},
                "orgTree": [], "ASR_FIXES": [], "KNOWN_SPEAKER_MAPS": {}}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"failed to load {target.name}: {e}")
    data["_source"] = target.name
    return data


@app.get("/api/contacts")
async def list_contacts(category:str=None, tier:str=None):
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    contacts = []
    for fp in sorted(PEOPLE_DIR.glob("*.md")):
        c = parse_contact(fp)
        if category and c["category"] != category: continue
        if tier and c["tier"] != tier: continue
        contacts.append(c)
    return contacts

@app.get("/api/contacts/graph")
async def contacts_graph():
    """Generate force-graph compatible data with enhanced info."""
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    cat_map = contact_cat_map()
    nodes = []
    links = []
    name_to_slug = {}

    for fp in sorted(PEOPLE_DIR.glob("*.md")):
        c = parse_contact(fp)
        name_to_slug[c["name"]] = c["slug"]
        cat_info = cat_map.get(c["category"], {})
        nodes.append({
            "id": c["slug"],
            "name": c["name"],
            "company": c["company"],
            "title": c["title"],
            "category": c["category"],
            "category_name": cat_info.get("name", c["category"]),
            "tier": c["tier"],
            "val": TIER_SIZES.get(c["tier"], 2),
            "color": cat_info.get("color", "#666"),
            "days_cold": c["days_cold"],
            "interaction_count": c["interaction_count"],
        })

    # Build edges
    for fp in sorted(PEOPLE_DIR.glob("*.md")):
        c = parse_contact(fp)
        for rel in c["relationships"]:
            target_name = rel.get("name","")
            target_slug = name_to_slug.get(target_name)
            if target_slug:
                links.append({
                    "source": c["slug"],
                    "target": target_slug,
                    "type": rel.get("type",""),
                })

    # If no explicit relationships, create links by shared company
    if not links:
        company_groups = {}
        for n in nodes:
            if n["company"]:
                company_groups.setdefault(n["company"], []).append(n["id"])
        for company, slugs in company_groups.items():
            for i in range(len(slugs)):
                for j in range(i+1, len(slugs)):
                    links.append({"source":slugs[i],"target":slugs[j],"type":"同公司"})

    # Add a center "me" node
    settings = load_settings()
    center_name = settings.get("user_name","") or "用户"
    nodes.insert(0, {
        "id": "__me__",
        "name": center_name,
        "company": "",
        "title": "",
        "category": "team",
        "category_name": "我",
        "tier": "A",
        "val": 12,
        "color": "#c8a96e",
        "days_cold": None,
        "interaction_count": 0,
    })
    for n in nodes[1:]:
        links.append({"source":"__me__","target":n["id"],"type":"认识"})

    return {"nodes":nodes,"links":links,"categories":load_contact_categories()}

@app.get("/api/contacts/cold")
async def contacts_going_cold():
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    cold = []
    for fp in sorted(PEOPLE_DIR.glob("*.md")):
        c = parse_contact(fp)
        if c["days_cold"] is None: continue
        threshold = {"A":14,"B":30,"C":90}.get(c["tier"], 90)
        if c["days_cold"] >= threshold:
            cold.append({**c, "threshold": threshold, "overdue_days": c["days_cold"] - threshold})
    return sorted(cold, key=lambda x: (-{"A":3,"B":2,"C":1}.get(x["tier"],0), -x["days_cold"]))

@app.get("/api/contacts/{slug}")
async def get_contact(slug:str):
    fp = PEOPLE_DIR / f"{slug}.md"
    if not fp.exists(): raise HTTPException(404)
    c = parse_contact(fp)
    c["raw"] = fp.read_text("utf-8")
    return c

@app.post("/api/contacts")
async def create_contact(body:dict):
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    name = body.get("name","").strip()
    if not name: raise HTTPException(400, "Name required")
    slug = re.sub(r'[^\w\u4e00-\u9fff]','-', name)[:30].strip('-').lower()
    fp = PEOPLE_DIR / f"{slug}.md"

    meta = {
        "name": name,
        "company": body.get("company",""),
        "title": body.get("title",""),
        "category": body.get("category","industry"),
        "tier": body.get("tier","B"),
        "tags": body.get("tags",[]),
        "location": body.get("location",""),
        "wechat": body.get("wechat",""),
        "phone": body.get("phone",""),
        "email": body.get("email",""),
        "met_date": today_s(),
        "met_context": body.get("met_context",""),
        "last_contact": today_s(),
        "next_followup": (date.today()+timedelta(days=14)).isoformat(),
    }
    content = f"""# {name} · {body.get('title','')}

## 关系背景
{body.get('background','（待补充）')}

## 联系记录
| 日期 | 方式 | 内容摘要 |
|------|------|---------|
| {today_s()} | 初识 | {body.get('met_context','')} |

## 备注
"""
    write_md(fp, meta, content)
    _auto_growth()
    return {"ok":True,"slug":slug}

@app.post("/api/contacts/merge")
async def merge_contacts(body:dict):
    """Merge two contacts. Keep primary, merge secondary's data into it, delete secondary."""
    primary_slug = body.get("primary","")
    secondary_slug = body.get("secondary","")
    if not primary_slug or not secondary_slug:
        raise HTTPException(400, "Need primary and secondary slugs")
    fp1 = PEOPLE_DIR / f"{primary_slug}.md"
    fp2 = PEOPLE_DIR / f"{secondary_slug}.md"
    if not fp1.exists(): raise HTTPException(404, f"Primary {primary_slug} not found")
    if not fp2.exists(): raise HTTPException(404, f"Secondary {secondary_slug} not found")

    # Parse both
    raw1 = fp1.read_text("utf-8")
    raw2 = fp2.read_text("utf-8")
    meta1 = parse_yaml_meta(raw1)
    meta2 = parse_yaml_meta(raw2)

    # Merge: fill empty fields in primary from secondary
    for k in ["company","title","location","wechat","phone","email","met_context"]:
        if not meta1.get(k) and meta2.get(k):
            meta1[k] = meta2[k]

    # Merge interaction tables
    # Extract table rows from secondary
    sec_rows = []
    in_table = False
    for line in raw2.split('\n'):
        if '联系记录' in line: in_table = True; continue
        if in_table and line.startswith('|') and not line.startswith('|---') and not line.startswith('| 日期'):
            sec_rows.append(line)
        if in_table and line.startswith('## ') and '联系' not in line:
            break

    # Insert secondary rows into primary
    if sec_rows:
        lines1 = raw1.split('\n')
        insert_idx = -1
        in_t = False
        for i, line in enumerate(lines1):
            if '联系记录' in line: in_t = True; continue
            if in_t and line.startswith('|') and not line.startswith('|---'):
                insert_idx = i
            if in_t and line.startswith('## ') and '联系' not in line:
                break
        if insert_idx > 0:
            for row in sec_rows:
                insert_idx += 1
                lines1.insert(insert_idx, row)
            # Re-parse to get content after meta
            m1 = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw1, re.DOTALL)
            content1 = '\n'.join(lines1[len(raw1[:m1.end()].split('\n'))-1:]) if m1 else '\n'.join(lines1)
            write_md(fp1, meta1, content1)
        else:
            m1 = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw1, re.DOTALL)
            write_md(fp1, meta1, raw1[m1.end():] if m1 else raw1)
    else:
        m1 = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw1, re.DOTALL)
        write_md(fp1, meta1, raw1[m1.end():] if m1 else raw1)

    # Delete secondary
    fp2.unlink()
    return {"ok":True,"merged_into":primary_slug,"deleted":secondary_slug}

@app.put("/api/contacts/{slug}")
async def update_contact(slug:str, body:dict):
    """Update an existing contact's frontmatter fields."""
    fp = PEOPLE_DIR / f"{slug}.md"
    if not fp.exists(): raise HTTPException(404)

    raw = fp.read_text("utf-8")
    # Parse existing meta and content
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw, re.DOTALL)
    if not m: raise HTTPException(400, "Invalid file format")

    meta = parse_yaml_meta(raw)
    content = raw[m.end():]

    # Update fields from body
    updatable = ["name","company","title","category","tier","location","wechat","phone","email","met_context","next_followup","tags"]
    for field in updatable:
        if field in body:
            meta[field] = body[field]

    # Also update background in content if provided
    if "background" in body:
        bg = body["background"]
        content = re.sub(r'(## 关系背景\n).*?(\n## )', rf'\1{bg}\n\2', content, flags=re.DOTALL)

    write_md(fp, meta, content)

    # Handle rename: if name changed, rename file
    new_name = body.get("name","").strip()
    if new_name and new_name != slug:
        new_slug = re.sub(r'[^\w\u4e00-\u9fff]','-', new_name)[:30].strip('-').lower()
        new_fp = PEOPLE_DIR / f"{new_slug}.md"
        if not new_fp.exists() and new_slug != slug:
            fp.rename(new_fp)
            return {"ok":True,"slug":new_slug}

    return {"ok":True,"slug":slug}

@app.post("/api/contacts/{slug}/interact")
async def add_interaction(slug:str, body:dict):
    fp = PEOPLE_DIR / f"{slug}.md"
    if not fp.exists(): raise HTTPException(404)
    raw = fp.read_text("utf-8")
    method = body.get("method","微信")
    summary = body.get("summary","")
    d = today_s()

    table_row = f"| {d} | {method} | {summary} |"
    lines = raw.split('\n')
    in_table = False
    last_row = -1
    for i, line in enumerate(lines):
        if '联系记录' in line or 'Notes' in line:
            in_table = True; continue
        if in_table and line.startswith('|') and not line.startswith('|---'):
            last_row = i
        if in_table and line.startswith('## ') and '联系' not in line and 'Notes' not in line:
            break
    if last_row > 0:
        lines.insert(last_row + 1, table_row)
    else:
        lines.append(table_row)

    raw_new = '\n'.join(lines)
    raw_new = re.sub(r'last_contact:\s*\S+', f'last_contact: {d}', raw_new)
    tier_match = re.search(r'tier:\s*(\S+)', raw_new)
    tier = tier_match.group(1) if tier_match else "B"
    next_days = {"A":14,"B":30,"C":90}.get(tier, 30)
    next_date = (date.today()+timedelta(days=next_days)).isoformat()
    raw_new = re.sub(r'next_followup:\s*\S+', f'next_followup: {next_date}', raw_new)
    if 'next_contact:' in raw_new:
        raw_new = re.sub(r'next_contact:\s*\S+', f'next_contact: {next_date}', raw_new)

    fp.write_text(raw_new, "utf-8")
    return {"ok":True,"next_followup":next_date}


# ── API: Heatmap ──────────────────────────────────────
@app.get("/api/heatmap")
async def heatmap():
    START = get_start()
    today = date.today()
    # Include pre-start days if user is active before official start
    effective_start = min(START, today)
    total_days = max(365, (START - effective_start).days + 365)
    daily_dir = VAULT/"Journal"/"Daily"
    notes_dir = VAULT/"Notes"
    dec_dir = VAULT/"Decisions"
    days = []
    for i in range(total_days):
        d = effective_start + timedelta(days=i); ds = d.isoformat()
        level = 0; detail = []; acts = []  # acts: activity types for color
        dfp = daily_dir/f"{ds}.md"
        if dfp.exists():
            data = parse_md(dfp)
            tasks = [t for t in data["tasks"] if t["text"].strip()]
            done = sum(1 for t in tasks if t["done"])
            total = len(tasks)
            if total > 0:
                pct = done/total
                if pct >= 0.85: level = max(level,4)
                elif pct >= 0.6: level = max(level,3)
                elif pct >= 0.3: level = max(level,2)
                else: level = max(level,1)
                detail.append(f"任务 {done}/{total}")
                acts.append("task")
            if data["content"].strip():
                if level == 0: level = 1
                detail.append("有日记")
                acts.append("journal")
        nfp = notes_dir/f"{ds}.md"
        if nfp.exists():
            cnt = nfp.read_text("utf-8").count("\n- [")
            if cnt > 0: level = max(level,1); detail.append(f"速记 {cnt}"); acts.append("note")
        for fp in (dec_dir.glob(f"{ds}-*.md") if dec_dir.exists() else []):
            level = max(level,2); detail.append("决策"); acts.append("decision"); break
        if d > date.today() and level == 0: level = -1
        days.append({"date":ds,"weekday":d.weekday(),"level":level,"detail":" · ".join(detail),"acts":acts})
    return {"start_date":effective_start.isoformat(),"days":days}


# ── API: File Browser ─────────────────────────────────
@app.get("/api/file")
async def read_file(path:str):
    fp = VAULT/path
    if not fp.exists(): raise HTTPException(404)
    try:
        resolved = fp.resolve()
        if not str(resolved).startswith(str(VAULT.resolve())):
            raise HTTPException(403, "Access denied")
    except (ValueError, OSError):
        raise HTTPException(403, "Invalid path")
    return parse_md(fp)

FOLDER_ICONS = {
    "根目录":"📋","Journal":"📅","Journal/Daily":"📅","Journal/Weekly":"📋",
    "Journal/Quarterly":"📊","Contacts":"👤","Contacts/people":"👤",
    "Decisions":"⚡","Notes":"✏️","Projects":"🚀","Templates":"📝",
    "Memory":"🧠","Memory/insights":"💡",
}
FOLDER_ORDER = ["根目录","Journal/Daily","Journal/Weekly","Journal/Quarterly","Notes","Memory","Memory/insights","Decisions","Contacts/people","Projects","Templates"]

FILE_ICONS = {
    ".md": "📄", ".json": "📋", ".py": "🐍", ".js": "📜",
    ".png": "🖼", ".jpg": "🖼", ".jpeg": "🖼", ".gif": "🖼",
    ".mp3": "🎵", ".wav": "🎵", ".webm": "🎵", ".m4a": "🎵",
}

@app.get("/api/tree")
async def file_tree():
    groups = {}
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        rel = Path(root).relative_to(VAULT)
        folder = str(rel) if str(rel) != '.' else '根目录'
        md_files = []
        for f in sorted(files):
            if f.startswith('.'): continue
            ext = Path(f).suffix.lower()
            if ext not in ('.md', '.json', '.txt'): continue
            fp = Path(root)/f
            mtime = fp.stat().st_mtime
            size = fp.stat().st_size
            icon = FILE_ICONS.get(ext, "📄")
            md_files.append({"path":str(rel/f) if str(rel)!='.' else f,"name":f,"mtime":mtime,"size":size,"icon":icon})
        if md_files:
            md_files.sort(key=lambda x: -x["mtime"])
            icon = "📂"
            for prefix, ic in FOLDER_ICONS.items():
                if folder == prefix or folder.startswith(prefix+"/"):
                    icon = ic; break
            groups[folder] = {"folder":folder,"icon":icon,"files":md_files,"count":len(md_files)}

    def sort_key(item):
        folder = item["folder"]
        try: return (FOLDER_ORDER.index(folder), folder)
        except ValueError:
            if folder.startswith("Projects/"): return (7.5, folder)
            return (99, folder)

    return sorted(groups.values(), key=sort_key)


# ── API: Interviews (TicNote) ────────────────────────
TICNOTE_DIR = VAULT / "TicNote"

@app.get("/api/interviews")
async def get_interviews():
    """List all interview date folders and their files."""
    import re as _re
    if not TICNOTE_DIR.exists():
        return []
    results = []
    for d in sorted(TICNOTE_DIR.iterdir(), reverse=True):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        files = []
        for fp in sorted(d.glob("*.md")):
            size = fp.stat().st_size
            raw = fp.read_text("utf-8")
            # Parse YAML frontmatter (--- ... ---) for title, then fall back to first heading
            _lines = raw.split("\n")
            _start = 0
            fm_title = ""
            if _lines and _lines[0].strip() == '---':
                for _li in range(1, len(_lines)):
                    if _lines[_li].strip() == '---':
                        _start = _li + 1
                        break
                    _tm = _re.match(r'^title:\s*(.+)$', _lines[_li])
                    if _tm:
                        fm_title = _tm.group(1).strip()
            first_line = ""
            if not fm_title:
                for _li in range(_start, min(_start + 10, len(_lines))):
                    _cl = _lines[_li].lstrip("# ").strip()
                    if _cl:
                        first_line = _cl
                        break
            stem = fp.stem
            # Parse org/person from filename
            # New format: "千丁BU-智慧建造-—·主题·2026-04-08"
            # Legacy:     "千丁数科-—-主题-04月08日"
            # Split on · first to get prefix, then split prefix on -
            seg0 = stem.split("·")[0]  # "千丁BU-智慧建造-—" or "C1供应链-—"
            dash_parts = seg0.split("-")
            org = dash_parts[0] if len(dash_parts) >= 2 else ""
            person = dash_parts[-1] if len(dash_parts) >= 2 else ""
            # Parse time: ISO "2026-04-08" or Chinese "04月08日"
            time_m = _re.search(r'(\d{4})-(\d{2})-(\d{2})', stem)
            if not time_m:
                time_m = _re.search(r'(\d{2})月(\d{2})日', stem)
            sort_key = ""
            time_str = ""
            if time_m:
                groups = time_m.groups()
                if len(groups) == 3 and len(groups[0]) == 4:
                    # ISO: 2026-04-08
                    sort_key = f"{groups[0]}-{groups[1]}-{groups[2]}T00:00"
                    time_str = f"{groups[1]}-{groups[2]}"
                else:
                    # Chinese: 04月08日
                    mm, dd = groups[0], groups[1]
                    sort_key = f"2026-{mm}-{dd}T00:00"
                    time_str = f"{mm}-{dd}"
            # Parse duration from content: "2026-04-08 11:07:02|26m 46s|CaptainWyon"
            duration = ""
            dur_m = _re.search(r'\d{4}-\d{2}-\d{2}\s[\d:]+\|(.+?)\|', raw[:500])
            if dur_m:
                duration = dur_m.group(1).strip()
            if not duration:
                fm_dur = _re.search(r'^duration:\s*(.+)$', raw[:800], _re.MULTILINE)
                if fm_dur:
                    duration = fm_dur.group(1).strip()
            # Parse duration → seconds (supports "1h 16m 31s", "25m 16s", "48m28s")
            dur_sec = 0
            if duration:
                h_m = _re.search(r'(\d+)\s*h', duration)
                m_m = _re.search(r'(\d+)\s*m(?!s)', duration)
                s_m = _re.search(r'(\d+)\s*s', duration)
                if h_m: dur_sec += int(h_m.group(1)) * 3600
                if m_m: dur_sec += int(m_m.group(1)) * 60
                if s_m: dur_sec += int(s_m.group(1))
            # Transcript character count (CJK + non-space chars, skip frontmatter)
            body = raw[(len("\n".join(_lines[:_start]))):] if _start else raw
            chars = len(_re.sub(r'\s+', '', body))
            # Auto-classify by filename prefix
            cat = "未分类"
            low = seg0.lower()
            if low.startswith("集团") or low.startswith("千丁ceo") or low.startswith("千丁hrd"):
                cat = "管理层"
            elif _re.match(r'^C\d', seg0) or _re.match(r'^N\d', seg0) or _re.match(r'^龙湖C\d', seg0) or _re.match(r'^龙湖N\d', seg0):
                cat = "航道"
            elif "终面" in seg0 or "面试" in seg0:
                cat = "面试"
            elif "千丁BU" in seg0 or "千丁战略" in seg0 or (seg0.startswith("千丁") and any(k in seg0 for k in ["物管", "财务", "签零", "员工", "数科", "建造", "建管", "空间", "资管", "城服", "IDC", "营销", "运营", "AI创新"])):
                cat = "BU"
            elif seg0.startswith("外部"):
                cat = "外部"
            elif "AI赋能" in stem or "ASR" in stem:
                cat = "内部"
            files.append({
                "name": stem,
                "title": fm_title or first_line or stem,
                "path": str(fp.relative_to(VAULT)),
                "size": size,
                "org": org,
                "person": person,
                "time": time_str,
                "duration": duration,
                "duration_sec": dur_sec,
                "chars": chars,
                "sort_key": sort_key,
                "cat": cat,
            })
        # Sort files by sort_key descending (newest first)
        files.sort(key=lambda f: f["sort_key"], reverse=True)
        if files:
            results.append({"date": d.name, "files": files, "count": len(files)})
    return results


# ── API: Hiring (面试候选人) ──────────────────────────
HIRING_DIR = VAULT / "Hiring"

@app.get("/api/hiring")
async def get_hiring():
    """List all hiring candidates."""
    import json as _json
    if not HIRING_DIR.exists():
        return []
    results = []
    for fp in sorted(HIRING_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = _json.loads(fp.read_text("utf-8"))
            results.append({
                "id": fp.stem,
                "name": data.get("name", fp.stem),
                "position": data.get("position", {}).get("title", ""),
                "status": data.get("status", "待评估"),
                "source": data.get("position", {}).get("source", ""),
                "date": data.get("date", ""),
                "match_score": data.get("resume", {}).get("match_score", 0),
                "tags": data.get("tags", []),
            })
        except Exception:
            pass
    return results

@app.get("/api/hiring/candidate")
async def get_hiring_candidate(id: str):
    """Read a single candidate JSON."""
    import json as _json
    fp = HIRING_DIR / f"{id}.json"
    if not fp.exists():
        raise HTTPException(404)
    return _json.loads(fp.read_text("utf-8"))


@app.get("/api/interviews/file")
async def get_interview_file(path: str):
    """Read a single interview file."""
    fp = VAULT / path
    if not fp.exists() or not str(fp).startswith(str(TICNOTE_DIR)):
        raise HTTPException(404)
    raw = fp.read_text("utf-8")
    return {"path": path, "raw": raw, "name": fp.stem}


# ── API: Reports ─────────────────────────────────────
REPORTS_DIR = VAULT / "Projects" / "LongFor" / "reports"

@app.get("/api/reports")
async def get_reports():
    """List all report files."""
    if not REPORTS_DIR.exists():
        return []
    results = []
    # Recursive so subfolders (00-personal, 01-diagnosis, ...) are discovered
    all_files = sorted(REPORTS_DIR.rglob("*.md"),
                       key=lambda p: (str(p.relative_to(REPORTS_DIR))),
                       reverse=False)
    for fp in all_files:
        rel = fp.relative_to(REPORTS_DIR)
        # top-level subfolder is the section (e.g. "01-diagnosis"); empty for legacy flat files
        parts = list(rel.parts)
        section_dir = parts[0] if len(parts) > 1 else ""
        text = fp.read_text("utf-8")
        title = ""
        subtitle = ""
        eyebrow = ""
        category = ""
        priority = ""
        section = ""
        entity = ""
        person = ""
        doc_date = ""
        version = ""
        tags = []
        # Parse YAML frontmatter if present
        if text.startswith("---\n") or text.startswith("---\r\n"):
            end = text.find("\n---", 4)
            if end != -1:
                fm_block = text[4:end]
                for ln in fm_block.splitlines():
                    if ":" not in ln:
                        continue
                    k, _, v = ln.partition(":")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "title" and not title:
                        title = v
                    elif k == "subtitle" and not subtitle:
                        subtitle = v
                    elif k == "eyebrow" and not eyebrow:
                        eyebrow = v
                    elif k == "category" and not category:
                        category = v
                    elif k == "priority" and not priority:
                        priority = v
                    elif k == "section" and not section:
                        section = v
                    elif k == "entity" and not entity:
                        entity = v
                    elif k == "person" and not person:
                        person = v
                    elif k == "date" and not doc_date:
                        doc_date = v
                    elif k == "version" and not version:
                        version = v
                    elif k == "tags" and not tags:
                        # Support either "tags: a, b, c" or "tags: [a, b, c]"
                        tv = v.strip().lstrip("[").rstrip("]")
                        tags = [t.strip().strip('"').strip("'") for t in tv.split(",") if t.strip()]
        if not title:
            # Fall back to first non-empty heading line
            for ln in text.splitlines():
                s = ln.strip()
                if not s or s == "---":
                    continue
                title = s.lstrip("# ").strip()
                break
        # Prefer explicit frontmatter section; else infer from subfolder name.
        final_section = section or section_dir
        # Always derive entity from the 2nd-level folder (folder taxonomy is source of truth),
        # not from frontmatter — ensures consistent grouping regardless of what agents wrote.
        folder_entity = parts[1] if len(parts) >= 3 else ""
        entity = folder_entity  # override any frontmatter entity
        # Derive sub-entity (third-level folder like 20-航道/处方 → "处方") for further grouping
        sub_entity = parts[2] if len(parts) >= 4 else ""
        # Infer date from filename tail like "...·2026-04-11.md" if not in frontmatter
        if not doc_date:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", fp.stem)
            if m:
                doc_date = m.group(1)
        # Infer "person" anchor for grouping inside an entity.
        # Priority: explicit frontmatter → filename prefix before "·" → empty
        if not person:
            stem = fp.stem
            # Patterns like "C1-—·xxx" or "—-CHO·xxx" or "—团队·xxx"
            # Take text before the first "·" and strip any trailing "-ROLE"
            anchor = stem.split("·")[0] if "·" in stem else stem
            # For航道 files: "C1-—" → keep "C1 —"
            m2 = re.match(r"^([CN]\d)[\-\s](.+)$", anchor)
            if m2:
                person = f"{m2.group(1)} {m2.group(2)}"
            else:
                # For BU/管理层: "—-CHO" → "—"; "—团队" → "—团队"
                person = anchor.split("-")[0].strip() if "-" in anchor else anchor.strip()
        results.append({
            "name": fp.stem,
            "title": title or fp.stem,
            "subtitle": subtitle,
            "eyebrow": eyebrow,
            "category": category,
            "priority": priority,
            "section": final_section,
            "entity": entity,
            "subEntity": sub_entity,
            "person": person,
            "date": doc_date,
            "version": version,
            "tags": tags,
            "path": str(fp.relative_to(VAULT)),
            "size": fp.stat().st_size,
            "mtime": fp.stat().st_mtime,
        })
    # Sort by mtime desc for stable listing
    results.sort(key=lambda r: r["mtime"], reverse=True)
    return results


@app.get("/api/reports/file")
async def get_report_file(path: str):
    """Read a single report file."""
    fp = VAULT / path
    if not fp.exists() or not str(fp).startswith(str(REPORTS_DIR)):
        raise HTTPException(404)
    raw = fp.read_text("utf-8")
    return {"path": path, "raw": raw, "name": fp.stem}


@app.get("/api/reports/image")
async def get_report_image(path: str):
    """Serve an image file from reports directory."""
    from fastapi.responses import FileResponse
    fp = REPORTS_DIR / path
    if not fp.exists() or not str(fp.resolve()).startswith(str(REPORTS_DIR)):
        raise HTTPException(404)
    suffix = fp.suffix.lower()
    media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
             "webp": "image/webp", "gif": "image/gif", "svg": "image/svg+xml"}
    return FileResponse(fp, media_type=media.get(suffix.lstrip("."), "application/octet-stream"),
                        headers={"Cache-Control": "public, max-age=86400"})


@app.put("/api/reports/file")
async def save_report_file(body: dict):
    """Save/update a report file."""
    path = body.get("path", "")
    content = body.get("content", "")
    if path:
        fp = VAULT / path
    else:
        name = body.get("name", f"report-{datetime.now().strftime('%Y%m%d-%H%M')}")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        fp = REPORTS_DIR / f"{name}.md"
    if not str(fp.resolve()).startswith(str(REPORTS_DIR)):
        raise HTTPException(403, "Invalid path")
    fp.write_text(content, "utf-8")
    return {"ok": True, "path": str(fp.relative_to(VAULT))}


# ── API: Task Repeats ────────────────────────────────
@app.get("/api/task-repeats")
async def get_task_repeats():
    return load_task_repeats()

@app.post("/api/task-repeats/delete")
async def delete_task_repeat(body:dict):
    text = body.get("text","")
    repeats = load_task_repeats()
    repeats = [r for r in repeats if r["text"] != text]
    save_task_repeats(repeats)
    return {"ok":True}


# ── API: Special Days (日子) ─────────────────────────
@app.get("/api/days")
async def get_special_days():
    days = load_special_days()
    result = []
    for d in days:
        nxt, countdown = compute_next_occurrence(d)
        result.append({**d, "next_occurrence": nxt, "countdown": countdown})
    result.sort(key=lambda x: x.get("countdown") if x.get("countdown") is not None else 9999)
    return result

@app.post("/api/days")
async def create_special_day(body:dict):
    days = load_special_days()
    entry = {
        "id": uuid.uuid4().hex[:8],
        "name": body.get("name",""),
        "date": body.get("date",""),
        "type": body.get("type","custom"),
        "repeat": body.get("repeat","yearly"),
        "icon": body.get("icon","📅"),
        "note": body.get("note",""),
        "created": today_s(),
    }
    days.append(entry)
    save_special_days(days)
    return {"ok":True, "id":entry["id"]}

@app.put("/api/days/{day_id}")
async def update_special_day(day_id:str, body:dict):
    days = load_special_days()
    for d in days:
        if d["id"] == day_id:
            for k in ["name","date","type","repeat","icon","note"]:
                if k in body: d[k] = body[k]
            break
    save_special_days(days)
    return {"ok":True}

@app.delete("/api/days/{day_id}")
async def delete_special_day(day_id:str):
    days = load_special_days()
    days = [d for d in days if d["id"] != day_id]
    save_special_days(days)
    return {"ok":True}


# ── API: Memory System ────────────────────────────────
MEMORY_DIR = VAULT / "Memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

def ensure_memory_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_INDEX.exists():
        MEMORY_INDEX.write_text("# Memory Index\n\n", "utf-8")

@app.get("/api/memory")
async def list_memories():
    ensure_memory_dir()
    memories = []
    for fp in sorted(MEMORY_DIR.glob("*.md")):
        if fp.name == "MEMORY.md":
            continue
        text = fp.read_text("utf-8")
        meta = parse_yaml_meta(text)
        # Extract content after frontmatter
        m = re.match(r'^---\s*\n.*?\n---\s*\n', text, re.DOTALL)
        content = text[m.end():].strip() if m else text.strip()
        memories.append({
            "filename": fp.name,
            "name": meta.get("name", fp.stem),
            "type": meta.get("type", "general"),
            "description": meta.get("description", ""),
            "content": content,
            "mtime": fp.stat().st_mtime,
        })
    # Read index
    index_content = MEMORY_INDEX.read_text("utf-8") if MEMORY_INDEX.exists() else ""
    return {"memories": memories, "index": index_content}

@app.get("/api/memory/{filename}")
async def get_memory(filename: str):
    ensure_memory_dir()
    fp = MEMORY_DIR / filename
    if not fp.exists():
        raise HTTPException(404, "Memory not found")
    if not str(fp.resolve()).startswith(str(MEMORY_DIR.resolve())):
        raise HTTPException(403, "Access denied")
    text = fp.read_text("utf-8")
    meta = parse_yaml_meta(text)
    m = re.match(r'^---\s*\n.*?\n---\s*\n', text, re.DOTALL)
    content = text[m.end():].strip() if m else text.strip()
    return {"filename": fp.name, "name": meta.get("name", fp.stem), "type": meta.get("type", "general"),
            "description": meta.get("description", ""), "content": content, "raw": text}

@app.post("/api/memory")
async def save_memory(body: dict):
    ensure_memory_dir()
    filename = body.get("filename", "")
    name = body.get("name", "")
    mem_type = body.get("type", "general")
    description = body.get("description", "")
    content = body.get("content", "")

    if not filename:
        # Generate filename from name
        slug = re.sub(r'[^\w\u4e00-\u9fff]+', '_', name.lower()).strip('_')[:40]
        filename = f"{slug}.md"

    if not filename.endswith(".md"):
        filename += ".md"

    fp = MEMORY_DIR / filename
    if not str(fp.resolve()).startswith(str(MEMORY_DIR.resolve())):
        raise HTTPException(403, "Access denied")

    # Write memory file with frontmatter
    lines = ["---", f"name: {name}", f"description: {description}", f"type: {mem_type}", "---", "", content]
    fp.write_text("\n".join(lines), "utf-8")

    # Update MEMORY.md index
    _update_memory_index()
    return {"ok": True, "filename": filename}

@app.delete("/api/memory/{filename}")
async def delete_memory(filename: str):
    ensure_memory_dir()
    fp = MEMORY_DIR / filename
    if not fp.exists():
        raise HTTPException(404)
    if not str(fp.resolve()).startswith(str(MEMORY_DIR.resolve())):
        raise HTTPException(403)
    if filename == "MEMORY.md":
        raise HTTPException(400, "Cannot delete index")
    fp.unlink()
    _update_memory_index()
    return {"ok": True}

def _update_memory_index():
    """Rebuild MEMORY.md index from all memory files."""
    ensure_memory_dir()
    lines = ["# Memory Index", "", "| 文件 | 类型 | 描述 |", "|------|------|------|"]
    for fp in sorted(MEMORY_DIR.glob("*.md")):
        if fp.name == "MEMORY.md":
            continue
        meta = parse_yaml_meta(fp.read_text("utf-8"))
        name = meta.get("name", fp.stem)
        mem_type = meta.get("type", "general")
        desc = meta.get("description", "")
        lines.append(f"| [{name}]({fp.name}) | {mem_type} | {desc} |")
    MEMORY_INDEX.write_text("\n".join(lines) + "\n", "utf-8")


# ── API: Full-text Search ─────────────────────────────
@app.get("/api/search")
async def search_vault(q: str = "", limit: int = 20):
    if not q or len(q.strip()) < 1:
        return {"results": [], "total": 0}
    query = q.strip().lower()
    keywords = query.split()
    results = []

    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if not f.endswith('.md'):
                continue
            fp = Path(root) / f
            try:
                text = fp.read_text("utf-8")
            except:
                continue
            text_lower = text.lower()
            # Score: count keyword matches
            score = sum(text_lower.count(kw) for kw in keywords)
            if score == 0:
                continue
            # Extract snippet around first match
            idx = text_lower.find(keywords[0])
            start = max(0, idx - 60)
            end = min(len(text), idx + 120)
            snippet = text[start:end].replace('\n', ' ').strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet += "..."

            rel_path = str(fp.relative_to(VAULT))
            results.append({
                "path": rel_path,
                "name": f,
                "folder": str(Path(root).relative_to(VAULT)),
                "score": score,
                "snippet": snippet,
                "mtime": fp.stat().st_mtime,
            })

    results.sort(key=lambda x: -x["score"])
    return {"results": results[:limit], "total": len(results)}


# ── API: Enhanced Daily (mood/energy/focus) ───────────
@app.get("/api/today/meta")
async def get_today_meta():
    """Get today's mood/energy/focus metadata."""
    ensure_today()
    fp = find_daily()
    data = parse_md(fp)
    meta = data.get("meta", {})
    return {
        "date": today_s(),
        "mood": meta.get("mood", ""),
        "energy": meta.get("energy", ""),
        "focus": meta.get("focus", ""),
        "tags": meta.get("tags", "[]"),
    }

@app.put("/api/today/meta")
async def update_today_meta(body: dict):
    """Update today's mood/energy/focus in frontmatter."""
    ensure_today()
    fp = find_daily()
    text = fp.read_text("utf-8")

    # Parse existing frontmatter
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if m:
        meta_text = m.group(1)
        content_after = text[m.end():]
        # Update/add fields
        meta_lines = meta_text.split('\n')
        fields_to_update = {k: body[k] for k in ["mood", "energy", "focus", "tags"] if k in body}
        for key, val in fields_to_update.items():
            found = False
            for i, line in enumerate(meta_lines):
                if line.startswith(f"{key}:"):
                    meta_lines[i] = f"{key}: {val}"
                    found = True
                    break
            if not found:
                meta_lines.append(f"{key}: {val}")
        new_text = "---\n" + "\n".join(meta_lines) + "\n---\n" + content_after
    else:
        # No frontmatter, add it
        fields = {k: body.get(k, "") for k in ["mood", "energy", "focus", "tags"]}
        fm = "---\n" + "\n".join(f"{k}: {v}" for k, v in fields.items()) + "\n---\n"
        new_text = fm + text

    fp.write_text(new_text, "utf-8")
    _auto_growth()
    return {"ok": True}


# ── API: Unified Tasks ───────────────────────────────
@app.get("/api/tasks/unified")
async def get_unified_tasks(tab: str = "today"):
    """Unified task view aggregating today/tomorrow/week/month data."""
    result = {"tab": tab, "tasks": [], "schedule": []}

    if tab == "today":
        ensure_today()
        fp = find_daily()
        data = parse_md(fp)
        tasks = [t for t in data.get("tasks",[]) if t["text"].strip()]
        for t in tasks:
            t["source"] = "daily"
            t["date"] = today_s()
            t["description"] = get_task_description(fp, t["text"])
        result["tasks"] = tasks
        result["schedule"] = parse_time_blocks(fp)
        result["diary_html"] = data.get("html","")

    elif tab == "tomorrow":
        tmr = (date.today() + timedelta(days=1)).isoformat()
        fp = find_daily(tmr)
        if fp.exists():
            data = parse_md(fp)
            tasks = [t for t in data.get("tasks",[]) if t["text"].strip()]
            for t in tasks:
                t["source"] = "daily"
                t["date"] = tmr
                t["description"] = get_task_description(fp, t["text"])
            result["tasks"] = tasks
            result["schedule"] = parse_time_blocks(fp)
        result["date"] = tmr

    elif tab == "week":
        # Aggregate weekly file + all daily files this week
        all_tasks = []
        all_schedule = []
        today_d = date.today()
        dow = today_d.weekday()  # Monday=0
        week_start = today_d - timedelta(days=dow)

        # Weekly file tasks
        ensure_weekly()
        wfp = find_weekly()
        wdata = parse_md(wfp)
        for t in wdata.get("tasks",[]):
            if t["text"].strip():
                t["source"] = "weekly"
                t["date"] = ""
                t["description"] = get_task_description(wfp, t["text"])
                all_tasks.append(t)

        # Daily files for each day of the week
        for i in range(7):
            d = week_start + timedelta(days=i)
            ds = d.isoformat()
            fp = find_daily(ds)
            if fp.exists():
                data = parse_md(fp)
                for t in data.get("tasks",[]):
                    if t["text"].strip():
                        t["source"] = "daily"
                        t["date"] = ds
                        t["description"] = get_task_description(fp, t["text"])
                        all_tasks.append(t)
                for b in parse_time_blocks(fp):
                    b["date"] = ds
                    all_schedule.append(b)

        result["tasks"] = all_tasks
        result["schedule"] = all_schedule
        result["week_number"] = week_n()

    elif tab == "month":
        all_tasks = []
        today_d = date.today()
        # Get all daily files for the month
        daily_dir = VAULT / "Journal" / "Daily"
        prefix = today_d.strftime("%Y-%m")
        if daily_dir.exists():
            for fp in sorted(daily_dir.glob(f"{prefix}-*.md")):
                ds = fp.stem  # YYYY-MM-DD
                data = parse_md(fp)
                for t in data.get("tasks",[]):
                    if t["text"].strip():
                        t["source"] = "daily"
                        t["date"] = ds
                        t["description"] = get_task_description(fp, t["text"])
                        all_tasks.append(t)
        result["tasks"] = all_tasks

    elif tab == "days":
        result["days"] = load_special_days()

    # Add repeats info
    repeats = load_task_repeats()
    repeat_map = {r["text"]: r["repeat"] for r in repeats}
    for t in result.get("tasks",[]):
        core = re.sub(r'^\[\d{2}:\d{2}(?:-\d{2}:\d{2})?\]\s*', '', t["text"]).strip()
        core_no_tag = re.sub(r'\s*#\S+$', '', core).strip()
        t["repeat"] = repeat_map.get(core, repeat_map.get(core_no_tag, ""))

    return result


# ── API: On This Day ─────────────────────────────────
@app.get("/api/on-this-day")
async def on_this_day():
    """Find journal entries from the same date in previous years/weeks."""
    today = date.today()
    entries = []

    # Same date last year
    daily_dir = VAULT / "Journal" / "Daily"
    if daily_dir.exists():
        for fp in daily_dir.glob("*.md"):
            try:
                d = date.fromisoformat(fp.stem)
                if d.month == today.month and d.day == today.day and d.year != today.year:
                    text = fp.read_text("utf-8")[:500]
                    entries.append({"date": fp.stem, "type": "same_date", "label": f"{d.year}年同一天", "snippet": text.split('\n')[0][:100]})
                elif d == today - timedelta(days=7):
                    text = fp.read_text("utf-8")[:500]
                    entries.append({"date": fp.stem, "type": "last_week", "label": "上周今日", "snippet": text.split('\n')[0][:100]})
            except:
                continue

    entries.sort(key=lambda x: x["date"], reverse=True)
    return {"entries": entries}


# ── API: AI Reflection ────────────────────────────────
@app.post("/api/reflect")
async def ai_reflect(body: dict):
    """AI-powered daily/weekly reflection with deep data gathering across journal, notes,
    decisions, contacts, tasks, and memory archives."""
    import requests as req
    reflect_type = body.get("type", "daily")  # "daily" or "weekly"
    settings = load_settings()
    mode = settings.get("ai_mode", "none")

    if mode == "none":
        return {"ok": False, "error": "请先配置AI"}

    # ── Helper: collect decisions by date range ──
    def _collect_decisions(dates: list[str]) -> str:
        dec_dir = VAULT / "Decisions"
        if not dec_dir.exists():
            return ""
        parts = []
        for fp in sorted(dec_dir.glob("*.md")):
            for d in dates:
                if fp.stem.startswith(d):
                    parts.append(f"### {fp.stem}\n{fp.read_text('utf-8')[:1500]}")
                    break
        return ("\n--- 决策记录 ---\n" + "\n\n".join(parts)) if parts else ""

    # ── Helper: collect contact info by date range ──
    def _collect_interactions(dates: list[str]) -> str:
        people_dir = VAULT / "Contacts" / "people"
        if not people_dir.exists():
            return ""
        parts = []
        date_set = set(dates)
        for fp in sorted(people_dir.glob("*.md")):
            try:
                text = fp.read_text("utf-8")
            except Exception:
                continue
            # Check if this contact was met/updated on target dates
            has_date_match = False
            for d in date_set:
                if d in text:
                    has_date_match = True
                    break
            if has_date_match:
                # Include the whole contact file (truncated) for richer context
                parts.append(f"### {fp.stem}\n{text[:1500]}")
        return ("\n--- 今日相关联系人 ---\n" + "\n\n".join(parts)) if parts else ""

    # ── Helper: task completion stats from daily files ──
    def _task_stats(dates: list[str]) -> str:
        total, done = 0, 0
        for d in dates:
            fp = VAULT / "Journal" / "Daily" / f"{d}.md"
            if not fp.exists():
                continue
            data = parse_md(fp)
            for t in data["tasks"]:
                if t["text"].strip():
                    total += 1
                    if t["done"]:
                        done += 1
        if total == 0:
            return ""
        rate = round(done / total * 100)
        return f"\n--- 任务统计 ---\n完成 {done}/{total} ({rate}%)\n"

    # ── Helper: collect memory files ──
    def _collect_memory(limit: int = 10, max_chars: int = 800) -> str:
        ensure_memory_dir()
        parts = []
        for fp in sorted(MEMORY_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if fp.name == "MEMORY.md":
                continue
            parts.append(f"### {fp.stem}\n{fp.read_text('utf-8')[:max_chars]}")
            if len(parts) >= limit:
                break
        return ("\n--- 记忆档案 ---\n" + "\n\n".join(parts)) if parts else ""

    # ── Helper: last week's reflection ──
    def _last_week_reflection() -> str:
        insights_dir = MEMORY_DIR / "insights"
        if not insights_dir.exists():
            return ""
        # Look back 7-14 days for a weekly reflection
        for offset in range(7, 15):
            d = (date.today() - timedelta(days=offset)).isoformat()
            fp = insights_dir / f"{d}_weekly.md"
            if fp.exists():
                return f"\n--- 上周反思 ---\n{fp.read_text('utf-8')[:2000]}\n"
        return ""

    # ── Gather context based on reflect_type ──
    context_parts = []
    today = today_s()

    def _clean_journal(text: str) -> str:
        """Strip empty template sections from journal to reduce noise."""
        lines = text.split('\n')
        cleaned = []
        skip_empty_section = False
        for i, line in enumerate(lines):
            # Detect empty template fields: "**做了什么：**" followed by blank
            if re.match(r'^\*\*.*：\*\*\s*$', line):
                # Check if next non-blank line is another template field or section header
                rest = [l for l in lines[i+1:i+3] if l.strip()]
                if not rest or (rest and (rest[0].startswith('**') or rest[0].startswith('##'))):
                    continue  # Skip empty template field
            # Skip empty blockquotes (template placeholders like "> ")
            if line.strip() == '>':
                continue
            cleaned.append(line)
        return '\n'.join(cleaned)

    if reflect_type == "daily":
        dates = [today]

        # Journal (cleaned of empty template noise)
        fp = find_daily()
        if fp.exists():
            raw = fp.read_text('utf-8')
            cleaned_journal = _clean_journal(raw)
            context_parts.append(f"--- 今日日志 ---\n{cleaned_journal}")

        # Notes
        notes_fp = VAULT / "Notes" / f"{today}.md"
        if notes_fp.exists():
            context_parts.append(f"--- 今日速记 ---\n{notes_fp.read_text('utf-8')}")

        # Decisions
        context_parts.append(_collect_decisions(dates))

        # Contact interactions (full file, up to 1500 chars per contact)
        context_parts.append(_collect_interactions(dates))

        # Task stats
        context_parts.append(_task_stats(dates))

        # TicNote interviews matching target dates (by filename date, not folder)
        if TICNOTE_DIR.exists():
            interview_parts = []
            # Convert dates to filename patterns: "2026-04-09" → "04月09日"
            date_patterns = set()
            for d in dates:
                parts = d.split("-")
                if len(parts) == 3:
                    date_patterns.add(f"{parts[1]}月{parts[2]}日")
            for td in TICNOTE_DIR.iterdir():
                if not td.is_dir() or td.name.startswith("_"):
                    continue
                for fp in sorted(td.glob("*.md")):
                    stem = fp.stem
                    # Check filename contains a matching date
                    if not any(dp in stem for dp in date_patterns):
                        continue
                    raw = fp.read_text("utf-8")
                    sections = raw.split("## 总结")
                    if len(sections) > 1:
                        summary_text = sections[1].split("## 转录")[0].strip()
                    else:
                        summary_text = raw[:3000]
                    interview_parts.append(f"### 访谈: {stem}\n{summary_text[:2000]}")
            if interview_parts:
                context_parts.append("\n--- 今日访谈记录（TicNote总结） ---\n" + "\n\n".join(interview_parts))

        # Memory (5 most recent, 500 chars each — just for background context)
        context_parts.append(_collect_memory(5, 500))

        prompt = """综合以上日志、速记、联系人、任务、访谈记录等全部数据，输出今日复盘（800-1200字）。
访谈记录是今天最重要的活动来源，务必重点分析。
注意：速记和日志可能记录了同一件事的不同角度，合并分析不要重复。

🎯 **今日进展**
最重要的2-3件事，每件一行。标注 ✅/🔄。引用具体数字或结论。

👥 **人物与沟通**
今天沟通的关键人物，格式：**姓名**（职位）— 沟通要点。新建联系用🆕标记。

💡 **发现与洞察**
从今天信息中提炼2-3条有价值的发现。必须包含具体数字、对比或趋势判断。

⚠️ **待解决**
需要跟进的事项，每条标注负责人或下一步动作。没有写「暂无」。

📌 **明日 Top 3**
每件一句话，说明为什么明天要做（而不是后天）。

严格基于数据，不编造。"""

    else:
        # Weekly — 7 days
        dates = [(date.today() - timedelta(days=i)).isoformat() for i in range(7)]

        # 7 days of journals
        for d in dates:
            fp = VAULT / "Journal" / "Daily" / f"{d}.md"
            if fp.exists():
                context_parts.append(f"--- {d} 日志 ---\n{fp.read_text('utf-8')}")

        # 7 days of notes
        for d in dates:
            notes_fp = VAULT / "Notes" / f"{d}.md"
            if notes_fp.exists():
                context_parts.append(f"--- {d} 速记 ---\n{notes_fp.read_text('utf-8')[:2000]}")

        # Weekly plan
        weekly_fp = find_weekly()
        if weekly_fp.exists():
            context_parts.append(f"--- 本周计划 ---\n{weekly_fp.read_text('utf-8')}")

        # Decisions
        context_parts.append(_collect_decisions(dates))

        # Contact interactions
        context_parts.append(_collect_interactions(dates))

        # Task stats
        context_parts.append(_task_stats(dates))

        # TicNote interviews for the week
        if TICNOTE_DIR.exists():
            interview_parts = []
            for d_name in dates:
                td = TICNOTE_DIR / d_name
                if not td.exists():
                    continue
                for fp in sorted(td.glob("*.md")):
                    raw = fp.read_text("utf-8")
                    sections = raw.split("## 总结")
                    if len(sections) > 1:
                        summary_text = sections[1].split("## 转录")[0].strip()
                    else:
                        summary_text = raw[:2000]
                    interview_parts.append(f"### 访谈: {fp.stem}\n{summary_text[:1500]}")
            if interview_parts:
                context_parts.append("\n--- 本周访谈记录（TicNote总结） ---\n" + "\n\n".join(interview_parts))

        # Memory
        context_parts.append(_collect_memory(10, 800))

        # Last week's reflection for continuity
        context_parts.append(_last_week_reflection())

        prompt = """综合以上7天的全部数据（特别是访谈记录），输出本周复盘（1000-1500字）。

📊 **本周主线**
一句话概括这周在做什么，然后列3-5项成果，每项带具体产出物或数字。

👥 **关系网络变化**
本周新认识/深度沟通的关键人物，格式：**姓名**（职位）— 关系进展。用🆕/🔄/⚡标记新建/加深/突破。

💡 **本周洞察**
2-3条最重要的发现或认知升级，必须有数据支撑或可验证的判断。

⚠️ **问题与风险**
当前面临的挑战，每条标注紧急度（🔴🟡🟢）和建议应对。

📌 **下周 Top 3**
每件说明为什么是本周完不成必须下周做的。

如有上周反思可对比，用↑↓标注趋势。严格基于数据，不编造。"""

    # Filter out empty parts and build full context
    full_context = "\n\n".join(p for p in context_parts if p)

    system_msg = f"""你是一位CTO级别的个人效能顾问。用户是科技公司高管，输出供他截图分享给同事或上级。
今天: {today_s()} Day {day_n()} W{week_n()} Q{quarter_n()}

风格：
- 专业、清晰、有信息密度。像McKinsey汇报，不像朋友圈
- 用自然的中文，禁用：赋能/维度/杠杆/拓扑/矩阵/降维/预编译/全面/深入/核心/关键性
- 数字要具体（"外部收入占比20-30%"而非"收入有待提升"）
- 人名+职位要准确引用，不要泛化

规则：
1. 严格基于提供的数据，不编造任何细节
2. 速记和日志可能有重复内容，去重后合并分析
3. 空白模板字段（未填写的）完全忽略
4. 每个章节3-5行，控制总长度
5. 建议必须具体可执行，带时间或对象"""

    # ── Call AI (in thread to avoid blocking event loop) ──
    import asyncio

    def _do_reflect_sync():
        if mode == "api":
            base_url = settings.get("api_base_url", "").rstrip("/")
            api_key = settings.get("api_key", "")
            model_name = settings.get("api_model", "")
            if not all([base_url, api_key, model_name]):
                return {"ok": False, "error": "请配置完整的API信息"}
            try:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                           "HTTP-Referer": "https://ome365.app", "X-Title": "Ome365"}
                payload = {"model": model_name, "max_tokens": 4000, "temperature": 0.3, "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": full_context + "\n\n" + prompt}
                ]}
                resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120, **_proxy_kwargs())
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                return {"ok": False, "error": str(e)}
        elif mode == "ollama":
            ollama_url = settings.get("ollama_url", "http://localhost:11434").rstrip("/")
            model_name = settings.get("ollama_model", "llama3.1")
            try:
                payload = {"model": model_name, "temperature": 0.3, "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": full_context + "\n\n" + prompt}
                ], "stream": False}
                resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=120, **_proxy_kwargs())
                resp.raise_for_status()
                text = resp.json().get("message", {}).get("content", "")
            except Exception as e:
                return {"ok": False, "error": str(e)}
        else:
            return {"ok": False, "error": f"未知模式: {mode}"}

        # Save insight
        insights_dir = MEMORY_DIR / "insights"
        insights_dir.mkdir(exist_ok=True)
        insight_fp = insights_dir / f"{today_s()}_{reflect_type}.md"
        type_label = "今日反思" if reflect_type == "daily" else "本周反思"
        insight_meta = f"---\ntitle: {type_label} · {today_s()}\ndate: {today_s()}\ntype: {reflect_type}\nauthor: Ome365 AI\n---\n\n# {type_label} · {today_s()}\n\n"
        insight_fp.write_text(insight_meta + text, "utf-8")
        return {"ok": True, "response": text, "saved_to": str(insight_fp.relative_to(VAULT))}

    return await asyncio.to_thread(_do_reflect_sync)


# ── API: Reflections List ──────────────────────────────
@app.get("/api/reflections")
async def list_reflections():
    """List all saved reflection files from Memory/insights/ for the reflections view."""
    insights_dir = MEMORY_DIR / "insights"
    if not insights_dir.exists():
        return {"ok": True, "items": []}
    items = []
    for fp in sorted(insights_dir.glob("*.md"), reverse=True):
        stem = fp.stem  # e.g. "2026-04-08_daily"
        parts = stem.rsplit("_", 1)
        date_str = parts[0] if len(parts) >= 1 else stem
        rtype = parts[1] if len(parts) >= 2 else "daily"
        content = fp.read_text("utf-8")
        # Strip frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                content = content[end+3:].strip()
        lines = content.strip().split("\n")
        title = lines[0].lstrip("# ").strip() if lines else "反思"
        items.append({
            "path": str(fp.relative_to(VAULT)),
            "date": date_str,
            "type": rtype,
            "title": title[:60],
            "content": content,  # frontend renders with marked.js
            "_open": False,
        })
    return {"ok": True, "items": items}


# ── API: Streaks ──────────────────────────────────────
@app.get("/api/streaks")
async def get_streaks():
    """Calculate streak data: consecutive days with completed tasks."""
    daily_dir = VAULT / "Journal" / "Daily"
    if not daily_dir.exists():
        return {"current_streak": 0, "best_streak": 0, "total_active_days": 0}

    active_dates = set()
    for fp in daily_dir.glob("*.md"):
        try:
            d = date.fromisoformat(fp.stem)
            data = parse_md(fp)
            done = sum(1 for t in data["tasks"] if t["done"])
            if done > 0:
                active_dates.add(d)
        except:
            continue

    if not active_dates:
        return {"current_streak": 0, "best_streak": 0, "total_active_days": 0}

    # Current streak (counting back from today)
    current = 0
    d = date.today()
    while d in active_dates:
        current += 1
        d -= timedelta(days=1)

    # Best streak
    sorted_dates = sorted(active_dates)
    best = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
            run += 1
            best = max(best, run)
        else:
            run = 1

    return {"current_streak": current, "best_streak": best, "total_active_days": len(active_dates)}


# ── API: Growth / Nurturing System ────────────────────
GROWTH_FILE = Path(__file__).parent / "growth.json"

GROWTH_PHASES = [
    {"id": "newborn", "name": "初生", "icon": "🌱", "min_interactions": 0, "min_days": 0, "desc": "刚刚苏醒，对一切好奇"},
    {"id": "forming", "name": "成长", "icon": "🌿", "min_interactions": 20, "min_days": 3, "desc": "开始记住你的偏好"},
    {"id": "distinct", "name": "独立", "icon": "🌳", "min_interactions": 80, "min_days": 14, "desc": "形成了自己的观点和风格"},
    {"id": "soulmate", "name": "知己", "icon": "🌟", "min_interactions": 200, "min_days": 30, "desc": "懂你的每一个细微表达"},
]

BOND_LEVELS = [
    {"level": 1, "name": "初识", "min_interactions": 0, "min_days": 0, "icon": "🤝"},
    {"level": 2, "name": "熟悉", "min_interactions": 10, "min_days": 2, "icon": "💬"},
    {"level": 3, "name": "信任", "min_interactions": 30, "min_days": 7, "icon": "🔗"},
    {"level": 4, "name": "默契", "min_interactions": 80, "min_days": 21, "icon": "💎"},
    {"level": 5, "name": "知己", "min_interactions": 150, "min_days": 45, "icon": "⭐"},
    {"level": 6, "name": "灵犀", "min_interactions": 300, "min_days": 90, "icon": "✨"},
    {"level": 7, "name": "共生", "min_interactions": 500, "min_days": 180, "icon": "🌌"},
]

ACHIEVEMENTS = [
    {"id": "first_note", "name": "第一笔", "icon": "✏️", "desc": "写下第一条速记", "check": "notes_count >= 1"},
    {"id": "first_task", "name": "开始行动", "icon": "✅", "desc": "完成第一个任务", "check": "tasks_done >= 1"},
    {"id": "streak_3", "name": "三日坚持", "icon": "🔥", "desc": "连续3天活跃", "check": "streak >= 3"},
    {"id": "streak_7", "name": "一周不断", "icon": "🔥🔥", "desc": "连续7天活跃", "check": "streak >= 7"},
    {"id": "streak_30", "name": "月度战士", "icon": "🏆", "desc": "连续30天活跃", "check": "streak >= 30"},
    {"id": "memory_5", "name": "有记性", "icon": "🧠", "desc": "积累5条记忆", "check": "memory_count >= 5"},
    {"id": "reflect_first", "name": "知行合一", "icon": "💡", "desc": "完成第一次AI反思", "check": "reflect_count >= 1"},
    {"id": "contacts_10", "name": "社交达人", "icon": "👥", "desc": "建立10个联系人", "check": "contacts >= 10"},
    {"id": "plan_25", "name": "计划执行者", "icon": "🗺️", "desc": "完成25%年度计划", "check": "plan_pct >= 25"},
    {"id": "plan_50", "name": "半程英雄", "icon": "🏅", "desc": "完成50%年度计划", "check": "plan_pct >= 50"},
    {"id": "active_30", "name": "持之以恒", "icon": "📅", "desc": "累计30天活跃", "check": "active_days >= 30"},
    {"id": "active_100", "name": "百日精进", "icon": "💯", "desc": "累计100天活跃", "check": "active_days >= 100"},
]

def load_growth() -> dict:
    default = {
        "total_interactions": 0,
        "first_use_date": today_s(),
        "achievements_unlocked": [],
        "ome_name": "Ome",
        "ome_personality": "好奇、温暖、直接",
        "evolution_log": [],  # [{date, shift, phase}]
        "traits": [],  # accumulated personality traits
    }
    return {**default, **_safe_json_load(GROWTH_FILE, {})}

def save_growth(data: dict):
    GROWTH_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

def _auto_growth(count=1):
    """Background growth interaction increment.

    Writes both the legacy local growth.json counter AND Ome's internal bond
    counter (which drives /api/growth phase + bond progression). Without the
    Ome side, interactions count stays at 5 regardless of user activity because
    only ome.chat() bumps the Ome bond internally.
    """
    try:
        growth = load_growth()
        growth["total_interactions"] = growth.get("total_interactions", 0) + count
        if growth["total_interactions"] % 20 == 0:
            growth["evolution_pending"] = True
        save_growth(growth)
    except:
        pass
    # Bump Ome's internal bond counter so /api/growth progresses too.
    try:
        ome = get_ome()
        if ome and hasattr(ome, "bond"):
            today_str = today_s()
            with _ome_lock:
                for _ in range(max(1, int(count))):
                    ome.bond.record_interaction(today_str)
                # Persist bond state (SQLite soul_state) so count survives restart.
                if hasattr(ome, "_save_life_state"):
                    try: ome._save_life_state()
                    except Exception: pass
    except Exception:
        pass

def _compute_vault_stats() -> dict:
    """Compute vault statistics for Ome external stats injection."""
    notes_dir = VAULT / "Notes"
    notes_count = sum(1 for _ in notes_dir.glob("*.md")) if notes_dir.exists() else 0
    daily_dir = VAULT / "Journal" / "Daily"
    tasks_done = 0
    tasks_total = 0
    active_dates = set()
    if daily_dir.exists():
        for fp in daily_dir.glob("*.md"):
            try:
                d = date.fromisoformat(fp.stem)
                data = parse_md(fp)
                done = sum(1 for t in data["tasks"] if t["done"])
                total = len(data["tasks"])
                tasks_done += done
                tasks_total += total
                if done > 0:
                    active_dates.add(d)
            except:
                continue
    contacts_dir = VAULT / "Contacts" / "people"
    contacts_count = len(list(contacts_dir.glob("*.md"))) if contacts_dir.exists() else 0
    plan = parse_plan()
    plan_pct = plan["overview"]["pct"]
    active_days = len(active_dates)
    # Streak
    streak = 0
    d = date.today()
    while d in active_dates:
        streak += 1
        d -= timedelta(days=1)
    memory_count = len(list((VAULT / "Memory").glob("*.md"))) - 1 if (VAULT / "Memory").exists() else 0
    insights_dir = VAULT / "Memory" / "insights"
    reflect_count = len(list(insights_dir.glob("*.md"))) if insights_dir.exists() else 0
    return {
        "notes_count": notes_count,
        "tasks_done": tasks_done,
        "tasks_total": tasks_total,
        "contacts_count": contacts_count,
        "plan_pct": plan_pct,
        "active_days": active_days,
        "streak": streak,
        "memory_count": max(0, memory_count),
        "reflect_count": reflect_count,
    }

def _compute_growth_state() -> dict:
    """Compute the full growth state from all data sources."""
    growth = load_growth()
    interactions = growth.get("total_interactions", 0)
    first_date = growth.get("first_use_date", today_s())
    try:
        days_since = (date.today() - date.fromisoformat(first_date)).days
    except:
        days_since = 0

    # Determine phase
    phase = GROWTH_PHASES[0]
    for p in reversed(GROWTH_PHASES):
        if interactions >= p["min_interactions"] and days_since >= p["min_days"]:
            phase = p; break

    # Determine bond level
    bond = BOND_LEVELS[0]
    for b in reversed(BOND_LEVELS):
        if interactions >= b["min_interactions"] and days_since >= b["min_days"]:
            bond = b; break

    # Next bond level
    next_bond = None
    for b in BOND_LEVELS:
        if b["level"] > bond["level"]:
            next_bond = b; break

    # Bond progress (percentage to next level)
    bond_progress = 100
    if next_bond:
        inter_range = max(1, next_bond["min_interactions"] - bond["min_interactions"])
        days_range = max(1, next_bond["min_days"] - bond["min_days"])
        inter_pct = min(100, (interactions - bond["min_interactions"]) / inter_range * 100)
        days_pct = min(100, (days_since - bond["min_days"]) / days_range * 100)
        bond_progress = int(min(inter_pct, days_pct))  # Both must be met

    # Gather stats for achievements
    notes_dir = VAULT / "Notes"
    notes_count = sum(1 for _ in notes_dir.glob("*.md")) if notes_dir.exists() else 0
    daily_dir = VAULT / "Journal" / "Daily"
    tasks_done = 0
    active_dates = set()
    if daily_dir.exists():
        for fp in daily_dir.glob("*.md"):
            try:
                d = date.fromisoformat(fp.stem)
                data = parse_md(fp)
                done = sum(1 for t in data["tasks"] if t["done"])
                tasks_done += done
                if done > 0:
                    active_dates.add(d)
            except:
                continue

    # Streak
    streak = 0
    d = date.today()
    while d in active_dates:
        streak += 1
        d -= timedelta(days=1)

    memory_count = len(list((VAULT / "Memory").glob("*.md"))) - 1 if (VAULT / "Memory").exists() else 0
    insights_dir = VAULT / "Memory" / "insights"
    reflect_count = len(list(insights_dir.glob("*.md"))) if insights_dir.exists() else 0
    contacts_dir = VAULT / "Contacts" / "people"
    contacts = len(list(contacts_dir.glob("*.md"))) if contacts_dir.exists() else 0
    plan = parse_plan()
    plan_pct = plan["overview"]["pct"]
    active_days = len(active_dates)

    # Check achievements
    unlocked = set(growth.get("achievements_unlocked", []))
    stats = {"notes_count": notes_count, "tasks_done": tasks_done, "streak": streak,
             "memory_count": max(0, memory_count), "reflect_count": reflect_count,
             "contacts": contacts, "plan_pct": plan_pct, "active_days": active_days}
    newly_unlocked = []
    for ach in ACHIEVEMENTS:
        if ach["id"] not in unlocked:
            try:
                if eval(ach["check"], {"__builtins__": {}}, stats):
                    unlocked.add(ach["id"])
                    newly_unlocked.append(ach)
            except:
                pass

    # Save updated state
    if newly_unlocked or growth.get("achievements_unlocked", []) != list(unlocked):
        growth["achievements_unlocked"] = list(unlocked)
        save_growth(growth)

    achievements_list = []
    for ach in ACHIEVEMENTS:
        achievements_list.append({**ach, "unlocked": ach["id"] in unlocked})

    return {
        "phase": phase,
        "bond": {**bond, "progress": bond_progress},
        "next_bond": next_bond,
        "total_interactions": interactions,
        "days_since_first": days_since,
        "ome_name": growth.get("ome_name", "Ome"),
        "ome_personality": growth.get("ome_personality", "好奇、温暖、直接"),
        "traits": growth.get("traits", []),
        "evolution_log": growth.get("evolution_log", [])[-10:],  # Last 10 entries
        "achievements": achievements_list,
        "newly_unlocked": newly_unlocked,
        "stats": stats,
    }

@app.get("/api/growth")
async def get_growth():
    ome = get_ome()
    if ome:
        try:
            # Inject vault stats into Ome before dashboard
            vault_stats = _compute_vault_stats()
            with _ome_lock:
                try:
                    ome.report_external_stats(vault_stats)
                except:
                    pass
                dash = ome.life_dashboard()

            ome_bond = dash.get("bond", {})
            total_interactions = ome_bond.get("total_interactions", 0)
            # Always prefer identity.created_at — life_dashboard()'s bond dict
            # may surface min_days (of next level) under "days", which caused
            # the sidebar to report "3天" when the real age was 10.
            days_since = 0
            try:
                created = ome.soul.identity.get("created_at", "") if hasattr(ome, "soul") else ""
                if created:
                    from datetime import datetime as _dt
                    days_since = max(0, (date.today() - _dt.strptime(created[:10], "%Y-%m-%d").date()).days)
            except Exception:
                pass
            if not days_since:
                # Last-resort fallbacks.
                days_since = ome_bond.get("days_since_creation") or 0
                if not days_since:
                    try:
                        days_since = getattr(ome.bond, "days_since_creation", 0)
                    except Exception:
                        days_since = 0
            days_since = int(days_since or 0)

            # Map Ome phase to legacy phase (match by interaction/days thresholds)
            phase = GROWTH_PHASES[0]
            for p in reversed(GROWTH_PHASES):
                if total_interactions >= p["min_interactions"] and days_since >= p["min_days"]:
                    phase = p; break

            # Map Ome bond to legacy bond (add icon, progress)
            bond_level = ome_bond.get("level", 0)
            legacy_bond = None
            for b in BOND_LEVELS:
                if b["level"] <= max(1, bond_level):
                    legacy_bond = b
            if not legacy_bond:
                legacy_bond = BOND_LEVELS[0]

            # Next bond level
            next_bond = None
            for b in BOND_LEVELS:
                if b["level"] > legacy_bond["level"]:
                    next_bond = b; break

            # Bond progress
            bond_progress = 100
            if next_bond:
                inter_needed = ome_bond.get("interactions_needed", next_bond["min_interactions"] - legacy_bond["min_interactions"])
                inter_done = total_interactions - legacy_bond["min_interactions"]
                bond_progress = min(99, max(0, int(inter_done / max(1, inter_needed) * 100)))

            # Flatten achievements: Ome returns {unlocked:[], locked:[]}
            ome_ach = dash.get("achievements", {})
            achievements_list = []
            for a in ome_ach.get("unlocked", []):
                achievements_list.append({**a, "unlocked": True, "desc": a.get("description", "")})
            for a in ome_ach.get("locked", []):
                achievements_list.append({**a, "unlocked": False, "desc": a.get("description", "")})
            # If Ome returned no achievements, fall back to legacy
            if not achievements_list:
                unlocked = set()
                for ach in ACHIEVEMENTS:
                    try:
                        if eval(ach["check"], {"__builtins__": {}}, vault_stats):
                            unlocked.add(ach["id"])
                    except:
                        pass
                for ach in ACHIEVEMENTS:
                    achievements_list.append({**ach, "unlocked": ach["id"] in unlocked})

            growth = load_growth()

            # New Ome 0.5.0 fields
            daily_challenge = dash.get("daily_challenge")
            memory_stats = dash.get("memory_stats")
            ome_phase = dash.get("phase", {})
            next_milestone = dash.get("next_milestone")

            return {
                "ome_name": ome.name,
                "ome_personality": ", ".join(ome.traits),
                "phase": {
                    **phase,
                    "phase_id": ome_phase.get("phase_id", phase.get("id", 0)),
                    "persona": ome_phase.get("persona", ""),
                    "strategy_hint": ome_phase.get("strategy_hint", ""),
                },
                "bond": {**legacy_bond, "progress": bond_progress, "name": ome_bond.get("name", legacy_bond["name"])},
                "next_bond": next_bond,
                "emotion": dash.get("emotion", {}),
                "achievements": achievements_list,
                "skills": dash.get("skills", []),
                "streak": dash.get("streak", {}),
                "highlights": dash.get("highlights", []),
                "evolution_pending": ome.evolution_pending,
                "commits_since_reflection": ome.commits_since_reflection,
                "total_interactions": total_interactions,
                "days_since_first": days_since,
                "traits": ome.traits,
                "stats": vault_stats,
                "evolution_log": growth.get("evolution_log", [])[-10:],
                # Ome 0.5.0 new fields
                "daily_challenge": daily_challenge,
                "memory_stats": memory_stats,
                "next_milestone": next_milestone,
                # Ome 0.7.0 new fields
                "capabilities": dash.get("capabilities", {}),
                "maturity": dash.get("maturity", {}),
            }
        except Exception as e:
            import traceback; traceback.print_exc()
            pass  # Fall through to legacy
    return _compute_growth_state()

@app.post("/api/growth/interact")
async def record_interaction(body: dict = {}):
    """Record an interaction (called after AI use, note creation, etc.)"""
    ome = get_ome()
    if ome:
        return {
            "ok": True,
            "total": ome.life_dashboard().get("bond", {}).get("total_interactions", 0),
            "evolution_pending": ome.evolution_pending,
        }
    # Legacy fallback
    growth = load_growth()
    growth["total_interactions"] = growth.get("total_interactions", 0) + body.get("count", 1)
    total = growth["total_interactions"]
    evolution_pending = (total % 20 == 0) and total > 0
    if evolution_pending:
        growth["evolution_pending"] = True
    save_growth(growth)
    return {"ok": True, "total": total, "evolution_pending": evolution_pending}

@app.put("/api/growth/profile")
async def update_growth_profile(body: dict):
    """Update Ome's name and personality."""
    growth = load_growth()
    if "ome_name" in body:
        growth["ome_name"] = body["ome_name"]
    if "ome_personality" in body:
        growth["ome_personality"] = body["ome_personality"]
    save_growth(growth)
    return {"ok": True}

@app.post("/api/growth/evolve")
async def evolve_personality():
    """AI analyzes recent interactions and generates a personality evolution insight."""
    ome = get_ome()
    if ome:
        try:
            with _ome_lock:
                result = ome.evolve()
            return {
                "ok": True,
                "evolution": {"date": today_s(), "shift": result.get("summary", ""), "reason": "Ome自省"},
                "new_trait": ", ".join(result.get("new_traits_observed", [])),
                "drift_detected": result.get("drift_detected"),
                "method": result.get("method", ""),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}

    # Legacy fallback
    import requests as req
    settings = load_settings()
    if settings.get("ai_mode", "none") == "none":
        return {"ok": False, "error": "请先配置AI"}
    growth = load_growth()
    context_parts = []
    fp = find_daily()
    if fp.exists(): context_parts.append(fp.read_text("utf-8")[:2000])
    current_traits = ", ".join(growth.get("traits", [])) or growth.get("ome_personality", "好奇、温暖、直接")
    prompt = f"""分析用户数据，为AI助手"{growth.get('ome_name','Ome')}"生成个性进化记录。当前特征：{current_traits}，互动{growth.get('total_interactions',0)}次。
用户数据：{chr(10).join(context_parts)[:2000]}
输出JSON：{{"shift":"变化描述","new_trait":"新特征","reason":"原因"}}"""
    try:
        base_url = settings.get("api_base_url","").rstrip("/")
        api_key = settings.get("api_key","")
        model = settings.get("api_model","")
        headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}
        payload = {"model":model,"max_tokens":200,"messages":[
            {"role":"system","content":"只输出JSON。"},{"role":"user","content":prompt}]}
        resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=30, **_proxy_kwargs())
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        json_match = re.search(r'\{[^}]+\}', text)
        if json_match:
            evo = json.loads(json_match.group())
            entry = {"date": today_s(), "shift": evo.get("shift",""), "reason": evo.get("reason","")}
            growth.setdefault("evolution_log", []).append(entry)
            if evo.get("new_trait"):
                traits = growth.get("traits", [])
                if evo["new_trait"] not in traits: traits.append(evo["new_trait"])
                growth["traits"] = traits[-10:]
            save_growth(growth)
            return {"ok": True, "evolution": entry, "new_trait": evo.get("new_trait","")}
        return {"ok": False, "error": "AI返回格式异常"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


# ── Ome 0.5.0 New Endpoints ──────────────────────────

@app.get("/api/growth/timeline")
async def get_growth_timeline(limit: int = 20):
    """成长事件流 — growth_timeline()"""
    ome = get_ome()
    if not ome:
        return {"timeline": []}
    try:
        with _ome_lock:
            timeline = ome.growth_timeline(limit)
        return {"timeline": timeline}
    except Exception as e:
        return {"timeline": [], "error": str(e)[:100]}

@app.get("/api/growth/emotion-history")
async def get_emotion_history(days: int = 30):
    """情绪变化轨迹 — emotion_history()"""
    ome = get_ome()
    if not ome:
        return {"history": []}
    try:
        with _ome_lock:
            history = ome.emotion_history(days)
        return {"history": history}
    except Exception as e:
        return {"history": [], "error": str(e)[:100]}

@app.get("/api/memory-stats")
async def get_memory_stats():
    """记忆健康仪表盘 — memory_stats()"""
    ome = get_ome()
    if not ome:
        return {"stats": {}}
    try:
        with _ome_lock:
            stats = ome.memory_stats()
        return {"stats": stats}
    except Exception as e:
        return {"stats": {}, "error": str(e)[:100]}


# ── Reminders & Proactive ─────────────────────────────
REMINDERS_FILE = Path(__file__).parent / "reminders.json"

def load_reminders() -> list:
    return _safe_json_load(REMINDERS_FILE, [])

def save_reminders(reminders: list):
    REMINDERS_FILE.write_text(json.dumps(reminders, ensure_ascii=False, indent=2), "utf-8")

@app.get("/api/reminders")
async def get_reminders():
    """Get all reminders. Client filters by time."""
    reminders = load_reminders()
    # Also auto-generate reminders from tasks with time prefix and special days
    auto = []
    # Tasks with [HH:MM] prefix
    ensure_today()
    fp = find_daily()
    data = parse_md(fp)
    for t in data["tasks"]:
        tm = re.match(r'^\[(\d{2}:\d{2})\]\s*(.+)', t["text"])
        if tm and not t["done"]:
            auto.append({"id": f"task_{tm.group(1)}_{tm.group(2)[:20]}", "type": "task", "time": tm.group(1),
                         "title": tm.group(2).strip(), "auto": True})
    # Special days (today only)
    days_file = Path(__file__).parent / "special_days.json"
    if days_file.exists():
        sdays = _safe_json_load(days_file, [])
        td = date.today()
        for sd in sdays:
            is_today = False
            if sd.get("repeat") == "yearly":
                is_today = sd["date"] == f"{td.month:02d}-{td.day:02d}"
            elif sd.get("repeat") == "monthly":
                try: is_today = int(sd["date"]) == td.day
                except: pass
            else:
                is_today = sd["date"] == today_s()
            if is_today:
                auto.append({"id": f"day_{sd.get('id','')}", "type": "day", "time": "09:00",
                             "title": f"{sd.get('icon','📅')} {sd['name']}", "auto": True})
    # Time blocks
    blocks = parse_time_blocks(fp)
    for b in blocks:
        if b["item"]:
            # Extract start time from block (e.g. "09-12" -> "09:00")
            start = b["time"].split("-")[0].strip()
            if len(start) <= 2: start += ":00"
            auto.append({"id": f"block_{b['time']}_{b['item'][:10]}", "type": "block", "time": start,
                         "title": f"时间块: {b['item']}", "auto": True})
    return {"ok": True, "reminders": reminders, "auto_reminders": auto}

@app.post("/api/reminders")
async def create_reminder(body: dict):
    reminders = load_reminders()
    r = {"id": str(uuid.uuid4())[:8], "time": body.get("time",""), "title": body.get("title",""),
         "type": body.get("type","custom"), "repeat": body.get("repeat","none"),
         "created": today_s()}
    reminders.append(r)
    save_reminders(reminders)
    return {"ok": True, "reminder": r}

@app.delete("/api/reminders/{rid}")
async def delete_reminder(rid: str):
    reminders = load_reminders()
    reminders = [r for r in reminders if r.get("id") != rid]
    save_reminders(reminders)
    return {"ok": True}

@app.get("/api/memories")
async def get_ome_memories(q: str = "", limit: int = 20, types: str = ""):
    """Recall memories from Ome brain, with optional type_filter."""
    ome = get_ome()
    if ome:
        try:
            type_filter = [t.strip() for t in types.split(",") if t.strip()] or None
            with _ome_lock:
                results = ome.recall(q or "最近的事", top_k=limit, type_filter=type_filter)
            return {"memories": results}
        except Exception as e:
            return {"memories": [], "error": str(e)[:100]}
    return {"memories": []}

@app.post("/api/memories")
async def add_ome_memory(body: dict):
    """Store a memory into Ome brain."""
    ome = get_ome()
    if ome:
        try:
            with _ome_lock:
                result = ome.remember(body.get("content", ""), source=body.get("source", "manual"))
            _auto_growth()
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}
    return {"ok": False, "error": "Ome not available"}

@app.delete("/api/memories/{memory_id}")
async def delete_ome_memory(memory_id: str):
    """Delete a specific Ome memory by ID."""
    ome = get_ome()
    if ome:
        try:
            with _ome_lock:
                store = ome.soul.store
                mem = store.get(memory_id)
                if not mem:
                    return {"ok": False, "error": "记忆不存在"}
                store._conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
                store._embeddings_cache.pop(memory_id, None)
                store._conn.commit()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}
    return {"ok": False, "error": "Ome not available"}

@app.put("/api/memories/{memory_id}")
async def update_ome_memory(memory_id: str, body: dict):
    """Update content of a specific Ome memory by ID."""
    ome = get_ome()
    new_content = body.get("content", "").strip()
    if not new_content:
        return {"ok": False, "error": "内容不能为空"}
    if ome:
        try:
            with _ome_lock:
                store = ome.soul.store
                mem = store.get(memory_id)
                if not mem:
                    return {"ok": False, "error": "记忆不存在"}
                store._conn.execute("UPDATE memories SET content=? WHERE id=?", (new_content, memory_id))
                store._embeddings_cache.pop(memory_id, None)
                store._conn.commit()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}
    return {"ok": False, "error": "Ome not available"}

@app.get("/api/proactive")
async def get_proactive():
    """Generate a proactive AI message based on current context."""
    settings = load_settings()
    if not settings.get("proactive_enabled", True):
        return {"ok": False, "reason": "disabled"}

    ome = get_ome()
    if ome:
        try:
            with _ome_lock:
                greeting = ome.generate_greeting()
            if greeting and "连不上" not in greeting:
                return {"ok": True, "message": greeting, "trigger": "ome_greeting"}
        except:
            pass

    # Legacy fallback
    import requests as req
    if settings.get("ai_mode", "none") == "none":
        return {"ok": False, "reason": "no_ai"}
    hour = datetime.now().hour
    fp = find_daily()
    data = parse_md(fp)
    tasks = [t for t in data["tasks"] if t["text"].strip()]
    done, total = sum(1 for t in tasks if t["done"]), len(tasks)
    if hour < 9: prompt = f"早上{hour}点，{total}个任务。晨间打气15字。只输出这句话。"
    elif hour < 12 and done == 0 and total > 0: prompt = f"上午{hour}点，{total}个任务没开始。温和推动15字。只输出。"
    elif 12 <= hour < 14: prompt = f"午间，{done}/{total}完成。鼓励15字。只输出。"
    elif hour >= 17 and done < total: prompt = f"下午{hour}点，还有{total-done}个。冲刺15字。只输出。"
    elif hour >= 21: prompt = f"晚{hour}点，{done}/{total}完成。晚安15字。只输出。"
    else: return {"ok": False, "reason": "no_trigger"}
    try:
        base_url = settings.get("api_base_url","").rstrip("/")
        api_key = settings.get("api_key","")
        model = settings.get("api_model","")
        if not all([base_url, api_key, model]): return {"ok": False, "reason": "no_config"}
        headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}
        payload = {"model":model,"max_tokens":50,"messages":[{"role":"user","content":prompt}]}
        resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15, **_proxy_kwargs())
        resp.raise_for_status()
        return {"ok": True, "message": resp.json()["choices"][0]["message"]["content"].strip().strip('"')}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:100]}


# ── API: Insights (洞察 · flagship AI synthesis) ──────
# 基于访谈/反思/速记/记忆/汇报/联系人的综合洞察，是 Ome365 面向
# 职业/企业应用的最大亮点：AI 从你的日常碎片里提炼出主题、项目点子、
# 业务诊断和待思考的问题。
INSIGHTS_DIR = VAULT / "Insights"

def _insights_corpus(days: int = 90) -> dict:
    """收集最近 N 天的原始语料，用于喂给大模型做综合分析。"""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    notes, reflections, interviews, reports, memories, contacts_summary = [], [], [], [], [], []

    # Notes
    nd = VAULT / "Notes"
    if nd.exists():
        for fp in sorted(nd.glob("*.md"), reverse=True)[:60]:
            if fp.stem < cutoff: continue
            for line in fp.read_text("utf-8").split('\n'):
                m = re.match(r'^- \[\d{2}:\d{2}\]\s*(?:#(\S+)\s+)?(.*)', line)
                if m and m.group(2).strip():
                    notes.append(f"[{fp.stem} #{m.group(1) or ''}] {m.group(2).strip()}")

    # Reflections
    rd = VAULT / "Reflections"
    if rd.exists():
        for fp in sorted(rd.glob("*.md"), reverse=True)[:30]:
            if fp.stem < cutoff: continue
            txt = fp.read_text("utf-8")[:2000]
            reflections.append(f"[{fp.stem}]\n{txt}")

    # Interviews (只取标题和最前面的摘要)
    ind = VAULT / "Interviews"
    if ind.exists():
        for fp in sorted(ind.glob("*.md"), reverse=True)[:20]:
            if fp.stem[:10] < cutoff: continue
            txt = fp.read_text("utf-8")[:1500]
            interviews.append(f"[{fp.stem}]\n{txt}")

    # Reports
    repd = VAULT / "Reports"
    if repd.exists():
        for fp in sorted(repd.glob("*.md"), reverse=True)[:15]:
            if fp.stem[:10] < cutoff: continue
            txt = fp.read_text("utf-8")[:1500]
            reports.append(f"[{fp.stem}]\n{txt}")

    # Memories (from Memory/ folder)
    md = VAULT / "Memory"
    if md.exists():
        for fp in sorted(md.rglob("*.md"), reverse=True)[:30]:
            try:
                if fp.stat().st_mtime < datetime.fromisoformat(cutoff).timestamp():
                    continue
            except Exception:
                pass
            txt = fp.read_text("utf-8")[:800]
            memories.append(f"[{fp.stem}]\n{txt}")

    # Contacts (most recently interacted)
    pd = VAULT / "Contacts" / "people"
    if pd.exists():
        for fp in sorted(pd.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
            try:
                data = parse_md(fp)
                meta = data.get("meta", {})
                name = meta.get("name", fp.stem)
                company = meta.get("company", "")
                contacts_summary.append(f"{name}（{company}）")
            except Exception:
                pass

    return {
        "notes": notes[:200],
        "reflections": reflections[:15],
        "interviews": interviews[:10],
        "reports": reports[:8],
        "memories": memories[:15],
        "contacts": contacts_summary[:20],
        "stats": {
            "notes_count": len(notes),
            "reflections_count": len(reflections),
            "interviews_count": len(interviews),
            "reports_count": len(reports),
            "memories_count": len(memories),
            "contacts_count": len(contacts_summary),
            "days": days,
        }
    }


def _insights_context_text(corpus: dict, max_chars: int = 16000) -> str:
    """把 corpus 拼成一段文本喂给 LLM。"""
    parts = []
    s = corpus["stats"]
    parts.append(f"=== 过去 {s['days']} 天语料 ===")
    parts.append(f"速记 {s['notes_count']} 条 / 反思 {s['reflections_count']} 篇 / 访谈 {s['interviews_count']} 场 / 汇报 {s['reports_count']} 份 / 记忆 {s['memories_count']} 条 / 近联系人 {s['contacts_count']}")

    if corpus["notes"]:
        parts.append("\n--- 速记（带标签）---")
        parts.append("\n".join(corpus["notes"][:80]))
    if corpus["reflections"]:
        parts.append("\n--- 反思节选 ---")
        parts.append("\n\n".join(corpus["reflections"][:8]))
    if corpus["interviews"]:
        parts.append("\n--- 访谈节选 ---")
        parts.append("\n\n".join(corpus["interviews"][:5]))
    if corpus["reports"]:
        parts.append("\n--- 汇报节选 ---")
        parts.append("\n\n".join(corpus["reports"][:4]))
    if corpus["memories"]:
        parts.append("\n--- 长期记忆 ---")
        parts.append("\n".join(corpus["memories"][:10]))
    if corpus["contacts"]:
        parts.append("\n--- 近期联系人 ---")
        parts.append("、".join(corpus["contacts"]))

    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(已截断)"
    return text


def _ai_call_json(system: str, user: str, max_tokens: int = 3200) -> dict:
    """调用底层 API 返回 JSON；处理 code fence。"""
    import requests as req
    settings = load_settings()
    mode = settings.get("ai_mode", "none")
    if mode == "none":
        return {"ok": False, "error": "请在设置中配置AI服务"}
    def _sync():
        try:
            if mode == "api":
                base_url = settings.get("api_base_url","").rstrip("/")
                api_key = settings.get("api_key","")
                model_name = settings.get("api_model","")
                if not all([base_url, api_key, model_name]):
                    return {"ok": False, "error": "API 配置不完整"}
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                           "HTTP-Referer": "https://ome365.app", "X-Title": "Ome365"}
                payload = {"model": model_name, "max_tokens": max_tokens, "temperature": 0.4,
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}]}
                resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload,
                                timeout=180, **_proxy_kwargs())
                resp.raise_for_status()
                txt = resp.json()["choices"][0]["message"]["content"].strip()
            elif mode == "ollama":
                ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
                payload = {"model": settings.get("ollama_model","llama3.1"), "temperature": 0.4,
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}],
                           "stream": False}
                resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=180, **_proxy_kwargs())
                resp.raise_for_status()
                txt = resp.json().get("message", {}).get("content", "").strip()
            else:
                return {"ok": False, "error": f"未知AI模式: {mode}"}
            cleaned = re.sub(r'^```(?:json)?\s*', '', txt)
            cleaned = re.sub(r'\s*```\s*$', '', cleaned).strip()
            # LLM 偶尔会把 JSON 混在说明里，尝试找第一个 { 到最后一个 }
            if not cleaned.startswith('{'):
                i, j = cleaned.find('{'), cleaned.rfind('}')
                if i != -1 and j > i: cleaned = cleaned[i:j+1]
            return {"ok": True, "data": json.loads(cleaned), "raw": txt}
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"JSON 解析失败: {e}", "raw": txt[:800] if 'txt' in dir() else ''}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return _sync()


@app.get("/api/insights/overview")
async def insights_overview():
    """洞察页面的 overview：语料统计 + 已保存的洞察卡片。"""
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    corpus = _insights_corpus(90)
    cards = []
    for fp in sorted(INSIGHTS_DIR.glob("*.json"), reverse=True):
        if fp.name.startswith("_"):   # skip _latest.json
            continue
        try:
            cards.append(json.loads(fp.read_text("utf-8")))
        except Exception:
            pass
    latest = None
    latest_fp = INSIGHTS_DIR / "_latest.json"
    if latest_fp.exists():
        try:
            latest = json.loads(latest_fp.read_text("utf-8"))
        except Exception:
            pass
    return {"stats": corpus["stats"], "cards": cards, "latest": latest}


@app.post("/api/insights/synthesize")
async def insights_synthesize(body: dict):
    """把所有语料喂给 LLM，输出结构化综合洞察。"""
    days = int(body.get("days", 90))
    focus = (body.get("focus") or "").strip()
    corpus = _insights_corpus(days)
    context = _insights_context_text(corpus)

    focus_hint = f"\n用户特别关注：{focus}\n" if focus else ""

    system = "你是船长的高级战略顾问。输入是船长最近的工作语料（访谈、反思、速记、汇报、长期记忆、联系人）。输出必须是合法 JSON，不要任何说明文字。"
    user = f"""{context}
{focus_hint}
请基于以上语料，为船长（北大计算机硕士、AI 产品与技术领导者、龙湖千丁 CTO）输出以下 JSON：

{{
  "headline": "一句话点明本轮洞察的核心发现（25 字内，直接、有穿透力）",
  "themes": [
    {{"title": "主题名", "summary": "2 句话说明这是什么", "signals": ["支持这个主题的 2-3 条原始片段"]}}
  ],
  "projects": [
    {{"title": "项目/产品点子", "hypothesis": "核心假设（1 句）", "audience": "目标用户", "value": "用户能获得什么", "next_step": "本周可以推进的第一步", "confidence": "high|medium|low"}}
  ],
  "diagnosis": {{
    "strengths": ["3-5 条能力/资源上的优势"],
    "risks": ["3-5 条需要警惕的风险或盲区"],
    "blind_spots": ["2-3 条船长自己可能没注意到的事情"]
  }},
  "opportunities": [
    {{"title": "机会名", "why_now": "为什么此刻成立（结合语料证据）", "action": "一句话行动建议"}}
  ],
  "questions": [
    "3-5 个值得船长下周静下来思考的开放式问题"
  ]
}}

要求：
- themes 4-6 个，projects 3-5 个，opportunities 2-4 个
- 用具体的名词和动词，不要说废话
- signals 必须是从语料里真实抽取的原文碎片（可以精简）
- 所有字段都要填，没有就写 "（语料不足）"
- 只输出 JSON
"""

    result = _ai_call_json(system, user, max_tokens=4000)
    if not result.get("ok"):
        return result
    data = result["data"]
    data["_meta"] = {
        "generated_at": datetime.now().isoformat(timespec='seconds'),
        "days": days,
        "focus": focus,
        "stats": corpus["stats"],
    }
    # 保存 latest
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    (INSIGHTS_DIR / "_latest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    return {"ok": True, "insight": data}


@app.post("/api/insights/save")
async def insights_save(body: dict):
    """把一次 synthesize 的结果（或手动编辑后的版本）存成卡片。"""
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    insight = body.get("insight") or {}
    note = body.get("note", "")
    card_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    card = {
        "id": card_id,
        "saved_at": datetime.now().isoformat(timespec='seconds'),
        "note": note,
        "insight": insight,
    }
    (INSIGHTS_DIR / f"{card_id}.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), "utf-8")
    return {"ok": True, "id": card_id}


@app.delete("/api/insights/card/{card_id}")
async def insights_delete(card_id: str):
    fp = INSIGHTS_DIR / f"{card_id}.json"
    if fp.exists(): fp.unlink()
    return {"ok": True}


@app.post("/api/insights/ask")
async def insights_ask(body: dict):
    """对语料提问，AI 基于船长的真实数据回答。"""
    q = (body.get("question") or "").strip()
    if not q:
        return {"ok": False, "error": "请输入问题"}
    corpus = _insights_corpus(int(body.get("days", 90)))
    context = _insights_context_text(corpus, max_chars=12000)

    system = "你是船长的私人战略顾问，只能基于船长自己的语料回答，不许编造。输出必须是合法 JSON。"
    user = f"""{context}

船长的问题：{q}

请输出 JSON：
{{
  "answer": "基于语料的清晰回答（3-8 句，结构化分点或段落皆可，中文）",
  "evidence": ["2-4 条你引用的语料片段（要是原文出现过的）"],
  "followups": ["2-3 个顺势值得追问的问题"]
}}

只输出 JSON。
"""
    result = _ai_call_json(system, user, max_tokens=2200)
    if not result.get("ok"):
        return result
    return {"ok": True, "reply": result["data"]}


# ── API: Life (生活 · 家庭 / 健康 / 仪式 / 时刻) ──────
# 面向个人生活品质：女儿周末计划、健康打卡、日常仪式、生活高光时刻。
# 核心洞察：米莱真实年龄 11.5 岁 → 上大学还有 ~365 个周末，这个数字
# 必须每天都让船长看到。
LIFE_DIR = VAULT / "Life"
LIFE_DATA_FILE = LIFE_DIR / "life.json"
LIFE_MOMENTS_FILE = LIFE_DIR / "moments.md"

LIFE_DEFAULTS = {
    "daughter": {
        "name": "米莱",
        "birth_date": "2014-09-15",   # 11.5 岁（可在前端编辑）
        "college_age": 18,
    },
    "weekends": [],       # [{id, date, title, theme, activities, notes, done, photos}]
    "weekend_ideas": [],  # [{id, title, vibe, duration, supplies, created_at}]
    "health": {
        "rings": {"sleep": 0, "exercise": 0, "meditate": 0, "diet": 0},  # 今日 0-100
        "logs": [],        # [{date, sleep, exercise, meditate, diet, note}]
        "targets": {"sleep": 8, "exercise": 30, "meditate": 10, "diet": 3},
    },
    "rituals": {
        "morning": [],     # [{id, text, done}]
        "evening": [],
        "weekly": [],
        "streaks": {"morning": 0, "evening": 0, "weekly": 0},
        "last_check": "",
    },
    "moments": [],         # [{id, date, category, text}]
}

def _life_load():
    LIFE_DIR.mkdir(parents=True, exist_ok=True)
    data = _safe_json_load(LIFE_DATA_FILE, default=None)
    if data is None:
        data = json.loads(json.dumps(LIFE_DEFAULTS))
        LIFE_DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    # Merge missing top-level keys from defaults (forward compat)
    for k, v in LIFE_DEFAULTS.items():
        if k not in data:
            data[k] = json.loads(json.dumps(v))
    return data

def _life_save(data: dict):
    LIFE_DIR.mkdir(parents=True, exist_ok=True)
    LIFE_DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

def _weekends_left(birth_date: str, college_age: int = 18) -> dict:
    try:
        bd = datetime.fromisoformat(birth_date).date()
    except Exception:
        return {"age": None, "weekends_left": None, "days_to_college": None}
    today = date.today()
    age_days = (today - bd).days
    age_years = round(age_days / 365.25, 1)
    college_start = bd.replace(year=bd.year + college_age)
    try:
        # make sure leap safe
        college_start = date(bd.year + college_age, bd.month, bd.day if bd.day <= 28 else 28)
    except Exception:
        pass
    days_left = (college_start - today).days
    weekends_left = max(0, days_left // 7)
    return {"age": age_years, "weekends_left": weekends_left, "days_to_college": max(0, days_left)}

def _next_weekend_dates():
    today = date.today()
    # Saturday
    sat_offset = (5 - today.weekday()) % 7
    if sat_offset == 0 and datetime.now().hour >= 20:
        sat_offset = 7
    sat = today + timedelta(days=sat_offset)
    sun = sat + timedelta(days=1)
    return sat.isoformat(), sun.isoformat()


@app.get("/api/life/overview")
async def life_overview():
    data = _life_load()
    d = data["daughter"]
    weekend_info = _weekends_left(d.get("birth_date",""), int(d.get("college_age", 18)))
    sat, sun = _next_weekend_dates()
    # Filter upcoming weekends
    upcoming = [w for w in data["weekends"] if w.get("date","") >= today_s()][:6]
    past = [w for w in data["weekends"] if w.get("date","") < today_s()][-8:][::-1]
    # Last 7 days of health logs
    logs = sorted(data["health"].get("logs", []), key=lambda x: x.get("date",""))
    recent_logs = logs[-7:]
    return {
        "daughter": d,
        "weekend_info": weekend_info,
        "next_weekend": {"saturday": sat, "sunday": sun},
        "upcoming_weekends": upcoming,
        "past_weekends": past,
        "weekend_ideas": data.get("weekend_ideas", [])[-12:],
        "health": {
            "rings": data["health"].get("rings", {"sleep":0,"exercise":0,"meditate":0,"diet":0}),
            "targets": data["health"].get("targets", {}),
            "recent_logs": recent_logs,
            "total_logs": len(logs),
        },
        "rituals": data["rituals"],
        "moments": sorted(data["moments"], key=lambda x: x.get("date",""), reverse=True)[:30],
    }


@app.post("/api/life/daughter")
async def life_daughter_update(body: dict):
    data = _life_load()
    for k in ("name", "birth_date", "college_age"):
        if k in body:
            data["daughter"][k] = body[k]
    _life_save(data)
    return {"ok": True}


@app.post("/api/life/weekend")
async def life_weekend_create(body: dict):
    data = _life_load()
    wk = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "date": body.get("date", ""),
        "title": body.get("title", "").strip() or "未命名周末",
        "theme": body.get("theme", ""),
        "activities": body.get("activities", []),
        "notes": body.get("notes", ""),
        "done": False,
        "photos": [],
        "created_at": today_s(),
    }
    data["weekends"].append(wk)
    _life_save(data)
    return {"ok": True, "id": wk["id"]}


@app.post("/api/life/weekend/toggle")
async def life_weekend_toggle(body: dict):
    data = _life_load()
    wid = body.get("id", "")
    for w in data["weekends"]:
        if w["id"] == wid:
            w["done"] = not w.get("done", False)
            break
    _life_save(data)
    return {"ok": True}


@app.delete("/api/life/weekend/{wid}")
async def life_weekend_delete(wid: str):
    data = _life_load()
    data["weekends"] = [w for w in data["weekends"] if w["id"] != wid]
    _life_save(data)
    return {"ok": True}


@app.post("/api/life/weekend/ideas")
async def life_weekend_ideas(body: dict):
    """AI 生成适合米莱当前年龄的周末活动点子。"""
    data = _life_load()
    d = data["daughter"]
    info = _weekends_left(d.get("birth_date",""))
    age = info.get("age")
    vibe = (body.get("vibe") or "").strip()
    season_hint = body.get("season", "")

    age_text = f"{age} 岁" if age else "11-12 岁"
    vibe_hint = f"\n特别要求：{vibe}" if vibe else ""
    season_text = f"\n当前季节：{season_hint}" if season_hint else ""

    system = "你是一个最懂孩子也最懂父亲的生活策划师。只输出合法 JSON，不要任何说明。"
    user = f"""请为船长（46岁父亲）和女儿米莱（{age_text}，喜欢打击乐/小提琴，养仓鼠和乌龟，梦想做「未来世界设计师」）生成 5 个真正好玩又有意义的周末活动点子。{vibe_hint}{season_text}

要求：
- 不是泛泛的"去公园"，要具体到做什么事、怎么玩
- 父女可以真的一起参与，不是船长看着女儿玩
- 涵盖不同风格：自然/创作/科技/安静相处/探索
- 每个点子要能激发「未来世界设计师」的好奇心
- 北京可执行（或室内通用）

输出 JSON：
{{
  "ideas": [
    {{
      "title": "活动名（8 字内有画面感）",
      "vibe": "自然|创作|科技|安静|探索",
      "duration": "半天|全天|2小时",
      "what": "具体做什么（2-3 句）",
      "why": "为什么对米莱有意义（1 句）",
      "supplies": ["需要准备的 2-4 样东西"]
    }}
  ]
}}
只输出 JSON。
"""
    result = _ai_call_json(system, user, max_tokens=2000)
    if not result.get("ok"):
        return result
    ideas = result["data"].get("ideas", [])
    # 存到 weekend_ideas
    now = datetime.now().isoformat(timespec='seconds')
    for i in ideas:
        i["id"] = datetime.now().strftime("%Y%m%d%H%M%S") + str(hash(i.get("title","")) % 1000)
        i["created_at"] = now
    data["weekend_ideas"] = (data.get("weekend_ideas", []) + ideas)[-30:]
    _life_save(data)
    return {"ok": True, "ideas": ideas}


@app.post("/api/life/health/log")
async def life_health_log(body: dict):
    data = _life_load()
    today = today_s()
    rings = {
        "sleep": int(body.get("sleep", data["health"]["rings"].get("sleep", 0))),
        "exercise": int(body.get("exercise", data["health"]["rings"].get("exercise", 0))),
        "meditate": int(body.get("meditate", data["health"]["rings"].get("meditate", 0))),
        "diet": int(body.get("diet", data["health"]["rings"].get("diet", 0))),
    }
    # clamp
    rings = {k: max(0, min(100, v)) for k, v in rings.items()}
    data["health"]["rings"] = rings
    # Upsert today's log
    logs = data["health"].get("logs", [])
    logs = [l for l in logs if l.get("date") != today]
    logs.append({"date": today, **rings, "note": body.get("note", "")})
    data["health"]["logs"] = sorted(logs, key=lambda x: x.get("date",""))[-60:]
    _life_save(data)
    return {"ok": True, "rings": rings}


@app.post("/api/life/health/targets")
async def life_health_targets(body: dict):
    data = _life_load()
    for k in ("sleep","exercise","meditate","diet"):
        if k in body:
            data["health"]["targets"][k] = body[k]
    _life_save(data)
    return {"ok": True}


@app.post("/api/life/ritual")
async def life_ritual_create(body: dict):
    data = _life_load()
    slot = body.get("slot", "morning")   # morning|evening|weekly
    text = body.get("text", "").strip()
    if not text: return {"ok": False, "error": "空的仪式"}
    if slot not in data["rituals"]: data["rituals"][slot] = []
    data["rituals"][slot].append({
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "text": text,
        "done": False,
    })
    _life_save(data)
    return {"ok": True}


@app.post("/api/life/ritual/toggle")
async def life_ritual_toggle(body: dict):
    data = _life_load()
    slot = body.get("slot", "morning")
    rid = body.get("id", "")
    for r in data["rituals"].get(slot, []):
        if r["id"] == rid:
            r["done"] = not r.get("done", False)
            break
    _life_save(data)
    return {"ok": True}


@app.delete("/api/life/ritual/{slot}/{rid}")
async def life_ritual_delete(slot: str, rid: str):
    data = _life_load()
    data["rituals"][slot] = [r for r in data["rituals"].get(slot, []) if r["id"] != rid]
    _life_save(data)
    return {"ok": True}


@app.post("/api/life/ritual/reset-day")
async def life_ritual_reset_day():
    """每天开始时清空完成状态，计算 streak。"""
    data = _life_load()
    today = today_s()
    if data["rituals"].get("last_check") != today:
        # 如果昨天所有 morning ritual 完成 → streak +1
        for slot in ("morning", "evening"):
            items = data["rituals"].get(slot, [])
            if items and all(r.get("done") for r in items):
                data["rituals"]["streaks"][slot] = data["rituals"]["streaks"].get(slot, 0) + 1
            else:
                data["rituals"]["streaks"][slot] = 0
            for r in items:
                r["done"] = False
        data["rituals"]["last_check"] = today
        _life_save(data)
    return {"ok": True}


@app.post("/api/life/moment")
async def life_moment_create(body: dict):
    data = _life_load()
    mom = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "date": body.get("date", today_s()),
        "category": body.get("category", "高光"),  # 高光 | 平静 | 挑战 | 成长
        "text": body.get("text", "").strip(),
    }
    if not mom["text"]:
        return {"ok": False, "error": "空时刻"}
    data["moments"].append(mom)
    _life_save(data)
    # 同步写入 moments.md 作为可读档案
    try:
        line = f"- [{mom['date']}] #{mom['category']} {mom['text']}\n"
        if LIFE_MOMENTS_FILE.exists():
            LIFE_MOMENTS_FILE.write_text(LIFE_MOMENTS_FILE.read_text("utf-8") + line, "utf-8")
        else:
            LIFE_MOMENTS_FILE.write_text(f"# 生活时刻\n\n{line}", "utf-8")
    except Exception:
        pass
    _auto_growth()
    return {"ok": True, "id": mom["id"]}


@app.delete("/api/life/moment/{mid}")
async def life_moment_delete(mid: str):
    data = _life_load()
    data["moments"] = [m for m in data["moments"] if m["id"] != mid]
    _life_save(data)
    return {"ok": True}


# ── LONGFOR COCKPIT · 千丁战略驾舱 ───────────────────
# Data source: a single markdown file (Vault/Longfor/cockpit.md).
# Structure: YAML frontmatter (meta) + H2 sections (`## id · title`),
# each section may contain prose and ONE optional fenced yaml block (structured data).
# Parsed into {meta, sections:[{id, title, prose_md, data}]} — frontend picks renderer by id.

LONGFOR_DIR = VAULT / "Longfor"
COCKPIT_FILE = LONGFOR_DIR / "cockpit.md"

def _parse_frontmatter(text: str):
    import yaml as _yaml
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = _yaml.safe_load(parts[1]) or {}
    except Exception:
        meta = {}
    return meta, parts[2].lstrip("\n")

def _parse_cockpit_md(md_text: str):
    """Parse cockpit md into {meta, sections}.
    Section header format: `## <id> · <title>` where id is ascii short key.
    """
    import yaml as _yaml
    meta, body = _parse_frontmatter(md_text)
    sections = []
    lines = body.splitlines()
    cur = None
    buf = []
    def flush():
        nonlocal cur, buf
        if cur is None:
            return
        raw = "\n".join(buf).strip()
        # Extract first ```yaml fenced block if any
        data = None
        prose_lines = []
        in_yaml = False
        yaml_lines = []
        captured_yaml = False
        for ln in raw.splitlines():
            if not captured_yaml and ln.strip().startswith("```yaml"):
                in_yaml = True
                continue
            if in_yaml:
                if ln.strip().startswith("```"):
                    in_yaml = False
                    captured_yaml = True
                    try:
                        data = _yaml.safe_load("\n".join(yaml_lines)) or {}
                    except Exception as e:
                        data = {"_error": str(e)}
                    continue
                yaml_lines.append(ln)
                continue
            prose_lines.append(ln)
        cur["prose_md"] = "\n".join(prose_lines).strip()
        cur["data"] = data
        sections.append(cur)
        cur = None
        buf = []
    for ln in lines:
        if ln.startswith("## "):
            flush()
            head = ln[3:].strip()
            # Split on first " · "
            if " · " in head:
                sid, title = head.split(" · ", 1)
            else:
                sid, title = head.split(" ", 1) if " " in head else (head, head)
            cur = {"id": sid.strip(), "title": title.strip()}
            buf = []
        else:
            if cur is not None:
                buf.append(ln)
    flush()
    return {"meta": meta, "sections": sections}

def _md_inline(text: str) -> str:
    """Very small markdown → HTML for prose: **bold**, `code`, line breaks, lists."""
    if not text:
        return ""
    import html as _html
    out = []
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    for p in paras:
        lines = p.splitlines()
        if all(l.strip().startswith(("- ", "* ")) for l in lines if l.strip()):
            out.append("<ul>" + "".join(
                f"<li>{_format_inline(_html.escape(l.strip()[2:]))}</li>" for l in lines if l.strip()
            ) + "</ul>")
        else:
            joined = " ".join(l.strip() for l in lines)
            out.append(f"<p>{_format_inline(_html.escape(joined))}</p>")
    return "".join(out)

def _format_inline(s: str) -> str:
    # **bold**
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    # `code`
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s

@app.get("/api/longfor/cockpit")
async def longfor_cockpit():
    if not COCKPIT_FILE.exists():
        return {"ok": False, "error": "cockpit.md not found", "path": str(COCKPIT_FILE)}
    try:
        md = COCKPIT_FILE.read_text(encoding="utf-8")
        parsed = _parse_cockpit_md(md)
        # Render prose to HTML
        for sec in parsed["sections"]:
            sec["prose_html"] = _md_inline(sec.get("prose_md", ""))
        return {
            "ok": True,
            "path": str(COCKPIT_FILE.relative_to(VAULT)),
            "meta": parsed["meta"],
            "sections": parsed["sections"],
            "mtime": COCKPIT_FILE.stat().st_mtime,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/longfor/cockpit/raw")
async def longfor_cockpit_raw():
    if not COCKPIT_FILE.exists():
        raise HTTPException(404, "cockpit.md not found")
    return {"ok": True, "content": COCKPIT_FILE.read_text(encoding="utf-8"), "mtime": COCKPIT_FILE.stat().st_mtime}

class CockpitSaveBody(BaseModel):
    content: str

@app.post("/api/longfor/cockpit/save")
async def longfor_cockpit_save(body: CockpitSaveBody):
    # Keep a lightweight backup (previous version) before writing
    if COCKPIT_FILE.exists():
        backup = LONGFOR_DIR / ".cockpit.backup.md"
        backup.write_text(COCKPIT_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    COCKPIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    COCKPIT_FILE.write_text(body.content, encoding="utf-8")
    return {"ok": True, "mtime": COCKPIT_FILE.stat().st_mtime, "bytes": len(body.content)}

@app.get("/api/longfor/cockpit/export")
async def longfor_cockpit_export():
    """Return a standalone, print-ready HTML with inline CSS for sharing."""
    if not COCKPIT_FILE.exists():
        raise HTTPException(404, "cockpit.md not found")
    try:
        md = COCKPIT_FILE.read_text(encoding="utf-8")
        parsed = _parse_cockpit_md(md)
        for sec in parsed["sections"]:
            sec["prose_html"] = _md_inline(sec.get("prose_md", ""))
        html = _render_cockpit_standalone(parsed)
        return HTMLResponse(html)
    except Exception as e:
        raise HTTPException(500, str(e))

def _render_cockpit_standalone(parsed: dict) -> str:
    """Render parsed cockpit into a self-contained shareable HTML page."""
    import html as _html
    meta = parsed.get("meta", {}) or {}
    title = _html.escape(meta.get("title", "千丁 · 战略驾舱"))
    subtitle = _html.escape(meta.get("subtitle", ""))
    author = _html.escape(meta.get("author", ""))
    updated = _html.escape(str(meta.get("updated", "")))
    eyebrow = _html.escape(meta.get("eyebrow", "LONGFOR · QIANDING"))
    north_star = _html.escape(meta.get("north_star", ""))
    one_liner = _html.escape(meta.get("one_liner", ""))
    blocks = []
    for sec in parsed["sections"]:
        sid = sec["id"]
        stitle = _html.escape(sec["title"])
        prose_html = sec.get("prose_html", "")
        data = sec.get("data") or {}
        body = _render_section_html(sid, data)
        blocks.append(f"""
<section class="sec sec-{sid}">
  <div class="sec-head">
    <div class="sec-id">{sid.upper()}</div>
    <h2>{stitle}</h2>
  </div>
  <div class="sec-prose">{prose_html}</div>
  {body}
</section>""")
    css = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Helvetica Neue','Inter','Noto Sans SC',sans-serif;background:#0a0c14;color:#e6e8ee;line-height:1.65;-webkit-font-smoothing:antialiased}
.page{max-width:1040px;margin:0 auto;padding:64px 48px 96px}
.cover{text-align:center;padding:80px 0 72px;border-bottom:1px solid rgba(200,169,110,0.18);margin-bottom:64px;position:relative}
.cover::before{content:"";position:absolute;top:30%;left:50%;transform:translateX(-50%);width:620px;height:620px;background:radial-gradient(circle,rgba(200,169,110,0.10),transparent 60%);pointer-events:none;z-index:0}
.cover>*{position:relative;z-index:1}
.eyebrow{letter-spacing:.22em;font-size:11px;color:#c8a96e;text-transform:uppercase;margin-bottom:18px;font-weight:600}
.cover h1{font-size:44px;font-weight:800;background:linear-gradient(135deg,#fff,#c8a96e);-webkit-background-clip:text;background-clip:text;color:transparent;margin-bottom:14px;letter-spacing:-.5px}
.subtitle{font-size:17px;color:#a8abb7;max-width:680px;margin:0 auto 28px;line-height:1.6}
.north{display:inline-block;padding:14px 24px;border:1px solid rgba(200,169,110,0.28);background:rgba(200,169,110,0.05);border-radius:14px;margin-top:12px;font-size:14px;color:#e8d5a8;max-width:720px}
.meta-row{margin-top:24px;font-size:12px;color:#7a7e8c;letter-spacing:.05em}
.sec{margin:80px 0;scroll-margin-top:40px}
.sec-head{margin-bottom:24px;border-left:3px solid #c8a96e;padding-left:18px}
.sec-id{font-size:10px;letter-spacing:.25em;color:#c8a96e;font-weight:700;margin-bottom:4px}
.sec h2{font-size:28px;font-weight:700;color:#fff;letter-spacing:-.3px}
.sec-prose{color:#b8bbc7;font-size:14.5px;margin-bottom:28px;max-width:820px}
.sec-prose p{margin-bottom:10px}
.sec-prose strong{color:#fff;font-weight:600}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.kpi-card{background:linear-gradient(180deg,rgba(200,169,110,0.06),rgba(200,169,110,0.02));border:1px solid rgba(200,169,110,0.18);border-radius:16px;padding:22px 20px}
.kpi-label{font-size:11px;letter-spacing:.12em;color:#c8a96e;text-transform:uppercase;margin-bottom:8px}
.kpi-now{font-size:13px;color:#7a7e8c;margin-top:4px}
.kpi-bar{height:6px;background:rgba(255,255,255,0.05);border-radius:3px;margin:10px 0 8px;overflow:hidden}
.kpi-fill{height:100%;background:linear-gradient(90deg,#c8a96e,#e8d5a8);border-radius:3px}
.kpi-value{font-size:28px;font-weight:700;color:#fff;font-family:'JetBrains Mono',monospace}
.kpi-value .unit{font-size:15px;color:#c8a96e;margin-left:2px}
.kpi-why{font-size:11px;color:#7a7e8c;margin-top:8px;line-height:1.5}
.ch-group{margin-bottom:28px}
.ch-group-head{display:flex;align-items:baseline;gap:14px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.08)}
.ch-group-label{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.22em;color:#60a5fa;font-weight:700}
.ch-group.inno-group .ch-group-label{color:#a78bfa}
.ch-group-title{font-size:14px;font-weight:500;color:#e6e8ee}
.ch-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.ch-card{background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px}
.ch-card.need{background:linear-gradient(180deg,rgba(96,165,250,0.06),rgba(96,165,250,0.01));border-color:rgba(96,165,250,0.2)}
.ch-card.inno{background:linear-gradient(180deg,rgba(167,139,250,0.06),rgba(167,139,250,0.01));border-color:rgba(167,139,250,0.2)}
.ch-head{display:flex;align-items:baseline;gap:10px;margin-bottom:6px}
.ch-code{font-family:'JetBrains Mono',monospace;font-size:11px;color:#c8a96e;font-weight:700}
.ch-name{font-size:15px;font-weight:600;color:#fff}
.ch-status{font-size:10px;letter-spacing:.08em;padding:2px 8px;border-radius:4px;background:rgba(200,169,110,0.1);color:#c8a96e;margin-left:auto}
.ch-row{font-size:12px;color:#8a8d98;margin-top:6px;line-height:1.55}
.ch-row b{color:#d8dae2;font-weight:500;display:inline-block;min-width:48px}
.bu-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.bu-card{background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:18px}
.bu-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.bu-name{font-size:16px;font-weight:600;color:#fff}
.bu-owner{font-size:12px;color:#c8a96e;font-weight:500}
.bu-status-row{display:flex;align-items:center;gap:8px;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.05)}
.bu-role{font-size:11px;color:#8a8d98}
.bu-row-next{margin-top:8px;padding-top:8px;border-top:1px dashed rgba(200,169,110,0.2)}
.bu-row-next b{color:#c8a96e!important}
.bu-status{display:inline-block;font-size:10px;padding:2px 8px;border-radius:4px;letter-spacing:.05em}
.bu-status.healthy{background:rgba(74,222,128,0.14);color:#4ade80}
.bu-status.pivot{background:rgba(251,191,36,0.14);color:#fbbf24}
.bu-status.under_pressure{background:rgba(248,113,113,0.14);color:#f87171}
.bu-status.build{background:rgba(139,139,248,0.14);color:#a5b4fc}
.bu-row{font-size:12px;color:#8a8d98;margin:4px 0;line-height:1.55}
.bu-row b{color:#d8dae2;font-weight:500;min-width:42px;display:inline-block}
.trident-stack{display:flex;flex-direction:column;gap:22px}
.tri-card{border-radius:20px;padding:28px 30px;position:relative;overflow:hidden}
.tri-card.amber{background:linear-gradient(180deg,rgba(251,191,36,0.10),rgba(251,191,36,0.02));border:1px solid rgba(251,191,36,0.24)}
.tri-card.cyan{background:linear-gradient(180deg,rgba(34,211,238,0.10),rgba(34,211,238,0.02));border:1px solid rgba(34,211,238,0.24)}
.tri-card.violet{background:linear-gradient(180deg,rgba(167,139,250,0.10),rgba(167,139,250,0.02));border:1px solid rgba(167,139,250,0.24)}
.tri-code{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.2em;opacity:.7;font-weight:700}
.tri-card.amber .tri-code{color:#fbbf24}
.tri-card.cyan .tri-code{color:#22d3ee}
.tri-card.violet .tri-code{color:#a78bfa}
.tri-name{font-size:22px;font-weight:700;color:#fff;margin:8px 0 4px;line-height:1.3;letter-spacing:-.2px}
.tri-tag{font-size:13px;color:#b8bbc7;margin-bottom:8px}
.tri-horizon{font-size:11px;color:#c8a96e;margin-bottom:16px;letter-spacing:.05em}
.tri-summary{font-size:13.5px;color:#d0d3dc;line-height:1.75;margin-bottom:20px;padding:14px 16px;background:rgba(0,0,0,0.22);border-radius:12px;border-left:2px solid rgba(200,169,110,0.4)}
.tri-block{margin:18px 0}
.tri-block-label{font-size:10px;letter-spacing:.16em;color:#c8a96e;text-transform:uppercase;font-weight:700;margin-bottom:10px}
.seg-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
.seg-item{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:12px 14px}
.seg-bu{font-size:12px;font-weight:600;color:#fff;margin-bottom:3px}
.seg-focus{font-size:11.5px;color:#a8abb7;line-height:1.55;margin-bottom:5px}
.seg-step{font-size:11px;color:#8a8d98;line-height:1.5}
.seg-step b{color:#c8a96e}
.pillar-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
.pillar{background:rgba(255,255,255,0.03);border-left:2px solid rgba(34,211,238,0.4);border-radius:0 10px 10px 0;padding:10px 14px}
.pillar-name{font-size:12.5px;font-weight:600;color:#fff;margin-bottom:3px}
.pillar-detail{font-size:11.5px;color:#a8abb7;line-height:1.55}
.exp-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
.exp-item{background:rgba(255,255,255,0.03);border-left:2px solid rgba(167,139,250,0.4);border-radius:0 10px 10px 0;padding:10px 14px}
.exp-name{font-size:12.5px;font-weight:600;color:#fff;margin-bottom:3px}
.exp-detail{font-size:11.5px;color:#a8abb7;line-height:1.55}
.bp-list{font-size:12px;color:#a8abb7;line-height:1.65;list-style:none;padding:0}
.bp-list li{padding-left:14px;position:relative;margin-bottom:4px}
.bp-list li::before{content:"+";position:absolute;left:2px;color:#c8a96e;font-weight:700}
.tri-firststep{margin-top:14px;padding:10px 14px;background:rgba(200,169,110,0.08);border:1px solid rgba(200,169,110,0.24);border-radius:10px;font-size:12px;color:#e8d5a8}
.tri-firststep b{color:#c8a96e;margin-right:4px}
.tri-note{margin-top:12px;padding:10px 14px;background:rgba(248,113,113,0.05);border:1px solid rgba(248,113,113,0.18);border-radius:10px;font-size:11.5px;color:#b8bbc7;line-height:1.6}
.tri-list{font-size:12px;color:#a8abb7;line-height:1.65;list-style:none;padding:0}
.tri-list li{padding-left:14px;position:relative;margin-bottom:4px}
.tri-list li::before{content:"›";position:absolute;left:2px;color:#c8a96e;font-weight:700}
.tri-foot{margin-top:18px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.06);font-size:11px;color:#8a8d98}
.eff-why{font-size:13px;color:#d0d3dc;background:rgba(200,169,110,0.06);border-left:3px solid #c8a96e;padding:12px 16px;border-radius:0 10px 10px 0;margin-bottom:18px;line-height:1.65}
.eff-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.eff-svc{background:rgba(200,169,110,0.04);border:1px solid rgba(200,169,110,0.16);border-radius:12px;padding:14px 16px}
.eff-name{font-size:13px;font-weight:600;color:#e8d5a8;margin-bottom:5px}
.eff-desc{font-size:11.5px;color:#a8abb7;line-height:1.55}
.eff-first{margin-top:18px;padding:14px 18px;background:rgba(200,169,110,0.08);border:1px solid rgba(200,169,110,0.24);border-radius:12px;font-size:13px;color:#e8d5a8}
.eff-first b{color:#c8a96e;margin-right:6px}
.phases{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media(max-width:900px){.phases{grid-template-columns:1fr}}
.phase{background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:20px}
.phase-label{font-size:13px;font-weight:700;color:#c8a96e;letter-spacing:.04em}
.phase-dates{font-size:11px;color:#7a7e8c;margin:4px 0 10px;font-family:'JetBrains Mono',monospace}
.phase-theme{font-size:13px;color:#fff;font-weight:500;margin-bottom:10px}
.phase-list{font-size:12px;color:#a8abb7;line-height:1.6}
.phase-list li{list-style:none;padding-left:14px;position:relative;margin-bottom:4px}
.phase-list li::before{content:"→";position:absolute;left:0;color:#c8a96e}
.bridge{background:rgba(0,0,0,0.28);border-radius:14px;padding:22px 24px;margin-top:14px;overflow-x:auto;border:1px solid rgba(255,255,255,0.05)}
.bridge table{width:100%;border-collapse:collapse;font-size:13px;min-width:680px}
.bridge th,.bridge td{padding:11px 10px;border-bottom:1px solid rgba(255,255,255,0.06)}
.bridge th{text-align:left;font-size:10px;letter-spacing:.12em;color:#c8a96e;text-transform:uppercase;font-weight:600}
.bridge th:not(:first-child):not(:last-child){text-align:right}
.bridge td.num{text-align:right;font-family:'JetBrains Mono',monospace;color:#e6e8ee;font-weight:500}
.bridge td.num .u{font-size:10px;color:#7a7e8c;margin-left:2px;font-weight:400}
.bridge td.num.strong{color:#fff;font-weight:700;font-size:14px}
.bridge td.num.total{color:#c8a96e;font-weight:700;font-size:14px}
.bridge td.name{color:#fff;font-weight:500;min-width:160px}
.bridge td.name.total-label{color:#c8a96e;font-weight:700;letter-spacing:.05em}
.bridge td.note{font-size:11.5px;color:#7a7e8c;padding-left:16px}
.bridge tfoot tr{border-top:1px solid rgba(200,169,110,0.28)}
.bridge tfoot td{border-bottom:none;padding-top:14px}
.risk-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.risk-card{background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px}
.risk-card.high{border-left:3px solid #f87171}
.risk-card.medium{border-left:3px solid #fbbf24}
.risk-card.low{border-left:3px solid #4ade80}
.risk-title{font-size:13px;font-weight:600;color:#fff;margin-bottom:6px;line-height:1.5}
.risk-mit{font-size:12px;color:#8a8d98;line-height:1.55}
.risk-mit b{color:#c8a96e;font-weight:500}
.asks{display:grid;gap:12px}
.ask-row{display:flex;align-items:center;gap:16px;background:linear-gradient(90deg,rgba(200,169,110,0.08),rgba(200,169,110,0.02));border:1px solid rgba(200,169,110,0.22);border-radius:14px;padding:18px 22px}
.ask-n{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;color:#c8a96e;min-width:36px}
.ask-body{flex:1}
.ask-title{font-size:15px;font-weight:600;color:#fff;margin-bottom:4px}
.ask-why{font-size:12px;color:#a8abb7}
.ask-date{font-family:'JetBrains Mono',monospace;font-size:11px;color:#c8a96e;padding:4px 10px;background:rgba(200,169,110,0.12);border-radius:6px;white-space:nowrap}
.footer{margin-top:80px;padding:32px;text-align:center;border-top:1px solid rgba(200,169,110,0.18);color:#8a8d98;font-size:13px;line-height:1.8}
.footer .sign{color:#c8a96e;margin-top:16px;letter-spacing:.08em;font-size:12px}
@media print{body{background:#fff;color:#111}.page{padding:24px}.cover h1{color:#1e3a8a;background:none;-webkit-text-fill-color:#1e3a8a}.sec h2{color:#1e3a8a}.sec-prose,.bu-row,.ch-row,.tri-list,.phase-list,.risk-mit,.kpi-why,.kpi-now{color:#444}.kpi-value,.ch-name,.bu-name,.tri-name,.phase-theme,.ask-title{color:#111}.footer,.meta-row{color:#666}.tri-hyp{background:#f5f6fa;color:#333}}
"""
    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="page">
  <header class="cover">
    <div class="eyebrow">{eyebrow}</div>
    <h1>{title}</h1>
    <div class="subtitle">{subtitle}</div>
    {f'<div class="north">★ {north_star}</div>' if north_star else ''}
    {f'<div class="north" style="margin-top:10px;background:rgba(200,169,110,0.02);">{one_liner}</div>' if one_liner else ''}
    <div class="meta-row">{author} · 更新于 {updated}</div>
  </header>
  {''.join(blocks)}
  <footer class="footer">
    Longfor Qianding Strategy Cockpit &nbsp;·&nbsp; {updated}<br>
    <div class="sign">{author}</div>
  </footer>
</div>
</body>
</html>"""
    return html_out

def _render_section_html(sid: str, data: dict) -> str:
    import html as _html
    if not data and sid != "notes":
        return ""
    data = data or {}

    def esc(x):
        return _html.escape(str(x)) if x is not None else ""

    if sid == "kpi":
        kpis = data.get("kpis", [])
        cards = []
        for k in kpis:
            cur = k.get("current", 0) or 0
            tgt = k.get("target", 0) or 0
            pct = min(100, int((cur / tgt * 100) if tgt else 0))
            cards.append(f"""<div class="kpi-card">
<div class="kpi-label">{esc(k.get('label',''))} <span class="kpi-hz">· {esc(k.get('horizon',''))}</span></div>
<div class="kpi-value">{tgt}<span class="unit">{esc(k.get('unit',''))}</span></div>
<div class="kpi-bar"><div class="kpi-fill" style="width:{pct}%"></div></div>
<div class="kpi-now">当前 {cur}{esc(k.get('unit',''))} → 目标 {tgt}{esc(k.get('unit',''))}</div>
<div class="kpi-why">{esc(k.get('why',''))}</div>
</div>""")
        return f'<div class="kpi-grid">{"".join(cards)}</div>'

    if sid == "channels":
        def render_group(label_zh, label_en, items, cls):
            cards = []
            for c in items:
                cards.append(f"""<div class="ch-card {cls}">
<div class="ch-head"><span class="ch-code">{esc(c.get('code',''))}</span><span class="ch-name">{esc(c.get('name',''))}</span><span class="ch-status">{esc(c.get('status',''))}</span></div>
<div class="ch-row"><b>痛点</b>{esc(c.get('pain',''))}</div>
<div class="ch-row"><b>AI 落点</b>{esc(c.get('ai_hook',''))}</div>
<div class="ch-row"><b>定位</b>{esc(c.get('qianding_role',''))}</div>
</div>""")
            return f"""<div class="ch-group {cls}-group">
<div class="ch-group-head"><span class="ch-group-label">{label_en}</span><span class="ch-group-title">{label_zh}</span></div>
<div class="ch-grid">{"".join(cards)}</div>
</div>"""
        html_out = ""
        if data.get("c_channels"):
            html_out += render_group("C1 - C5 · 需求方航道", "DEMAND TRACKS", data["c_channels"], "need")
        if data.get("n_channels"):
            html_out += render_group("N1 - N3 · 创新航道", "INNOVATION TRACKS", data["n_channels"], "inno")
        return html_out

    if sid == "bu":
        items = data.get("bu_list", [])
        cards = []
        for b in items:
            status = esc(b.get("status", ""))
            cards.append(f"""<div class="bu-card">
<div class="bu-top">
<div class="bu-name">{esc(b.get('name',''))}</div>
<div class="bu-owner">{esc(b.get('owner',''))}</div>
</div>
<div class="bu-status-row"><span class="bu-status {status}">{status}</span><span class="bu-role">{esc(b.get('role',''))}</span></div>
<div class="bu-row"><b>痛点</b>{esc(b.get('pain',''))}</div>
<div class="bu-row"><b>资产</b>{esc(b.get('asset',''))}</div>
<div class="bu-row"><b>解锁</b>{esc(b.get('unlock',''))}</div>
<div class="bu-row bu-row-next"><b>12 周</b>{esc(b.get('next_12w',''))}</div>
</div>""")
        return f'<div class="bu-grid">{"".join(cards)}</div>'

    if sid == "trident":
        items = data.get("tridents", [])
        cards = []
        for t in items:
            color = esc(t.get("color", "amber"))
            detail_blocks = []
            if t.get("segments"):
                segs = "".join(
                    f'<div class="seg-item"><div class="seg-bu">{esc(s.get("bu",""))}</div>'
                    f'<div class="seg-focus">{esc(s.get("focus",""))}</div>'
                    f'<div class="seg-step"><b>起步 →</b> {esc(s.get("first_step",""))}</div></div>'
                    for s in t["segments"]
                )
                detail_blocks.append(f'<div class="tri-block"><div class="tri-block-label">九条 BU 的分别切入</div><div class="seg-list">{segs}</div></div>')
            if t.get("pillars"):
                items_h = "".join(
                    f'<div class="pillar"><div class="pillar-name">{esc(p.get("name",""))}</div><div class="pillar-detail">{esc(p.get("detail",""))}</div></div>'
                    for p in t["pillars"]
                )
                detail_blocks.append(f'<div class="tri-block"><div class="tri-block-label">六大支柱</div><div class="pillar-grid">{items_h}</div></div>')
            if t.get("experiments"):
                items_h = "".join(
                    f'<div class="exp-item"><div class="exp-name">{esc(e.get("name",""))}</div><div class="exp-detail">{esc(e.get("detail",""))}</div></div>'
                    for e in t["experiments"]
                )
                detail_blocks.append(f'<div class="tri-block"><div class="tri-block-label">重点试验</div><div class="exp-list">{items_h}</div></div>')
            if t.get("best_practices"):
                bps = "".join(f"<li>{esc(x)}</li>" for x in t["best_practices"])
                detail_blocks.append(f'<div class="tri-block"><div class="tri-block-label">引入的外部最佳实践</div><ul class="bp-list">{bps}</ul></div>')
            if t.get("first_step"):
                detail_blocks.append(f'<div class="tri-firststep"><b>第一步 →</b> {esc(t.get("first_step",""))}</div>')
            if t.get("note"):
                detail_blocks.append(f'<div class="tri-note">{esc(t.get("note",""))}</div>')
            if t.get("targets"):
                ts = "".join(f"<li>{esc(x)}</li>" for x in t["targets"])
                detail_blocks.append(f'<div class="tri-block"><div class="tri-block-label">目标</div><ul class="tri-list">{ts}</ul></div>')
            summary = esc(t.get("summary", ""))
            cards.append(f"""<div class="tri-card {color}">
<div class="tri-code">{esc(t.get('code',''))}</div>
<div class="tri-name">{esc(t.get('name',''))}</div>
<div class="tri-tag">{esc(t.get('tagline',''))}</div>
<div class="tri-horizon">◦ {esc(t.get('horizon',''))}</div>
<div class="tri-summary">{summary}</div>
{"".join(detail_blocks)}
<div class="tri-foot">负责方 · {esc(t.get('owner',''))}</div>
</div>""")
        return f'<div class="trident-stack">{"".join(cards)}</div>'

    if sid == "efficiency":
        svcs = data.get("services", [])
        why = esc(data.get("why", ""))
        first = esc(data.get("first_step", ""))
        items = []
        for s in svcs:
            items.append(f'<div class="eff-svc"><div class="eff-name">{esc(s.get("name",""))}</div><div class="eff-desc">{esc(s.get("detail",""))}</div></div>')
        return f"""<div class="eff-why">{why}</div>
<div class="eff-grid">{"".join(items)}</div>
{f'<div class="eff-first"><b>第一步 →</b> {first}</div>' if first else ''}"""

    if sid == "roadmap":
        phases = data.get("phases", [])
        cards = []
        for p in phases:
            outs = "".join(f"<li>{esc(o)}</li>" for o in p.get("outcomes", []))
            cards.append(f"""<div class="phase">
<div class="phase-label">{esc(p.get('label',''))}</div>
<div class="phase-dates">{esc(p.get('dates',''))}</div>
<div class="phase-theme">{esc(p.get('theme',''))}</div>
<ul class="phase-list">{outs}</ul>
</div>""")
        return f'<div class="phases">{"".join(cards)}</div>'

    if sid == "finance":
        rows = data.get("bridge", [])
        trs = []
        for r in rows:
            unit = esc(r.get("unit", ""))
            trs.append(
                f'<tr><td class="name">{esc(r.get("name",""))}</td>'
                f'<td class="num">{r.get("y1",0)}<span class="u">{unit}</span></td>'
                f'<td class="num">{r.get("y2",0)}<span class="u">{unit}</span></td>'
                f'<td class="num">{r.get("y3",0)}<span class="u">{unit}</span></td>'
                f'<td class="num">{r.get("y4",0)}<span class="u">{unit}</span></td>'
                f'<td class="num strong">{r.get("y5",0)}<span class="u">{unit}</span></td>'
                f'<td class="note">{esc(r.get("note",""))}</td></tr>'
            )
        # Totals
        totals = [0,0,0,0,0]
        for r in rows:
            for i, k in enumerate(["y1","y2","y3","y4","y5"]):
                try: totals[i] += float(r.get(k, 0) or 0)
                except: pass
        tot_html = "".join(f'<td class="num total">{round(v,1)}<span class="u">亿</span></td>' for v in totals)
        return f"""<div class="bridge"><table>
<thead><tr><th>业务线</th><th>Y1</th><th>Y2</th><th>Y3</th><th>Y4</th><th>Y5</th><th>说明</th></tr></thead>
<tbody>{"".join(trs)}</tbody>
<tfoot><tr><td class="name total-label">合计</td>{tot_html}<td></td></tr></tfoot>
</table></div>"""

    if sid == "risks":
        items = data.get("risks", [])
        cards = []
        for r in items:
            sev = esc(r.get("severity", "medium"))
            cards.append(f"""<div class="risk-card {sev}">
<div class="risk-title">{esc(r.get('risk',''))}</div>
<div class="risk-mit"><b>对冲</b> · {esc(r.get('mitigation',''))}</div>
</div>""")
        return f'<div class="risk-grid">{"".join(cards)}</div>'

    if sid == "next":
        items = data.get("asks", [])
        rows = []
        for i, a in enumerate(items, 1):
            rows.append(f"""<div class="ask-row">
<div class="ask-n">0{i}</div>
<div class="ask-body"><div class="ask-title">{esc(a.get('title',''))}</div><div class="ask-why">{esc(a.get('why',''))}</div></div>
<div class="ask-date">{esc(a.get('deliver_by',''))}</div>
</div>""")
        return f'<div class="asks">{"".join(rows)}</div>'

    return ""


# ── PWA ───────────────────────────────────────────────
@app.get("/manifest.json")
async def manifest():
    settings = load_settings()
    goal = settings.get("main_goal","Ome365")
    return {"name":"Ome365","short_name":"Ome365","description":goal,"start_url":"/","display":"standalone","background_color":"#09090f","theme_color":"#c8a96e","icons":[{"src":"/icon.svg","sizes":"any","type":"image/svg+xml"}]}

@app.get("/icon.svg")
async def icon():
    return HTMLResponse('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="#09090f"/><text x="256" y="340" font-size="320" font-family="system-ui" font-weight="900" fill="url(#g)" text-anchor="middle">O</text><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#c8a96e"/><stop offset="100%" stop-color="#8a6d3b"/></linearGradient></defs></svg>', media_type="image/svg+xml")

static_dir = Path(__file__).parent / "static"

# ── Share: read-only document sharing ──
# URL: /<user>/<code>  (e.g. /wyon/43ce7eaa)
# Config: SHARE_USERS lists allowed usernames
# Deploy: set SHARE_BASE_URL to your public domain (e.g. https://ome365.example.com)
import hashlib

SHARE_USERS = os.environ.get("SHARE_USERS", "wyon").split(",")
SHARE_BASE_URL = os.environ.get("SHARE_BASE_URL", f"http://localhost:{PORT}")
SHARE_SERVER_PORT = int(os.environ.get("SHARE_PORT", "3651"))
SHARE_SERVER_BASE = os.environ.get("SHARE_SERVER_BASE", f"http://localhost:{SHARE_SERVER_PORT}")
SHARE_REGISTRY = Path(__file__).parent / "share_registry.json"

def _build_share_map():
    smap = {}
    tn = VAULT / "TicNote"
    if not tn.exists():
        return smap
    for md in tn.rglob("*.md"):
        if md.name.startswith("_"):
            continue
        rel = str(md.relative_to(VAULT))
        code = hashlib.sha256(rel.encode()).hexdigest()[:8]
        title = md.stem
        date_str = ""
        participants = ""
        try:
            head = md.read_text("utf-8")[:800]
            lines = head.split("\n")
            if lines and lines[0].strip() == "---":
                for li in lines[1:]:
                    if li.strip() == "---":
                        break
                    tm = re.match(r"^title:\s*(.+)$", li)
                    if tm:
                        title = tm.group(1).strip()
                    dm = re.match(r"^date:\s*(.+)$", li)
                    if dm:
                        date_str = dm.group(1).strip()
                    pm = re.match(r"^participants:\s*(.+)$", li)
                    if pm:
                        participants = pm.group(1).strip()
        except Exception:
            pass
        if not date_str:
            dm2 = re.search(r"(\d{4}-\d{2}-\d{2})", md.stem)
            if dm2:
                date_str = dm2.group(1)
        smap[code] = {"path": rel, "title": title, "name": md.stem, "date": date_str, "participants": participants}
    return smap

_share_map_cache = None

def _get_share_map():
    global _share_map_cache
    if _share_map_cache is None:
        _share_map_cache = _build_share_map()
    return _share_map_cache

@app.get("/api/share/list")
async def share_list():
    smap = _get_share_map()
    base = SHARE_BASE_URL.rstrip("/")
    user = SHARE_USERS[0] if SHARE_USERS else "user"
    return [{"code": k, "url": f"{base}/{user}/{k}", **v} for k, v in sorted(smap.items(), key=lambda x: x[1].get("date",""), reverse=True)]

@app.get("/api/share/refresh")
async def share_refresh():
    global _share_map_cache
    _share_map_cache = _build_share_map()
    return {"count": len(_share_map_cache)}

@app.get("/api/share/code")
async def share_code_for_path(path: str):
    """Get share code + URL for a document path."""
    smap = _get_share_map()
    for code, entry in smap.items():
        if entry["path"] == path:
            base = SHARE_BASE_URL.rstrip("/")
            user = SHARE_USERS[0] if SHARE_USERS else "user"
            return {"code": code, "url": f"{base}/{user}/{code}", "title": entry["title"]}
    raise HTTPException(404, "No share code for this path")

def _load_share_registry():
    if SHARE_REGISTRY.exists():
        return json.loads(SHARE_REGISTRY.read_text("utf-8"))
    return {}

def _save_share_registry(data):
    SHARE_REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

@app.get("/api/share/by-path")
async def share_by_path(path: str, user: str = ""):
    if not user:
        user = SHARE_USERS[0] if SHARE_USERS else "user"
    reg = _load_share_registry()
    ns = reg.get(user, {})
    for slug, entry in ns.items():
        if entry["path"] == path:
            base = SHARE_SERVER_BASE.rstrip("/")
            return {"found": True, "slug": slug, "title": entry["title"], "url": f"{base}/{user}/{slug}", "created": entry.get("created", "")}
    return {"found": False}

@app.get("/api/share/check-slug")
async def share_check_slug(slug: str, user: str = ""):
    if not user:
        user = SHARE_USERS[0] if SHARE_USERS else "user"
    reg = _load_share_registry()
    ns = reg.get(user, {})
    taken = slug in ns
    return {"slug": slug, "available": not taken, "existing": ns[slug] if taken else None}

@app.post("/api/share/register")
async def share_register(slug: str, path: str, title: str = "", user: str = ""):
    if not user:
        user = SHARE_USERS[0] if SHARE_USERS else "user"
    slug_re = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')
    if not slug_re.match(slug):
        raise HTTPException(400, "Slug must be alphanumeric/hyphens/underscores, 1-64 chars")
    fp = VAULT / path
    if not fp.exists():
        raise HTTPException(404, f"File not found: {path}")
    reg = _load_share_registry()
    ns = reg.setdefault(user, {})
    if slug in ns and ns[slug]["path"] != path:
        raise HTTPException(409, f"'{slug}' already taken by: {ns[slug]['title']}")
    # Dedup: remove any existing slug pointing to the same path
    old_slugs = [k for k, v in ns.items() if v["path"] == path and k != slug]
    for old in old_slugs:
        del ns[old]
    if not title:
        title = _extract_title_from_file(fp)
    ns[slug] = {"path": path, "title": title, "created": date.today().isoformat()}
    _save_share_registry(reg)
    base = SHARE_SERVER_BASE.rstrip("/")
    return {"url": f"{base}/{user}/{slug}", "slug": slug, "user": user, "title": title}

def _extract_title_from_file(fp):
    try:
        head = fp.read_text("utf-8")[:600]
        lines = head.split("\n")
        if lines and lines[0].strip() == "---":
            for li in lines[1:]:
                if li.strip() == "---":
                    break
                m = re.match(r"^title:\s*(.+)$", li)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return fp.stem

@app.delete("/api/share/register")
async def share_unregister(slug: str, user: str = ""):
    if not user:
        user = SHARE_USERS[0] if SHARE_USERS else "user"
    reg = _load_share_registry()
    ns = reg.get(user, {})
    if slug not in ns:
        raise HTTPException(404, "Slug not found")
    del ns[slug]
    if not ns:
        del reg[user]
    _save_share_registry(reg)
    return {"ok": True}

@app.get("/api/share/{code}")
async def share_get(code: str):
    smap = _get_share_map()
    entry = smap.get(code)
    if not entry:
        raise HTTPException(404, "Document not found")
    fp = VAULT / entry["path"]
    if not fp.exists():
        raise HTTPException(404, "File missing")
    raw = fp.read_text("utf-8")
    return {"raw": raw, "name": entry["name"], "title": entry["title"], "path": entry["path"]}

# 空仓（sample-vault）场景：REPORTS_DIR 可能不存在，StaticFiles 会抛错 → 确保目录存在
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA.mkdir(parents=True, exist_ok=True)
app.mount("/reports-static", StaticFiles(directory=str(REPORTS_DIR)), name="reports-static")
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

if __name__ == "__main__":
    # Validate vault
    if not VAULT.exists():
        VAULT.mkdir(parents=True, exist_ok=True)
    for d in ["Journal/Daily","Journal/Weekly","Journal/Monthly","Journal/Quarterly","Notes","Decisions","Contacts/people","Projects","AI-Logs","Templates","Memory","Memory/insights","Insights","Life","Longfor"]:
        (VAULT / d).mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(exist_ok=True)

    ip = get_local_ip()
    settings = load_settings()
    goal = settings.get("main_goal","365天个人执行计划")
    mode = settings.get("ai_mode","none")
    ai_status = f"AI: {mode}" if mode != "none" else "AI: 未配置"
    print(f"\n  Ome365 v0.6 · {goal}")
    print(f"  http://localhost:{PORT} · http://{ip}:{PORT}")
    print(f"  Vault: {VAULT} · {ai_status}")
    _init_ome()
    print()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
