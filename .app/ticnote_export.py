#!/usr/bin/env python3
"""
TicNote 通用导出工具
用法：python ticnote_export.py <关键词1> [关键词2] ... [--folder 文件夹名] [--date YYYY-MM-DD]

示例：
  python ticnote_export.py 千丁终面 千丁BU员工访谈
  python ticnote_export.py — --folder 录音文件 --date 2026-04-15
  python ticnote_export.py — — --folder "龙湖千丁-0414"
"""
import argparse, re, time, sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = Path(__file__).resolve().parent.parent / "TicNote"
STATE_DIR = BASE_DIR / "_browser_state"


def safe_fn(title):
    return re.sub(r'[/\\:*?"<>|]', '_', title.strip())[:120]


def click_in_sidebar(page, text, max_x=320):
    """在左栏找到包含text的元素并点击——前缀递减匹配（验证可靠）"""
    for prefix_len in [len(text), 20, 12, 8, 5]:
        prefix = text[:prefix_len]
        loc = page.get_by_text(prefix, exact=False)
        for idx in range(min(loc.count(), 8)):
            el = loc.nth(idx)
            try:
                if el.is_visible(timeout=600):
                    box = el.bounding_box()
                    if box and box["x"] + box["width"] < max_x:
                        el.click()
                        return True
            except:
                pass
    return False


def scrape_tab(page, tab_name):
    """点击tab并抓取中间区域内容（验证可靠）"""
    tab_loc = page.get_by_text(tab_name, exact=True)
    for idx in range(min(tab_loc.count(), 5)):
        el = tab_loc.nth(idx)
        try:
            if el.is_visible(timeout=800):
                box = el.bounding_box()
                if box and box["x"] > 200 and box["width"] < 200:
                    el.click()
                    time.sleep(2.5)
                    for attempt in range(3):
                        content = page.evaluate("""() => {
                            const vw = window.innerWidth;
                            const L = vw * 0.14, R = vw * 0.83;
                            let best = '';
                            for (const el of document.querySelectorAll('div, section, article')) {
                                const r = el.getBoundingClientRect();
                                if (r.left < L || r.right > R || r.width < 200 || r.height < 80) continue;
                                const t = el.innerText?.trim();
                                if (!t || t.length <= best.length) continue;
                                const h = t.slice(0, 200);
                                const junk = ['个人知识库','共享知识库','标准版','剩余','Shadow 2.0','Ask Shadow'];
                                if (junk.filter(k => h.includes(k)).length >= 2) continue;
                                best = t;
                            }
                            return best;
                        }""")
                        if content and len(content) > 50:
                            return content
                        time.sleep(2)
                    print(f"    ⚠️ 内容太短: {len(content) if content else 0} 字", flush=True)
        except Exception as e:
            print(f"    ⚠️ scrape_tab err: {e}", flush=True)
    return None


def list_sidebar(page, max_x=320):
    """打印左栏所有可见文字"""
    items = page.evaluate(f"""() => {{
        const items = [];
        for (const el of document.querySelectorAll('span, div, a, p')) {{
            const r = el.getBoundingClientRect();
            if (r.x + r.width > {max_x} || r.width < 20 || r.height < 8) continue;
            if (r.y < 0 || r.y > window.innerHeight) continue;
            const t = el.innerText?.trim();
            if (t && t.length > 2 && t.length < 120) items.push(t);
        }}
        return [...new Set(items)];
    }}""")
    return items


