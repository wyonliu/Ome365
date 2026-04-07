"""
Ome365 v0.5 — 个人超级助手
启动: cd .app && python3 server.py
"""

import os, re, json, glob, socket, subprocess, shutil, uuid, threading
from datetime import datetime, date, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

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
    if not fp.exists(): return {"quarters":[], "milestones":[], "overview":{}}
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
    vd = (date.today()+timedelta(days=90)).isoformat()
    meta = {"date":today_s(),"scope":body.scope,"impact":body.impact,"status":"待验证","verify_by":vd}
    content = f"""# 决策：{body.title}\n\n## 背景\n{body.background or '（待补充）'}\n\n## 备选方案\n1. **方案A**：\n2. **方案B**：\n\n## 最终选择\n（待补充）\n\n## 验证记录\n> {vd} 回来填写\n"""
    write_md(fp, meta, content)
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
@app.post("/api/notes")
async def create_note(body:dict):
    d = VAULT/"Notes"; d.mkdir(exist_ok=True)
    fp = d/f"{today_s()}.md"
    now = datetime.now().strftime("%H:%M")
    cat = body.get("category","")
    tag = f" #{cat}" if cat and cat != "uncategorized" else ""
    entry = f"- [{now}]{tag} {body['text']}\n"
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
        items = []
        for line in fp.read_text("utf-8").split('\n'):
            m = re.match(r'^- \[(\d{2}:\d{2})\]\s*(?:#(\S+)\s+)?(.*)', line)
            if m:
                item_cat = m.group(2) or ""
                if category and category != "all" and item_cat != category:
                    continue
                items.append({"time":m.group(1),"category":item_cat,"text":m.group(3)})
        if items: results.append({"date":fp.stem,"items":items,"path":str(fp.relative_to(VAULT))})
    return results

@app.get("/api/notes/file/{date_str}")
async def get_note_file(date_str:str):
    fp = VAULT/"Notes"/f"{date_str}.md"
    if not fp.exists(): raise HTTPException(404)
    return {"path":str(fp.relative_to(VAULT)),"raw":fp.read_text("utf-8")}

