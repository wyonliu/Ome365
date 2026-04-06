"""
Ome365 v6 — 个人执行面板
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

VAULT = Path(__file__).parent.parent.resolve()
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
    "ai_provider": "none",
    "anthropic_api_key": "",
    "anthropic_model": "claude-sonnet-4-20250514",
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3.1",
}

def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        saved = json.loads(SETTINGS_FILE.read_text("utf-8"))
        merged = {**SETTINGS_DEFAULTS, **saved}
        return merged
    return dict(SETTINGS_DEFAULTS)

def save_settings(settings: dict):
    # Only save known keys (merge with defaults to avoid losing new keys)
    merged = {**SETTINGS_DEFAULTS, **settings}
    SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")

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
        meta = {"date":today_s(),"week":f"W{week_n()}","energy":"/10"}
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
    if TASK_REPEATS_FILE.exists():
        return json.loads(TASK_REPEATS_FILE.read_text("utf-8"))
    return []

def save_task_repeats(repeats):
    TASK_REPEATS_FILE.write_text(json.dumps(repeats, ensure_ascii=False, indent=2), "utf-8")


# ── Special Days ────────────────────────────────────
SPECIAL_DAYS_FILE = Path(__file__).parent / "special_days.json"

def load_special_days():
    if SPECIAL_DAYS_FILE.exists():
        return json.loads(SPECIAL_DAYS_FILE.read_text("utf-8"))
    return []

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
    if CATEGORIES_FILE.exists():
        return json.loads(CATEGORIES_FILE.read_text("utf-8"))
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
    if CONTACT_CATS_FILE.exists():
        return json.loads(CONTACT_CATS_FILE.read_text("utf-8"))
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
    return {"path":str(fp.relative_to(VAULT)), **data}

@app.post("/api/today/toggle")
async def toggle_today(body:dict):
    return {"ok":toggle_task(find_daily(), body.get("text",""))}

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
    ensure_weekly()
    time_str = body.get("time","").strip()
    repeat = body.get("repeat","none")
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


# ── API: Media Upload (voice/image) ──────────────────
MEDIA.mkdir(exist_ok=True)

@app.post("/api/media/upload")
async def upload_media(file: UploadFile = File(...)):
    ext = Path(file.filename or "file").suffix or ".bin"
    if ext.lower() not in ('.webm','.mp3','.wav','.ogg','.m4a','.png','.jpg','.jpeg','.gif','.webp','.heic'):
        raise HTTPException(400, "Unsupported file type")
    uid = uuid.uuid4().hex[:8]
    fname = f"{today_s()}_{uid}{ext}"
    fp = MEDIA / fname
    with open(fp, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok":True,"filename":fname,"url":f"/media/{fname}","size":fp.stat().st_size}

app.mount("/media", StaticFiles(directory=str(MEDIA)), name="media")


# ── API: AI (multi-provider) ──────────────────────────
@app.post("/api/ai")
async def ai_ask(body:dict):
    """Call AI API — supports anthropic, openai-compatible, ollama, or none."""
    prompt = body.get("prompt","")
    context = body.get("context","")
    full_prompt = prompt
    if context:
        full_prompt = f"Context:\n{context}\n\n{prompt}"

    settings = load_settings()
    provider = settings.get("ai_provider", "none")

    # Build system prompt with vault context
    system_msg = f"""你是 Ome365 AI 助手，帮助用户管理365天个人执行计划。