def main():
    parser = argparse.ArgumentParser(description="TicNote 通用导出工具")
    parser.add_argument("keywords", nargs="+", help="录音标题关键词（每个关键词导出一个录音）")
    parser.add_argument("--folder", default="录音文件", help="TicNote左栏文件夹名（默认：录音文件）")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="导出日期目录（默认今天）")
    parser.add_argument("--auto", action="store_true", help="全自动模式：跳过所有input()，完成后自动关浏览器")
    args = parser.parse_args()

    export_dir = BASE_DIR / args.date
    export_dir.mkdir(exist_ok=True)

    from playwright.sync_api import sync_playwright

    print("=" * 60, flush=True)
    print(f"TicNote 导出 · {args.folder} → {', '.join(args.keywords)}", flush=True)
    print(f"导出目录: {export_dir}", flush=True)
    print("=" * 60, flush=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(STATE_DIR),
            headless=False,
            slow_mo=80,
            viewport={"width": 1400, "height": 900},
            locale="zh-CN",
        )
        page = context.pages[0] if context.pages else context.new_page()
        print("🌐 打开 TicNote...", flush=True)
        page.goto("https://ticnote.cn/zh", timeout=30000)
        time.sleep(4)

        body = page.inner_text("body")[:1000]
        if any(k in body for k in ["知识库", "CaptainWyon", "录音文件"]):
            print("  ✅ 已登录", flush=True)
        else:
            if args.auto:
                print("  ❌ 未登录！auto模式无法交互，退出", flush=True)
                context.close()
                sys.exit(1)
            print("  ❌ 未登录！请在浏览器中登录后按 Enter", flush=True)
            input()

        # 打开文件夹
        print(f"\n📂 打开文件夹: {args.folder}", flush=True)
        if not click_in_sidebar(page, args.folder):
            click_in_sidebar(page, "Recordings")
        time.sleep(3)

        sidebar = list_sidebar(page)
        print(f"  📋 侧栏 {len(sidebar)} 项:", flush=True)
        for s in sidebar[:25]:
            print(f"    {s}", flush=True)

        page.screenshot(path=str(export_dir / "_sidebar.png"))

        exported = 0
        for kw in args.keywords:
            print(f"\n{'─' * 40}", flush=True)
            print(f"📎 查找: {kw}", flush=True)

            # 检查是否已存在含此关键词的导出文件
            existing = [f for f in export_dir.glob("*.md") if kw in f.name and f.stat().st_size > 300]
            if existing:
                print(f"  ⏭️ 已存在: {existing[0].name}", flush=True)
                exported += 1
                continue

            # 先在侧栏找（max_x=320），再在中间区域找（max_x=700，TicNote有时在中间列表展示录音）
            found = click_in_sidebar(page, kw)
            if not found:
                print(f"  🔄 尝试中间区域...", flush=True)
                found = click_in_sidebar(page, kw, max_x=700)
            if not found:
                # 拆分关键词再试（先侧栏再中间）
                for sub in [kw[:len(kw)//2], kw[len(kw)//2:]]:
                    if len(sub) >= 2:
                        print(f"  🔄 尝试子串: {sub}", flush=True)
                        found = click_in_sidebar(page, sub) or click_in_sidebar(page, sub, max_x=700)
                        if found:
                            break
            if not found:
                if args.auto:
                    print("  ❌ 自动找不到，跳过", flush=True)
                    continue
                print("  ❌ 自动找不到，请在左栏手动点击该录音，然后按 Enter", flush=True)
                sidebar2 = list_sidebar(page)
                print("  当前侧栏:", flush=True)
                for s in sidebar2[:30]:
                    print(f"    {s}", flush=True)
                input()

            time.sleep(3)

            output_name = f"{kw}·{args.date}"

            parts = [f"# {output_name}\n"]
            parts.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            parts.append(f"来源文件夹: {args.folder}")
            parts.append(f"URL: {page.url}\n")
            got_any = False

            for tab in ["总结", "转录"]:
                print(f"  📑 {tab}...", end=" ", flush=True)
                content = scrape_tab(page, tab)
                if content:
                    parts.append(f"\n---\n\n## {tab}\n\n{content}\n")
                    got_any = True
                    print(f"✅ {len(content)} 字", flush=True)
                else:
                    print("未找到/不足", flush=True)

            if got_any:
                fp = export_dir / f"{safe_fn(output_name)}.md"
                fp.write_text('\n'.join(parts), "utf-8")
                exported += 1
                print(f"  💾 {fp.name}", flush=True)
            else:
                print("  ❌ 无内容", flush=True)

        print(f"\n{'=' * 60}", flush=True)
        print(f"✅ 导出 {exported}/{len(args.keywords)} 个文件到 {export_dir}/", flush=True)
        for f in sorted(export_dir.glob("*.md")):
            print(f"  📄 {f.name} ({f.stat().st_size:,} B)", flush=True)
        print("=" * 60, flush=True)

        if not args.auto:
            input("\n按 Enter 关闭浏览器...")
        context.close()


if __name__ == "__main__":
    main()
