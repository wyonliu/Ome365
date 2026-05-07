"""
Life Plan routes 测试 · 路径越权 / today-week 解析 / config fallback / auth 门禁。
"""
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import life_plan_routes as lp


# ══════════════════════════════════════════════════════
# Fixtures：在 tmp 目录里 mock 一个 plan_dir + config
# ══════════════════════════════════════════════════════
@pytest.fixture
def plan_env(tmp_path, monkeypatch):
    """
    造一个 tmp plan_dir + 覆盖模块级 _LIVE_CFG / _SAMPLE_CFG 指向 tmp config，
    避免污染真实 .app 下的 config。
    """
    plan_dir = tmp_path / "my-plan"
    (plan_dir / "2026").mkdir(parents=True)

    # 七类典型文件
    files = {
        "2026/00_profile.md": "---\ntitle: Profile\n---\n# Profile\n## 一、身份\n- name: Alice\n\n## 二、家庭\n- 家人 A\n- 家人 B\n- 家人 C\n- 家人 D\n",
        "2026/01_现状诊断.md": "---\ntitle: 现状\n---\n# 现状\n\n## 一、优势\n长。",
        "2026/02_一年目标.md": "---\ntitle: 一年目标\none_thing: '把主业做到 Top 3'\n---\n# 一年目标\n\n> 最重要：把主业做到 Top 3\n\n## 一、主业\n...",
        "2026/03_生活健康铁律.md": "---\ntitle: 铁律\n---\n# 铁律\n## 一、睡眠\n- 23:30 前睡\n## 二、饮食\n- 早餐必吃\n",
        "2026/04_底层心理根因.md": "---\ntitle: 根因\n---\n# 根因",
        "2026/05_今日一页_2026-04-20.md": "---\ntitle: 今日\n---\n# 今日 4-20\n",
        "2026/05_今日一页_2026-04-18.md": "---\ntitle: 今日旧\n---\n# 今日 4-18\n",
        "2026/06_本周一页_W2_2026-04-20_至_04-26.md": "---\ntitle: 本周W2\n---\n# W2\n",
        "2026/06_本周一页_W1_2026-04-13_至_04-19.md": "---\ntitle: 本周W1\n---\n# W1\n",
        "2026/深度分析.md": "---\ntitle: 深度\n---\n# 深度\n",
    }
    for rel, content in files.items():
        fp = plan_dir / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, "utf-8")

    cfg_file = tmp_path / "life_plan_config.json"
    cfg_file.write_text(json.dumps({
        "enabled": True,
        "plan_dir": str(plan_dir),
        "plan_start": "2026-04-08",
        "plan_days": 365,
        "label": "一年规划",
        "quarter_themes": {"Q1": "起手", "Q2": "自律"},
    }), "utf-8")

    # 覆盖模块级路径：live 走 tmp 的，sample 不存在（确保走 live）
    monkeypatch.setattr(lp, "_LIVE_CFG", cfg_file)
    monkeypatch.setattr(lp, "_SAMPLE_CFG", tmp_path / "no_sample.json")

    app = FastAPI()
    app.include_router(lp.build_router())
    client = TestClient(app)

    return {"plan_dir": plan_dir, "cfg_file": cfg_file, "client": client, "tmp": tmp_path}


@pytest.fixture
def empty_env(tmp_path, monkeypatch):
    """不存在 live 也不存在 sample → 所有端点应降级。"""
    monkeypatch.setattr(lp, "_LIVE_CFG", tmp_path / "no_live.json")
    monkeypatch.setattr(lp, "_SAMPLE_CFG", tmp_path / "no_sample.json")
    app = FastAPI()
    app.include_router(lp.build_router())
    return TestClient(app)