用户的工作目录是: {VAULT}
今天是: {today_s()}
Day: {day_n()}
Week: W{week_n()}
Quarter: Q{quarter_n()}
请用简洁有力的中文回答，像教练对运动员说话。"""

    # Read relevant files for context
    file_context = ""
    daily_fp = find_daily()
    if daily_fp.exists():
        file_context += f"\n--- 今日文件 ({daily_fp.name}) ---\n{daily_fp.read_text('utf-8')[:2000]}\n"
    plan_fp = VAULT / "000-365-PLAN.md"
    if plan_fp.exists():
        file_context += f"\n--- 365计划 ---\n{plan_fp.read_text('utf-8')[:3000]}\n"
    system_with_context = system_msg + file_context

    if provider == "none":
        return {"ok":False, "response":"", "error":"请在设置中配置AI服务"}

    elif provider == "anthropic":
        api_key = settings.get("anthropic_api_key","")
        model = settings.get("anthropic_model","claude-sonnet-4-20250514")
        if not api_key:
            return {"ok":False, "response":"", "error":"请在设置中填写 Anthropic API Key"}
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_with_context,
                messages=[{"role":"user","content":full_prompt}]
            )
            response_text = msg.content[0].text if msg.content else ""
            return {"ok":True, "response":response_text, "provider":"anthropic", "cost":0}
        except ImportError:
            return {"ok":False, "response":"", "error":"anthropic SDK未安装，请运行: pip install anthropic"}
        except Exception as e:
            return {"ok":False, "response":"", "error":str(e)}

    elif provider == "openai":
        import requests as req
        api_key = settings.get("openai_api_key","")
        base_url = settings.get("openai_base_url","https://api.openai.com/v1").rstrip("/")
        model = settings.get("openai_model","gpt-4o")
        if not api_key:
            return {"ok":False, "response":"", "error":"请在设置中填写 OpenAI API Key"}
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "max_tokens": 1024,
                "messages": [
                    {"role":"system","content":system_with_context},
                    {"role":"user","content":full_prompt}
                ]
            }
            resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            response_text = data["choices"][0]["message"]["content"]
            return {"ok":True, "response":response_text, "provider":"openai", "cost":0}
        except Exception as e:
            return {"ok":False, "response":"", "error":str(e)}

    elif provider == "ollama":
        import requests as req
        ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
        model = settings.get("ollama_model","llama3.1")
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role":"system","content":system_with_context},
                    {"role":"user","content":full_prompt}
                ],
                "stream": False,
            }
            resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("message",{}).get("content","")
            return {"ok":True, "response":response_text, "provider":"ollama", "cost":0}
        except Exception as e:
            return {"ok":False, "response":"", "error":str(e)}

    else:
        return {"ok":False, "response":"", "error":f"未知的AI服务提供商: {provider}"}

@app.get("/api/ai/session")
async def ai_session_info():
    settings = load_settings()
    return {"session_id": "sdk", "name": "Ome365", "provider": settings.get("ai_provider","none")}

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
    for field in ("anthropic_api_key", "openai_api_key"):
        if masked.get(field):
            masked[field] = mask_key(masked[field])
    return masked

@app.put("/api/settings")
async def update_settings(body: dict):
    settings = load_settings()
    # For API key fields: if the incoming value looks like a masked value (starts with ••),
    # keep the existing stored key instead of overwriting with the masked display value.
    sensitive_fields = ("anthropic_api_key", "openai_api_key")
    for k, v in body.items():
        if k in sensitive_fields and isinstance(v, str) and v.startswith("••"):
            # Don't overwrite — keep existing key
            continue
        settings[k] = v
    save_settings(settings)
    return {"ok": True}

@app.post("/api/settings/test-ai")
async def test_ai_connection():
    """Test the configured AI connection with a simple prompt."""
    settings = load_settings()
    provider = settings.get("ai_provider","none")

    if provider == "none":
        return {"ok":False, "error":"请先在设置中选择AI服务提供商"}

    test_prompt = "请回复「连接成功」四个字。"

    if provider == "anthropic":
        api_key = settings.get("anthropic_api_key","")
        model = settings.get("anthropic_model","claude-sonnet-4-20250514")
        if not api_key:
            return {"ok":False, "error":"请填写 Anthropic API Key"}
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=model,
                max_tokens=64,
                messages=[{"role":"user","content":test_prompt}]
            )
            text = msg.content[0].text if msg.content else ""
            return {"ok":True, "response":text, "provider":provider}
        except ImportError:
            return {"ok":False, "error":"anthropic SDK未安装: pip install anthropic"}
        except Exception as e:
            return {"ok":False, "error":str(e)}

    elif provider == "openai":
        import requests as req
        api_key = settings.get("openai_api_key","")
        base_url = settings.get("openai_base_url","https://api.openai.com/v1").rstrip("/")
        model = settings.get("openai_model","gpt-4o")
        if not api_key:
            return {"ok":False, "error":"请填写 OpenAI API Key"}
        try:
            headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}
            payload = {"model":model,"max_tokens":64,"messages":[{"role":"user","content":test_prompt}]}
            resp = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            return {"ok":True, "response":text, "provider":provider}
        except Exception as e:
            return {"ok":False, "error":str(e)}

    elif provider == "ollama":
        import requests as req
        ollama_url = settings.get("ollama_url","http://localhost:11434").rstrip("/")
        model = settings.get("ollama_model","llama3.1")
        try:
            payload = {"model":model,"messages":[{"role":"user","content":test_prompt}],"stream":False}
            resp = req.post(f"{ollama_url}/api/chat", json=payload, timeout=60)
            resp.raise_for_status()
            text = resp.json().get("message",{}).get("content","")
            return {"ok":True, "response":text, "provider":provider}
        except Exception as e:
            return {"ok":False, "error":str(e)}

    else:
        return {"ok":False, "error":f"未知提供商: {provider}"}


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
    if not fp.resolve().is_relative_to(VAULT): raise HTTPException(403)
    return parse_md(fp)

FOLDER_ICONS = {
    "根目录":"📋","Journal":"📅","Journal/Daily":"📅","Journal/Weekly":"📋",
    "Journal/Quarterly":"📊","Contacts":"👤","Contacts/people":"👤",
    "Decisions":"⚡","Notes":"✏️","Projects":"🚀","Templates":"📝",
}
FOLDER_ORDER = ["根目录","Journal/Daily","Journal/Weekly","Journal/Quarterly","Notes","Decisions","Contacts/people","Projects","Templates"]

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
    ip = get_local_ip()
    settings = load_settings()
    goal = settings.get("main_goal","365天个人执行计划")
    print(f"\n  Ome365 · {goal}")
    print(f"  http://localhost:{PORT} · http://{ip}:{PORT}")
    print(f"  Vault: {VAULT}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