@app.delete("/api/notes/{date_str}/{idx}")
async def delete_note_item(date_str:str, idx:int):
    """Delete a single note entry by date and line index."""
    fp = VAULT/"Notes"/f"{date_str}.md"
    if not fp.exists(): raise HTTPException(404)
    lines = fp.read_text("utf-8").split('\n')
    # Find all note-entry lines (- [HH:MM] ...)
    entry_lines = [(i, l) for i, l in enumerate(lines) if re.match(r'^- \[\d{2}:\d{2}\]', l)]
    if idx < 0 or idx >= len(entry_lines):
        raise HTTPException(400, "Index out of range")
    line_num = entry_lines[idx][0]
    lines.pop(line_num)
    # If only header remains, delete the file
    remaining_entries = [l for l in lines if re.match(r'^- \[\d{2}:\d{2}\]', l)]
    if not remaining_entries:
        fp.unlink()
    else:
        fp.write_text('\n'.join(lines), "utf-8")
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
    import requests as req
    prompt = body.get("prompt","")
    context = body.get("context","")
    full_prompt = prompt
    if context:
        full_prompt = f"Context:\n{context}\n\n{prompt}"

    settings = load_settings()
    mode = settings.get("ai_mode", "none")

    system_msg = f"""你是 Ome365 AI 助手，帮助用户管理365天个人执行计划。
用户的工作目录是: {VAULT}
今天是: {today_s()}
Day: {day_n()}
Week: W{week_n()}
Quarter: Q{quarter_n()}
请用简洁有力的中文回答，像教练对运动员说话。"""

    file_context = ""
    daily_fp = find_daily()
    if daily_fp.exists():
        file_context += f"\n--- 今日文件 ({daily_fp.name}) ---\n{daily_fp.read_text('utf-8')[:2000]}\n"
    plan_fp = VAULT / "000-365-PLAN.md"
    if plan_fp.exists():
        file_context += f"\n--- 365计划 ---\n{plan_fp.read_text('utf-8')[:3000]}\n"
    # Inject memory context so AI actually uses stored memories
    mem_dir = VAULT / "Memory"
    if mem_dir.exists():
        mem_texts = []
        for mf in sorted(mem_dir.glob("*.md")):
            if mf.name == "MEMORY.md":
                continue
            try:
                txt = mf.read_text("utf-8")[:500]
                mem_texts.append(txt)
            except:
                pass
        if mem_texts:
            file_context += "\n--- 用户记忆 ---\n" + "\n---\n".join(mem_texts[:10]) + "\n"
    system_with_context = system_msg + file_context

    if mode == "none":
        return {"ok":False, "error":"请在设置中配置AI服务"}

    elif mode == "api":
        base_url = settings.get("api_base_url","").rstrip("/")
        api_key = settings.get("api_key","")
        model = settings.get("api_model","")
        if not base_url or not api_key or not model:
            return {"ok":False, "error":"请在设置中填写完整的 API 地址、密钥和模型"}
        try:
            headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json",
                       "HTTP-Referer":"https://ome365.app","X-Title":"Ome365"}
            payload = {"model":model,"max_tokens":1024,"messages":[
                {"role":"system","content":system_with_context},
                {"role":"user","content":full_prompt}
            ]}
            resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60, **_proxy_kwargs())
            if resp.status_code == 403:
                body_text = resp.text[:200]
                if "region" in body_text.lower():
                    return {"ok":False, "error":f"模型 {model} 在当前地区不可用"}
                if "prohibited" in body_text.lower() or "terms" in body_text.lower():
                    return {"ok":False, "error":f"模型 {model} 被提供商拒绝（地区/代理限制），建议换用 deepseek/deepseek-chat"}
                return {"ok":False, "error":f"API 拒绝 (403): {body_text}"}
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return {"ok":True, "response":text, "provider":"api"}
        except req.exceptions.ConnectionError:
            return {"ok":False, "error":f"无法连接 {base_url}，请检查网络和代理设置"}
        except req.exceptions.Timeout:
            return {"ok":False, "error":"AI 请求超时（60s），请重试"}
        except Exception as e:
            return {"ok":False, "error":str(e)}

    elif mode == "ollama":
        ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
        model = settings.get("ollama_model","llama3.1")
        try:
            payload = {"model":model,"messages":[
                {"role":"system","content":system_with_context},
                {"role":"user","content":full_prompt}
            ],"stream":False}
            resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=120, **_proxy_kwargs())
            resp.raise_for_status()
            text = resp.json().get("message",{}).get("content","")
            return {"ok":True, "response":text, "provider":"ollama"}
        except Exception as e:
            return {"ok":False, "error":str(e)}

    return {"ok":False, "error":f"未知模式: {mode}"}

@app.get("/api/ai/session")
async def ai_session_info():
    settings = load_settings()
    return {"session_id": "sdk", "name": "Ome365", "provider": settings.get("ai_mode","none")}

