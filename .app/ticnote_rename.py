#!/usr/bin/env python3
"""
TicNote 批量改名工具
思路：从本地 .md 文件的第一行提取 TicNote 原标题，映射到我们的文件名，然后在 TicNote 里改名。
第一步：--discover 模式，右键点击一个条目看看有没有改名选项
第二步：--rename 模式，批量执行改名
"""

import re, time, sys, json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent / "TicNote"
STATE_DIR = BASE_DIR / "_browser_state"
TICNOTE_DIR = BASE_DIR / "2026-04-09"


def build_mapping():
    """从本地 .md 文件构建 TicNote原标题 → 我们的文件名 映射"""
    mapping = {}
    for fp in TICNOTE_DIR.glob("*.md"):
        first_line = fp.read_text("utf-8").split("\n")[0].lstrip("# ").strip()
        our_name = fp.stem  # 不含 .md
        if first_line and first_line != our_name:
            mapping[first_line] = our_name
    return mapping


def find_sidebar_item(page, title):
    """在左栏找到指定标题的元素"""
    for prefix_len in [len(title), 20, 12, 8]:
        prefix = title[:prefix_len]
        loc = page.get_by_text(prefix, exact=False)
        for idx in range(min(loc.count(), 8)):
            el = loc.nth(idx)
            try:
                if el.is_visible(timeout=500):
                    box = el.bounding_box()
                    if box and box["x"] + box["width"] < 300:
                        return el
            except:
                pass
    return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--discover"

    mapping = build_mapping()
    print(f"📋 找到 {len(mapping)} 条待改名映射:\n")
    for old, new in mapping.items():
        print(f"  {old[:30]:30s} → {new}")
    print()

    if not mapping:
        print("✅ 所有文件名已一致，无需改名")
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(STATE_DIR),
            headless=False,
            slow_mo=80,
            viewport={"width": 1400, "height": 900},
            locale="zh-CN",
        )
        page = context.pages[0] if context.pages else context.new_page()

        # 监听网络请求
        api_calls = []
        page.on("request", lambda req: api_calls.append({
            "url": req.url, "method": req.method,
            "post": req.post_data[:500] if req.post_data else None
        }) if ("api" in req.url or "ticnote" in req.url) and req.method in ("POST", "PUT", "PATCH") else None)

        page.goto("https://ticnote.cn/zh", timeout=30000)
        time.sleep(3)

        if mode == "--discover":
            # ── 发现模式：试探改名机制 ──
            test_title = list(mapping.keys())[0]
            print(f"\n🔍 Discovery: 尝试对「{test_title[:20]}...」触发改名\n")

            el = find_sidebar_item(page, test_title)
            if not el:
                print("  ❌ 左栏找不到该条目")
                input("按 Enter 关闭...")
                context.close()
                return

            # 策略A：右键菜单
            print("  🖱️ 策略A: 右键点击...")
            api_calls.clear()
            el.click(button="right")
            time.sleep(1.5)
            page.screenshot(path=str(BASE_DIR / "_rename_rightclick.png"))
            print(f"    截图: _rename_rightclick.png")

            # 看有没有重命名选项
            rename_found = False
            for keyword in ["重命名", "Rename", "rename", "编辑", "修改名称"]:
                loc = page.get_by_text(keyword, exact=False)
                if loc.count() > 0:
                    print(f"    ✅ 发现「{keyword}」选项！")
                    rename_found = True
                    # 点击它
                    loc.first.click()
                    time.sleep(1)
                    page.screenshot(path=str(BASE_DIR / "_rename_input.png"))
                    print(f"    截图: _rename_input.png")

                    # 检查是否出现了输入框
                    inputs = page.locator("input:visible, [contenteditable='true']:visible")
                    if inputs.count() > 0:
                        print(f"    ✅ 输入框出现！可以改名")
                        # 试一下改名
                        page.keyboard.press("Meta+a")
                        page.keyboard.type(mapping[test_title])
                        page.keyboard.press("Enter")
                        time.sleep(1)
                        page.screenshot(path=str(BASE_DIR / "_rename_done.png"))
                        print(f"    截图: _rename_done.png")
                        if api_calls:
                            print(f"    📡 捕获API调用:")
                            for c in api_calls:
                                print(f"      {c['method']} {c['url'][:80]}")
                                if c['post']:
                                    print(f"        body: {c['post'][:200]}")
                    break

            if not rename_found:
                # 关掉右键菜单
                page.keyboard.press("Escape")
                time.sleep(0.5)

                # 策略B：双击
                print("  🖱️ 策略B: 双击...")
                el = find_sidebar_item(page, test_title)
                if el:
                    el.dblclick()
                    time.sleep(1)
                    page.screenshot(path=str(BASE_DIR / "_rename_dblclick.png"))
                    print(f"    截图: _rename_dblclick.png")
                    inputs = page.locator("input:visible, [contenteditable='true']:visible")
                    if inputs.count() > 0:
                        print(f"    ✅ 双击后出现输入框！")
                    else:
                        print(f"    ❌ 双击无效")

                # 策略C：hover 看三点菜单
                print("  🖱️ 策略C: hover 找更多按钮...")
                el = find_sidebar_item(page, test_title)
                if el:
                    el.hover()
                    time.sleep(1)
                    page.screenshot(path=str(BASE_DIR / "_rename_hover.png"))
                    print(f"    截图: _rename_hover.png")
                    # 找 ... 按钮
                    parent = el.locator("xpath=..")
                    more = parent.locator("button, svg, [class*='more'], [class*='menu'], [class*='action']")
                    if more.count() > 0:
                        print(f"    ✅ 发现 {more.count()} 个操作按钮")
                        more.first.click()
                        time.sleep(1)
                        page.screenshot(path=str(BASE_DIR / "_rename_more_menu.png"))

            if api_calls:
                print(f"\n📡 所有捕获的API调用:")
                for c in api_calls:
                    print(f"  {c['method']} {c['url']}")

            print("\n查看截图判断哪种方式可行，然后跑 --rename")

        elif mode == "--rename":
            # ── 批量改名模式 ──
            print(f"\n🔄 开始批量改名 {len(mapping)} 条...\n")
            success = 0
            failed = []

            for old_title, new_name in mapping.items():
                print(f"  [{success+len(failed)+1}/{len(mapping)}] {old_title[:25]} → {new_name[:35]}")

                el = find_sidebar_item(page, old_title)
                if not el:
                    # 可能已经改过了，用新名字找
                    el = find_sidebar_item(page, new_name)
                    if el:
                        print(f"    ⏭️ 已改过")
                        success += 1
                        continue
                    print(f"    ❌ 找不到")
                    failed.append(old_title)
                    continue

                try:
                    el.click(button="right")
                    time.sleep(1)

                    rename_btn = page.get_by_text("重命名", exact=False)
                    if rename_btn.count() == 0:
                        rename_btn = page.get_by_text("Rename", exact=False)
                    if rename_btn.count() == 0:
                        print(f"    ❌ 无改名选项")
                        page.keyboard.press("Escape")
                        failed.append(old_title)
                        continue

                    rename_btn.first.click()
                    time.sleep(0.5)

                    page.keyboard.press("Meta+a")
                    page.keyboard.type(new_name)
                    page.keyboard.press("Enter")
                    time.sleep(1)
                    success += 1
                    print(f"    ✅")
                except Exception as e:
                    print(f"    ❌ {e}")
                    failed.append(old_title)
                    page.keyboard.press("Escape")
                    time.sleep(0.5)

            print(f"\n{'='*60}")
            print(f"✅ 成功: {success}  ❌ 失败: {len(failed)}")
            if failed:
                for t in failed:
                    print(f"  · {t}")

        input("\n按 Enter 关闭浏览器...")
        context.close()


if __name__ == "__main__":
    main()