# ══════════════════════════════════════════════════════
# /config
# ══════════════════════════════════════════════════════
class TestConfig:
    def test_live_config(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/config")
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is True
        assert data["plan_dir_exists"] is True
        assert data["plan_start"] == "2026-04-08"
        assert data["plan_days"] == 365

    def test_empty_config_degrades(self, empty_env):
        r = empty_env.get("/api/life/plan/config")
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is False
        assert data["plan_dir_exists"] is False


# ══════════════════════════════════════════════════════
# /hero
# ══════════════════════════════════════════════════════
class TestHero:
    def test_hero_day_num(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/hero")
        assert r.status_code == 200
        d = r.json()
        assert d["plan_days"] == 365
        assert d["day_num"] is not None  # 有 plan_start
        assert 0 <= d["progress_pct"] <= 100

    def test_hero_most_important(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/hero")
        d = r.json()
        # 从 02_一年目标 frontmatter.one_thing 抽
        assert "Top 3" in d["most_important"]

    def test_hero_quarter_theme(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/hero")
        d = r.json()
        assert d["quarter"] in (1, 2, 3, 4)
        assert d["quarter_theme"] in ("起手", "自律", "")

    def test_hero_empty(self, empty_env):
        """没 plan_dir 仍应返回，不抛 500。"""
        r = empty_env.get("/api/life/plan/hero")
        assert r.status_code == 200
        d = r.json()
        assert d["day_num"] is None or d["day_num"] >= 0


# ══════════════════════════════════════════════════════
# /tree
# ══════════════════════════════════════════════════════
class TestTree:
    def test_tree_groups(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/tree")
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        g = d["groups"]
        # today: 2 个 05_ 文件
        assert len(g["today"]) == 2
        # today 最新在前
        assert "2026-04-20" in g["today"][0]["name"]
        # week: 2 个 06_
        assert len(g["week"]) == 2
        assert "W2" in g["week"][0]["name"]
        # core: 00-04 五个
        assert len(g["core"]) == 5
        # core 按 name 正序
        assert g["core"][0]["name"].startswith("00")
        # archive: 深度分析
        assert len(g["archive"]) == 1

    def test_tree_titles_extracted(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/tree")
        d = r.json()
        core_titles = [f["title"] for f in d["groups"]["core"]]
        assert "Profile" in core_titles or "# Profile" not in core_titles
        # frontmatter title 优先
        assert any(t == "Profile" for t in core_titles)

    def test_tree_empty(self, empty_env):
        r = empty_env.get("/api/life/plan/tree")
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is False


# ══════════════════════════════════════════════════════
# /doc · 读 + 路径越权
# ══════════════════════════════════════════════════════
class TestDoc:
    def test_doc_read(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/doc", params={"rel": "2026/00_profile.md"})
        assert r.status_code == 200
        d = r.json()
        assert "# Profile" in d["raw"]
        assert d["title"] == "Profile"
        assert d["meta"]["title"] == "Profile"

    def test_doc_not_found(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/doc", params={"rel": "2026/nope.md"})
        assert r.status_code == 404

    def test_doc_escape_rejected_dotdot(self, plan_env):
        """拒 .. 逃逸。"""
        r = plan_env["client"].get("/api/life/plan/doc", params={"rel": "../etc/passwd"})
        assert r.status_code in (400, 403)

    def test_doc_escape_rejected_absolute(self, plan_env):
        """拒绝对路径。"""
        r = plan_env["client"].get("/api/life/plan/doc", params={"rel": "/etc/passwd"})
        assert r.status_code in (400, 403)

    def test_doc_escape_rejected_hidden_dotdot(self, plan_env):
        """中段 .. 也拒。"""
        r = plan_env["client"].get("/api/life/plan/doc", params={"rel": "2026/../../etc/passwd"})
        assert r.status_code in (400, 403)

    def test_doc_only_md(self, plan_env):
        """非 .md 拒。"""
        (plan_env["plan_dir"] / "secret.txt").write_text("x")
        r = plan_env["client"].get("/api/life/plan/doc", params={"rel": "secret.txt"})
        assert r.status_code in (400, 404)


# ══════════════════════════════════════════════════════
# /today + /week
# ══════════════════════════════════════════════════════
class TestTodayWeek:
    def test_today_picks_latest(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/today")
        assert r.status_code == 200
        d = r.json()
        assert "2026-04-20" in d["rel"]  # 最新
        assert "# 今日 4-20" in d["raw"]

    def test_week_picks_latest(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/week")
        assert r.status_code == 200
        d = r.json()
        assert "W2" in d["rel"]  # 最新

    def test_today_empty(self, empty_env):
        r = empty_env.get("/api/life/plan/today")
        assert r.status_code == 404

    def test_today_no_match(self, plan_env):
        # 删掉所有 05_ 文件
        for f in plan_env["plan_dir"].rglob("05_*.md"):
            f.unlink()
        r = plan_env["client"].get("/api/life/plan/today")
        assert r.status_code == 404


# ══════════════════════════════════════════════════════
# /snippet · H2 小节摘取（微升级用）
# ══════════════════════════════════════════════════════
class TestSnippet:
    def test_snippet_basic(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/snippet", params={
            "rel": "2026/00_profile.md",
            "heading": "## 二、家庭",
            "max_lines": 5,
        })
        assert r.status_code == 200
        d = r.json()
        assert "家人 A" in d["snippet"]
        # 不越界到「## 一、身份」
        assert "name: Alice" not in d["snippet"]

    def test_snippet_fuzzy_match(self, plan_env):
        """精确 heading 没匹上、用 key 前缀匹配。"""
        r = plan_env["client"].get("/api/life/plan/snippet", params={
            "rel": "2026/03_生活健康铁律.md",
            "heading": "## 一",  # 模糊
        })
        assert r.status_code == 200
        assert "23:30" in r.json()["snippet"]

    def test_snippet_not_found(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/snippet", params={
            "rel": "2026/00_profile.md",
            "heading": "## 不存在的标题",
        })
        assert r.status_code == 404

    def test_snippet_path_escape(self, plan_env):
        r = plan_env["client"].get("/api/life/plan/snippet", params={
            "rel": "../etc/passwd",
            "heading": "## 一",
        })
        assert r.status_code in (400, 403)


# ══════════════════════════════════════════════════════
# 单元函数（不经过 HTTP）
# ══════════════════════════════════════════════════════
class TestUnits:
    def test_classify(self):
        assert lp._classify("05_今日一页_2026-04-20.md")[0] == "today"
        assert lp._classify("06_本周一页_W2_2026-04-20_至_04-26.md")[0] == "week"
        assert lp._classify("02_一年目标.md")[0] == "core"
        assert lp._classify("深度分析.md")[0] == "archive"

    def test_parse_frontmatter(self):
        meta = lp._parse_frontmatter("---\ntitle: Hi\nday: 12\n---\n# body")
        assert meta["title"] == "Hi"
        assert meta["day"] == "12"

    def test_extract_title_priority(self):
        # frontmatter.title 优先
        t = lp._extract_title("---\ntitle: FM\n---\n# H1", "stem")
        assert t == "FM"
        # 没 frontmatter → H1
        t = lp._extract_title("# H1\n正文", "stem")
        assert t == "H1"
        # 都没有 → stem
        t = lp._extract_title("正文没标题", "stem")
        assert t == "stem"


# ══════════════════════════════════════════════════════
# Dashboard fixture：有真实结构的 05 md（核心3/时间块/红线/破线/主题）
# ══════════════════════════════════════════════════════
@pytest.fixture
def rich_plan_env(tmp_path, monkeypatch):
    plan_dir = tmp_path / "plan"
    (plan_dir / "2026").mkdir(parents=True)

    today_md = """---
title: 今日
---
# 今日一页 · 2026-04-20 周一 · Day 13 of 365

## 今日核心 3 件事

1. **中午 12:15**：发第 1 条红娘开口微信
2. **晨 08:15**：写神临山海 30 分钟
3. **18:30**：硬下班 → 19:15 出发羽毛球

## 时间块（逐项打勾）

| 时间 | 动作 | Done |
|---|---|---|
| 07:30 | 起床，冷水洗脸 | ☐ |
| 07:40 | 晨练 15 分钟 | ☐ |
| 08:15 | 神临山海 30 分钟 | ☐ |
| 18:30 | 硬下班 | ☐ |
| 23:45 | 上床 | ☐ |

## 红线 · 今日不做

- ❌ 不开第二个 Claude Code 会话
- ❌ 18:30 后不回工作消息
- ❌ 羽毛球后不宵夜

## 若破线（自动触发）

- 破 18:30 下班 → 次日 17:30 下班
- 破 24:00 上床 → 次日早晨冷水澡

## 一句话今日主题

节律稳为王。
"""
    (plan_dir / "2026" / "05_今日一页_2026-04-20.md").write_text(today_md, "utf-8")
    (plan_dir / "2026" / "05_今日一页_2026-04-18.md").write_text("---\ntitle: 旧\n---\n# 旧\n", "utf-8")

    cfg_file = tmp_path / "life_plan_config.json"
    cfg_file.write_text(json.dumps({
        "enabled": True,
        "plan_dir": str(plan_dir),
        "plan_start": "2026-04-08",
        "plan_days": 365,
    }), "utf-8")

    monkeypatch.setattr(lp, "_LIVE_CFG", cfg_file)
    monkeypatch.setattr(lp, "_SAMPLE_CFG", tmp_path / "no_sample.json")

    # 假 Ome365 vault 根（给 review_submit 写 Journal）
    vault_root = tmp_path / "fake_vault"
    vault_root.mkdir()
    monkeypatch.setenv("OME365_VAULT", str(vault_root))

    app = FastAPI()
    app.include_router(lp.build_router())
    client = TestClient(app)

    return {
        "plan_dir": plan_dir, "cfg_file": cfg_file, "client": client,
        "vault_root": vault_root, "tmp": tmp_path,
    }


# ══════════════════════════════════════════════════════
# /dashboard
# ══════════════════════════════════════════════════════
class TestDashboard:
    def test_dashboard_by_date(self, rich_plan_env):
        r = rich_plan_env["client"].get("/api/life/plan/dashboard?date=2026-04-20")
        assert r.status_code == 200
        d = r.json()
        assert d["date"] == "2026-04-20"
        assert d["day_num"] == 13
        assert d["weekday"] == 1  # Monday
        assert d["fallback"] is False
        assert "05_今日一页_2026-04-20.md" in d["source_rel"]
        # core_three
        assert len(d["core_three"]) == 3
        assert "红娘" in d["core_three"][0]["text"]
        assert d["core_three"][0]["idx"] == 1
        # blocks
        assert len(d["blocks"]) == 5
        times = [b["time"] for b in d["blocks"]]
        assert "07:30" in times and "23:45" in times
        assert d["blocks"][0]["key"] == "block_07:30"
        # redlines
        assert len(d["redlines"]) == 3
        assert any("Claude Code" in r for r in d["redlines"])
        # penalties
        assert len(d["penalties"]) == 2
        assert "破 18:30" in d["penalties"][0]["trigger"]
        # theme
        assert "节律稳为王" in d["theme"]

    def test_dashboard_fallback_when_no_md_for_date(self, rich_plan_env):
        r = rich_plan_env["client"].get("/api/life/plan/dashboard?date=2027-01-01")
        assert r.status_code == 200
        d = r.json()
        assert d["fallback"] is True
        # 回退到最新 05
        assert "05_今日一页_" in d["source_rel"]
        # 核心 3 / blocks 应来自最新一份（2026-04-20 的那份）
        assert len(d["core_three"]) == 3

    def test_dashboard_invalid_date(self, rich_plan_env):
        r = rich_plan_env["client"].get("/api/life/plan/dashboard?date=not-a-date")
        assert r.status_code == 400

    def test_dashboard_no_plan_dir(self, empty_env):
        r = empty_env.get("/api/life/plan/dashboard?date=2026-04-20")
        assert r.status_code == 404


# ══════════════════════════════════════════════════════
# /progress GET + POST
# ══════════════════════════════════════════════════════
class TestProgress:
    def test_progress_empty_skeleton(self, rich_plan_env):
        r = rich_plan_env["client"].get("/api/life/plan/progress?date=2026-04-20")
        assert r.status_code == 200
        d = r.json()
        assert d["date"] == "2026-04-20"
        assert d["checks"] == {}
        assert d["counters"]["scan_am"] == 0
        assert d["review"]["scores"]["rhythm"] is None

    def test_progress_post_merge(self, rich_plan_env):
        client = rich_plan_env["client"]
        # 第一次 POST
        r1 = client.post("/api/life/plan/progress", json={
            "date": "2026-04-20",
            "checks": {"core_0": True, "block_07:30": True},
            "counters": {"scan_am": 1, "active": 2},
        })
        assert r1.status_code == 200
        assert r1.json()["ok"] is True

        # 第二次 POST 只加一个勾，不应该覆盖前面
        r2 = client.post("/api/life/plan/progress", json={
            "date": "2026-04-20",
            "checks": {"block_08:15": True},
        })
        d2 = r2.json()["data"]
        # 所有旧勾 + 新勾都在
        assert d2["checks"]["core_0"] is True
        assert d2["checks"]["block_07:30"] is True
        assert d2["checks"]["block_08:15"] is True
        assert d2["counters"]["scan_am"] == 1  # 未传也保留

        # 落盘文件存在
        progress_fp = rich_plan_env["plan_dir"] / ".progress" / "2026" / "2026-04-20.json"
        assert progress_fp.exists()
        disk = json.loads(progress_fp.read_text("utf-8"))
        assert disk["checks"]["block_08:15"] is True

    def test_progress_invalid_date(self, rich_plan_env):
        r = rich_plan_env["client"].get("/api/life/plan/progress?date=xxx")
        assert r.status_code == 400

    def test_progress_uncheck(self, rich_plan_env):
        """取消勾选（set false）也能落盘"""
        client = rich_plan_env["client"]
        client.post("/api/life/plan/progress", json={
            "date": "2026-04-20",
            "checks": {"core_0": True},
        })
        client.post("/api/life/plan/progress", json={
            "date": "2026-04-20",
            "checks": {"core_0": False},
        })
        r = client.get("/api/life/plan/progress?date=2026-04-20")
        assert r.json()["checks"]["core_0"] is False


# ══════════════════════════════════════════════════════
# /review/submit
# ══════════════════════════════════════════════════════
class TestReviewSubmit:
    def test_review_submit_creates_journal(self, rich_plan_env):
        client = rich_plan_env["client"]
        r = client.post("/api/life/plan/review/submit", json={
            "date": "2026-04-20",
            "review": {
                "scores": {"rhythm": 4, "body": 3, "mind": 4, "work": 5, "relation": 3, "family": 5},
                "answers": {
                    "done_today": "测试今日",
                    "learned": "测试所学",
                    "tomorrow_one_thing": "测试明日",
                    "fulfilled_moment": "测试达成",
                    "proactive_moment": "测试主动",
                },
            },
        })
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["journal_appended"] is True
        assert d["tomorrow_date"] == "2026-04-21"
        assert d["tomorrow_md_exists"] is False

        # Journal 文件落到假 vault
        journal = rich_plan_env["vault_root"] / "Journal" / "2026" / "2026-04-20.md"
        assert journal.exists()
        text = journal.read_text("utf-8")
        assert "📖 一年规划 · 日复盘 · 2026-04-20" in text
        assert "节律 rhythm: 4" in text
        assert "测试今日" in text
        assert "submitted at" in text

        # progress JSON 也写了
        progress_fp = rich_plan_env["plan_dir"] / ".progress" / "2026" / "2026-04-20.json"
        assert progress_fp.exists()
        disk = json.loads(progress_fp.read_text("utf-8"))
        assert disk["review"]["scores"]["rhythm"] == 4
        assert disk["review"]["submitted_at"] is not None

    def test_review_submit_idempotent(self, rich_plan_env):
        """同一 submitted_at 再提交不重复追加到 Journal"""
        client = rich_plan_env["client"]
        payload = {
            "date": "2026-04-20",
            "review": {
                "scores": {"rhythm": 4},
                "answers": {"done_today": "x"},
                "submitted_at": "2026-04-20T22:00:00",
            },
        }
        client.post("/api/life/plan/review/submit", json=payload)
        client.post("/api/life/plan/review/submit", json=payload)
        journal = rich_plan_env["vault_root"] / "Journal" / "2026" / "2026-04-20.md"
        text = journal.read_text("utf-8")
        # 只出现一次
        assert text.count("2026-04-20T22:00:00") == 1

    def test_review_submit_appends_not_overwrites(self, rich_plan_env):
        """已存在的 Journal 只追加，不覆盖"""
        client = rich_plan_env["client"]
        # 预置一个 Journal 文件（用户已手写了别的内容）
        journal_dir = rich_plan_env["vault_root"] / "Journal" / "2026"
        journal_dir.mkdir(parents=True)
        journal = journal_dir / "2026-04-20.md"
        journal.write_text("# 已有日记\n\n这是我手写的内容。\n", "utf-8")

        client.post("/api/life/plan/review/submit", json={
            "date": "2026-04-20",
            "review": {"scores": {"rhythm": 5}, "answers": {"done_today": "OK"}},
        })
        text = journal.read_text("utf-8")
        assert "我手写的内容" in text   # 旧内容还在
        assert "一年规划 · 日复盘" in text  # 新内容追加

    def test_review_submit_invalid_date(self, rich_plan_env):
        r = rich_plan_env["client"].post("/api/life/plan/review/submit", json={
            "date": "bad", "review": {}
        })
        assert r.status_code == 400


# ══════════════════════════════════════════════════════
# 解析器单测
# ══════════════════════════════════════════════════════
class TestParsers:
    def test_split_h2_sections(self):
        text = "---\ntitle: T\n---\n# H1\n\n## 一、A\nA内容\n\n## 二、B\nB内容\n"
        s = lp._split_h2_sections(text)
        assert "一、A" in s
        assert s["一、A"].strip() == "A内容"
        assert "二、B" in s

    def test_parse_core_three(self):
        text = "# t\n## 今日核心 3 件事\n\n1. 第一件\n2. 第二件\n3. 第三件\n4. 第四件\n"
        items = lp._parse_core_three(text)
        assert len(items) == 3
        assert items[0]["text"] == "第一件"
        assert items[0]["idx"] == 1

    def test_parse_time_blocks(self):
        text = "# t\n## 时间块\n\n| 时间 | 动作 | Done |\n|---|---|---|\n| 07:30 | 起床 | ☐ |\n| 20:00-23:00 | 羽毛球 | ☐ |\n"
        blocks = lp._parse_time_blocks(text)
        assert len(blocks) == 2
        assert blocks[0]["time"] == "07:30"
        assert blocks[0]["action"] == "起床"
        assert blocks[0]["key"] == "block_07:30"
        assert blocks[1]["time"] == "20:00-23:00"

    def test_parse_redlines(self):
        text = "## 红线 · 今日不做\n- ❌ A\n- ❌ B\n"
        lines = lp._parse_redlines(text)
        assert len(lines) == 2
        assert "A" in lines[0]

    def test_parse_penalties(self):
        text = "## 若破线（自动触发）\n\n- 破 X → 罚 Y\n- 破 Z → 罚 W\n"
        ps = lp._parse_penalties(text)
        assert len(ps) == 2
        assert ps[0]["trigger"] == "破 X"
        assert ps[0]["penalty"] == "罚 Y"

    def test_merge_progress_does_not_lose_fields(self):
        existing = lp._empty_progress_skeleton("2026-04-20")
        existing["checks"]["a"] = True
        merged = lp._merge_progress(existing, {"checks": {"b": True}})
        assert merged["checks"]["a"] is True
        assert merged["checks"]["b"] is True