@app.post("/api/ai/smart-input")
async def ai_smart_input(body: dict):
    """AI分析非结构化输入，提取联系人/事件/待办/笔记等结构化数据。"""
    import requests as req
    text = body.get("text", "").strip()
    if not text:
        return {"ok": False, "error": "请输入内容"}

    settings = load_settings()
    if settings.get("ai_mode", "none") == "none":
        return {"ok": False, "error": "请先在设置中配置AI"}

    # Gather existing contacts for matching
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    existing_contacts = []
    for fp in sorted(PEOPLE_DIR.glob("*.md")):
        c = parse_contact(fp)
        existing_contacts.append({"name": c["name"], "slug": c["slug"], "company": c.get("company",""), "title": c.get("title","")})

    prompt = f"""你是一个超级结构化信息提取器。分析以下用户输入（可能是对话记录、会议笔记、微信聊天摘要等），提取以下结构化数据：

1. **联系人**：提到的人名、公司、职位、联系方式等。对于每个人，判断是"new"还是"update"（和已有联系人匹配）。
2. **事件/互动记录**：谁和谁发生了什么事，什么时候。
3. **待办事项**：需要跟进/完成的事情，附上时间（如果有）。
4. **速记/笔记**：值得记录的信息片段。

已有联系人列表（用于匹配）：
{json.dumps(existing_contacts, ensure_ascii=False)[:2000]}

今天是：{today_s()}

请输出JSON，格式：
{{
  "contacts": [
    {{"action":"new"|"update", "slug":"已有联系人的slug或空", "name":"姓名", "company":"公司", "title":"职位", "category":"industry|friend|partner|team|mentor|talent|investor", "met_context":"认识场景", "info":"需补充/更新的信息"}}
  ],
  "interactions": [
    {{"contact_name":"联系人姓名", "method":"微信|电话|面聊|其他", "summary":"互动摘要"}}
  ],
  "todos": [
    {{"text":"待办内容", "time":"HH:MM或空", "priority":"high|normal"}}
  ],
  "notes": [
    {{"text":"笔记内容", "category":""}}
  ],
  "summary": "一句话总结提取了什么"
}}

只输出JSON，不要其他文字。

用户输入：
{text}"""

    try:
        if settings.get("ai_mode") == "api":
            base_url = settings.get("api_base_url","").rstrip("/")
            api_key = settings.get("api_key","")
            model = settings.get("api_model","")
            headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json",
                       "HTTP-Referer":"https://ome365.app","X-Title":"Ome365"}
            payload = {"model":model,"max_tokens":2000,"messages":[
                {"role":"system","content":"你是结构化信息提取器，只输出JSON。"},
                {"role":"user","content":prompt}
            ]}
            resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60, **_proxy_kwargs())
            resp.raise_for_status()
            ai_text = resp.json()["choices"][0]["message"]["content"].strip()
        elif settings.get("ai_mode") == "ollama":
            ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
            payload = {"model":settings.get("ollama_model","llama3.1"),"messages":[
                {"role":"system","content":"你是结构化信息提取器，只输出JSON。"},
                {"role":"user","content":prompt}
            ],"stream":False}
            resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=120, **_proxy_kwargs())
            resp.raise_for_status()
            ai_text = resp.json().get("message",{}).get("content","").strip()
        else:
            return {"ok":False, "error":f"未知AI模式: {settings.get('ai_mode')}"}

        # Parse JSON from AI response (handle markdown code blocks)
        ai_text = re.sub(r'^```json\s*', '', ai_text)
        ai_text = re.sub(r'\s*```$', '', ai_text)
        result = json.loads(ai_text)
        return {"ok": True, "data": result}
    except json.JSONDecodeError:
        return {"ok": True, "data": {"contacts":[],"interactions":[],"todos":[],"notes":[],"summary":"AI返回格式异常，请重试"}, "raw": ai_text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/ai/smart-input/apply")
async def ai_smart_input_apply(body: dict):
    """Apply extracted structured data: create/update contacts, add todos, add notes, add interactions."""
    results = {"contacts_created":0, "contacts_updated":0, "interactions_added":0, "todos_added":0, "notes_added":0}
    data = body.get("data", {})

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
        time_str = todo.get("time","")
        if time_str:
            text = f"[{time_str}] {text}"
        fp = find_daily()
        if not fp.exists():
            fp.write_text(f"# {today_s()} {WEEKDAYS[date.today().weekday()]}\n\n## 任务\n- [ ] {text}\n", "utf-8")
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
    daily_dir = VAULT/"Journal"/"Daily"
    notes_dir = VAULT/"Notes"
    dec_dir = VAULT/"Decisions"
    days = []
    for i in range(365):
        d = START + timedelta(days=i); ds = d.isoformat()
        level = 0; detail = []
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
            elif data["content"].strip(): level = max(level,1); detail.append("有日记")
        nfp = notes_dir/f"{ds}.md"
        if nfp.exists():
            cnt = nfp.read_text("utf-8").count("\n- [")
            if cnt > 0: level = max(level,1); detail.append(f"速记 {cnt}")
        for fp in (dec_dir.glob(f"{ds}-*.md") if dec_dir.exists() else []):
            level = max(level,2); detail.append("决策"); break
        if d > date.today() and level == 0: level = -1
        days.append({"date":ds,"weekday":d.weekday(),"level":level,"detail":" · ".join(detail)})
    return {"start_date":START.isoformat(),"days":days}


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
    """AI-powered daily/weekly reflection that generates insights and saves to Memory."""
    import requests as req
    reflect_type = body.get("type", "daily")  # "daily" or "weekly"
    settings = load_settings()
    mode = settings.get("ai_mode", "none")

    if mode == "none":
        return {"ok": False, "error": "请先配置AI"}

    # Gather context
    context_parts = []
    if reflect_type == "daily":
        fp = find_daily()
        if fp.exists():
            context_parts.append(f"--- 今日日志 ---\n{fp.read_text('utf-8')[:3000]}")
        notes_fp = VAULT / "Notes" / f"{today_s()}.md"
        if notes_fp.exists():
            context_parts.append(f"--- 今日速记 ---\n{notes_fp.read_text('utf-8')[:2000]}")
        prompt = """请对我今天的工作做一个深度反思，包含：
1. 关键成就（做到了什么）
2. 模式识别（重复出现的行为/思维模式）
3. 改进建议（明天可以怎么做得更好）
4. 一句打气的话
请简洁有力，不要说教。"""
    else:
        # Weekly
        for i in range(7):
            d = today_s() if i == 0 else (date.today() - timedelta(days=i)).isoformat()
            fp = VAULT / "Journal" / "Daily" / f"{d}.md"
            if fp.exists():
                context_parts.append(f"--- {d} ---\n{fp.read_text('utf-8')[:1500]}")
        weekly_fp = find_weekly()
        if weekly_fp.exists():
            context_parts.append(f"--- 本周计划 ---\n{weekly_fp.read_text('utf-8')[:2000]}")
        prompt = """请对我这一周做一个深度反思，包含：
1. 本周最大收获
2. 本周关键洞察（从行为模式中发现了什么）
3. 需要调整的方向
4. 下周建议聚焦的1-2件事
请简洁有力。"""

    # Memory context
    ensure_memory_dir()
    memory_context = ""
    for fp in sorted(MEMORY_DIR.glob("*.md"))[:5]:
        if fp.name == "MEMORY.md":
            continue
        memory_context += f"\n--- Memory: {fp.stem} ---\n{fp.read_text('utf-8')[:500]}\n"

    full_context = "\n".join(context_parts) + memory_context

    system_msg = f"""你是 Ome365 AI 助手，帮助用户做深度反思和洞察提取。
今天是: {today_s()} Day {day_n()} W{week_n()} Q{quarter_n()}
你了解用户的记忆档案，请基于这些做个性化反思。
用简洁有力的中文，像教练对运动员说话。"""

    # Call AI
    if mode == "api":
        base_url = settings.get("api_base_url", "").rstrip("/")
        api_key = settings.get("api_key", "")
        model = settings.get("api_model", "")
        if not all([base_url, api_key, model]):
            return {"ok": False, "error": "请配置完整的API信息"}
        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                       "HTTP-Referer": "https://ome365.app", "X-Title": "Ome365"}
            payload = {"model": model, "max_tokens": 1500, "messages": [
                {"role": "system", "content": system_msg + "\n" + full_context},
                {"role": "user", "content": prompt}
            ]}
            resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=90, **_proxy_kwargs())
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]

            # Save insight to Memory/insights/
            insights_dir = MEMORY_DIR / "insights"
            insights_dir.mkdir(exist_ok=True)
            insight_fp = insights_dir / f"{today_s()}_{reflect_type}.md"
            insight_meta = f"---\nname: {reflect_type}_reflection_{today_s()}\ntype: insight\ndescription: {reflect_type} reflection for {today_s()}\n---\n\n"
            insight_fp.write_text(insight_meta + text, "utf-8")

            return {"ok": True, "response": text, "saved_to": str(insight_fp.relative_to(VAULT))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif mode == "ollama":
        ollama_url = settings.get("ollama_url", "http://localhost:11434").rstrip("/")
        model = settings.get("ollama_model", "llama3.1")
        try:
            payload = {"model": model, "messages": [
                {"role": "system", "content": system_msg + "\n" + full_context},
                {"role": "user", "content": prompt}
            ], "stream": False}
            resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=120, **_proxy_kwargs())
            resp.raise_for_status()
            text = resp.json().get("message", {}).get("content", "")

            insights_dir = MEMORY_DIR / "insights"
            insights_dir.mkdir(exist_ok=True)
            insight_fp = insights_dir / f"{today_s()}_{reflect_type}.md"
            insight_meta = f"---\nname: {reflect_type}_reflection_{today_s()}\ntype: insight\ndescription: {reflect_type} reflection for {today_s()}\n---\n\n"
            insight_fp.write_text(insight_meta + text, "utf-8")

            return {"ok": True, "response": text, "saved_to": str(insight_fp.relative_to(VAULT))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"未知模式: {mode}"}


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
    """Background growth interaction increment."""
    try:
        growth = load_growth()
        growth["total_interactions"] = growth.get("total_interactions", 0) + count
        if growth["total_interactions"] % 20 == 0:
            growth["evolution_pending"] = True
        save_growth(growth)
    except:
        pass

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
    return _compute_growth_state()

@app.post("/api/growth/interact")
async def record_interaction(body: dict = {}):
    """Record an interaction (called after AI use, note creation, etc.)"""
    growth = load_growth()
    growth["total_interactions"] = growth.get("total_interactions", 0) + body.get("count", 1)
    total = growth["total_interactions"]
    # Flag evolution pending every 20 interactions
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
    import requests as req
    settings = load_settings()
    if settings.get("ai_mode", "none") == "none":
        return {"ok": False, "error": "请先配置AI"}

    growth = load_growth()

    # Gather recent context
    context_parts = []
    fp = find_daily()
    if fp.exists():
        context_parts.append(fp.read_text("utf-8")[:2000])
    # Recent notes
    notes_dir = VAULT / "Notes"
    if notes_dir.exists():
        for nf in sorted(notes_dir.glob("*.md"), reverse=True)[:3]:
            context_parts.append(nf.read_text("utf-8")[:500])
    # Memories
    mem_dir = VAULT / "Memory"
    if mem_dir.exists():
        for mf in sorted(mem_dir.glob("*.md"))[:5]:
            if mf.name != "MEMORY.md":
                context_parts.append(mf.read_text("utf-8")[:300])

    current_traits = ", ".join(growth.get("traits", [])) or growth.get("ome_personality", "好奇、温暖、直接")
    prompt = f"""分析以下用户数据，为AI助手"{growth.get('ome_name','Ome')}"生成一条个性进化记录。

当前个性特征：{current_traits}
总互动次数：{growth.get('total_interactions',0)}
相识天数：{(date.today() - date.fromisoformat(growth.get('first_use_date', today_s()))).days}

用户数据：
{chr(10).join(context_parts)[:3000]}

请输出一条JSON，格式：{{"shift":"一句话描述个性变化（如：变得更关注用户的能量状态）","new_trait":"新增特征词（如：敏感体察）","reason":"原因（15字以内）"}}
只输出JSON，不要其他文字。"""

    try:
        if settings.get("ai_mode") == "api":
            base_url = settings.get("api_base_url","").rstrip("/")
            api_key = settings.get("api_key","")
            model = settings.get("api_model","")
            headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json",
                       "HTTP-Referer":"https://ome365.app","X-Title":"Ome365"}
            payload = {"model":model,"max_tokens":200,"messages":[
                {"role":"system","content":"你是个性进化分析器，只输出JSON。"},
                {"role":"user","content":prompt}
            ]}
            resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=30, **_proxy_kwargs())
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
        elif settings.get("ai_mode") == "ollama":
            ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
            payload = {"model":settings.get("ollama_model","llama3.1"),"messages":[
                {"role":"system","content":"你是个性进化分析器，只输出JSON。"},
                {"role":"user","content":prompt}
            ],"stream":False}
            resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=30)
            resp.raise_for_status()
            text = resp.json().get("message",{}).get("content","").strip()
        else:
            return {"ok": False, "error": "AI未配置"}

        # Parse the JSON response
        import re as _re
        json_match = _re.search(r'\{[^}]+\}', text)
        if json_match:
            evo = json.loads(json_match.group())
            entry = {"date": today_s(), "shift": evo.get("shift",""), "reason": evo.get("reason",""),
                     "phase": growth.get("total_interactions",0)}
            growth.setdefault("evolution_log", []).append(entry)
            if evo.get("new_trait"):
                traits = growth.get("traits", [])
                if evo["new_trait"] not in traits:
                    traits.append(evo["new_trait"])
                growth["traits"] = traits[-10:]  # Keep last 10 traits
            save_growth(growth)
            return {"ok": True, "evolution": entry, "new_trait": evo.get("new_trait","")}
        return {"ok": False, "error": "AI返回格式异常"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


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

@app.get("/api/proactive")
async def get_proactive():
    """Generate a proactive AI message based on current context."""
    import requests as req
    settings = load_settings()
    if not settings.get("proactive_enabled", True):
        return {"ok": False, "reason": "disabled"}
    if settings.get("ai_mode", "none") == "none":
        return {"ok": False, "reason": "no_ai"}

    now = datetime.now()
    hour = now.hour

    # Determine proactive trigger type
    fp = find_daily()
    data = parse_md(fp)
    tasks = [t for t in data["tasks"] if t["text"].strip()]
    done = sum(1 for t in tasks if t["done"])
    total = len(tasks)

    # Pick a contextual prompt
    if hour < 9:
        prompt = f"现在是早上{hour}点。用户今天有{total}个任务。给一句简短有力的晨间打气（15字以内），像教练对运动员说的。只输出这句话。"
    elif hour < 12 and done == 0 and total > 0:
        prompt = f"现在上午{hour}点，用户今天{total}个任务一个没开始。给一句温和的推动（15字以内），不要说教。只输出这句话。"
    elif hour >= 12 and hour < 14:
        prompt = f"午间了。用户完成了{done}/{total}个任务。给一句简短的午间提醒或鼓励（15字以内）。只输出这句话。"
    elif hour >= 17 and done < total:
        prompt = f"下午{hour}点了，还有{total-done}个任务没完成。给一句收尾冲刺的短句（15字以内）。只输出这句话。"
    elif hour >= 21:
        prompt = f"晚上{hour}点了。用户今天完成了{done}/{total}个任务。给一句简短的复盘提醒或晚安（15字以内）。只输出这句话。"
    else:
        # No proactive needed right now
        return {"ok": False, "reason": "no_trigger"}

    mode = settings.get("ai_mode")
    try:
        if mode == "api":
            base_url = settings.get("api_base_url","").rstrip("/")
            api_key = settings.get("api_key","")
            model = settings.get("api_model","")
            if not all([base_url, api_key, model]):
                return {"ok": False, "reason": "no_config"}
            headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json",
                       "HTTP-Referer":"https://ome365.app","X-Title":"Ome365"}
            growth = load_growth()
            system_msg = f"你是{growth.get('ome_name','Ome')}，用户的AI助手。个性：{growth.get('ome_personality','温暖直接')}。今天是Day {day_n()}。"
            payload = {"model":model,"max_tokens":50,"messages":[
                {"role":"system","content":system_msg},
                {"role":"user","content":prompt}
            ]}
            resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15, **_proxy_kwargs())
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip().strip('"')
            return {"ok": True, "message": text, "trigger": prompt[:20]}
        elif mode == "ollama":
            ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
            model = settings.get("ollama_model","llama3.1")
            growth = load_growth()
            system_msg = f"你是{growth.get('ome_name','Ome')}，用户的AI助手。个性：{growth.get('ome_personality','温暖直接')}。"
            payload = {"model":model,"messages":[
                {"role":"system","content":system_msg},
                {"role":"user","content":prompt}
            ],"stream":False}
            resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=15)
            resp.raise_for_status()
            text = resp.json().get("message",{}).get("content","").strip().strip('"')
            return {"ok": True, "message": text, "trigger": prompt[:20]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:100]}
    return {"ok": False, "reason": "unknown_mode"}


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
    for d in ["Journal/Daily","Journal/Weekly","Journal/Monthly","Journal/Quarterly","Notes","Decisions","Contacts/people","Projects","AI-Logs","Templates","Memory","Memory/insights"]:
        (VAULT / d).mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(exist_ok=True)

    ip = get_local_ip()
    settings = load_settings()
    goal = settings.get("main_goal","365天个人执行计划")
    mode = settings.get("ai_mode","none")
    ai_status = f"AI: {mode}" if mode != "none" else "AI: 未配置"
    print(f"\n  Ome365 v0.2 · {goal}")
    print(f"  http://localhost:{PORT} · http://{ip}:{PORT}")
    print(f"  Vault: {VAULT} · {ai_status}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
