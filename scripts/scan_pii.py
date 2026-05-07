#!/usr/bin/env python3
"""
Ome365 PII 4 道防线扫描器
v3.6 §10 D0.3 line 505 + §13.1 line 654（4-17 47 项 PII 泄漏教训防御）

用法：
  python3 scripts/scan_pii.py                    # L1 + L2 + L4 (默认·快)
  python3 scripts/scan_pii.py --history          # +L3 git history (慢·D-1 single canonical pass 用)
  python3 scripts/scan_pii.py --fixtures         # contract test against tests/fixtures/pii_47.txt
  python3 scripts/scan_pii.py --staged-only      # 只扫 staged·pre-commit hook 模式

退出码:
  0  = clean (no hits)
  N  = N hits across layers (use stderr for human-readable list)

4 道防线：
  L1·路径黑名单     - tracked 文件不应包含 PII 配置 / db / key
  L2·内容黑名单     - 文件内容不应含 API key / 密码 hash / 私钥
  L3·Git history    - 历史 commit blob 不应含业务 blocklist 词（opt-in·--history）
  L4·文件大小异常   - tracked >5MB 非 vendor 文件可能是数据泄漏

依赖：python3 标准库·git·grep
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── L1·绝对禁止 tracked 的 PII 配置路径 ───────────────────────────────────
PROTECTED_PATHS = [
    r'\.app/cockpit_config\.json$',
    r'\.app/tenant_config\.json$',
    r'\.app/share_registry\.json$',
    r'\.app/master\.key$',
    r'\.app/share_auth\.db$',
    r'\.app/settings\.json$',
    r'\.app/categories\.json$',
    r'\.app/contact_categories\.json$',
    r'\.app/special_days\.json$',
    r'\.app/task_repeats\.json$',
    r'\.app/reminders\.json$',
    r'\.app/claude_session\.json$',
    r'\.app/life_plan_config\.json$',
    r'\.app/growth\.json$',
    # 注：.app/life-plan-demo/ 是合法 demo 占位（v3.6 §四 line 168）·非 PII·不入 PROTECTED
    r'skills/truthguard/truth\.yml$',
    r'docs/SHARE_PASSWORD_UX_DESIGN\.md$',
    r'docs/SHARE_PRIVACY_DESIGN\.md$',
    r'docs/WORK_ASSISTANT_BRIEF\.md$',
    r'docs/INTERNAL_PLAYBOOK\.md$',
    r'docs/internal/',
    r'\.app/UPGRADE_V8\.md$',
    r'\.app/UPGRADE_V8_FULL\.md$',
    r'\.app/\.deploy-hash$',
    r'\.app/\.session-state$',
    r'\.ome365-bootstrapped$',
    r'^\.env$',
    r'^\.env\.local$',
    r'^\.env\.production$',
    r'^\.env\.[a-zA-Z]+\.live$',
    r'\.live\.json$',
    r'\.live\.yml$',
    r'^config/secrets\.',
    r'^config/credentials\.',
    r'^\.app/.*-PROD\.',
    r'^\.app/.*-PRODUCTION\.',
    r'^\.app/large_dump\.',
    r'^\.app/audit_log_',
    r'^\.app/embedding_cache\.bin$',
    r'^\.app/full_export\.',
    r'^\.app/user_data_backup\.',
]

# ── L2·内容 secret pattern ─────────────────────────────────────────────────
KEY_PATTERNS = [
    (r'sk-or-v1-[a-zA-Z0-9]{32,}', 'OpenRouter API key'),
    (r'sk-ant-api[0-9]{2}-[a-zA-Z0-9_\-]{32,}', 'Anthropic API key'),
    (r'(?<![a-zA-Z0-9])sk-[a-zA-Z0-9]{32,}(?![a-zA-Z0-9])', 'OpenAI-style API key'),
    (r'AIza[0-9A-Za-z_\-]{35}', 'Google API key'),
    (r'AKIA[0-9A-Z]{16}', 'AWS access key'),
    (r'ghp_[a-zA-Z0-9]{36,}', 'GitHub personal token'),
    (r'-----BEGIN [A-Z ]+ PRIVATE KEY-----', 'private key block'),
    (r'pbkdf2\$sha256,iter=\d+\$[A-Za-z0-9+/=_\-]{20,}\$[A-Za-z0-9+/=_\-]{20,}', 'pbkdf2 password hash'),
    (r'\$argon2id?\$v=\d+\$[mtp,=\d]+\$[A-Za-z0-9+/=]{8,}\$[A-Za-z0-9+/=]{16,}', 'argon2 password hash'),
    (r'fernet\$v1\$[A-Za-z0-9+/=_\-]{40,}', 'Fernet encrypted token'),
]

HOOKS_BLOCKLIST = ROOT / '.githooks' / 'business_name_blocklist.txt'

# 容许出现 PII pattern 的目录（fixture / hooks 自身定义 / docs 例子）
ALLOWED_PATTERN_PATHS = (
    'tests/fixtures/',
    '.githooks/',
    'scripts/scan_pii.py',
    'docs/legal/',  # 模板里可能有 placeholder
)


def get_files(staged_only: bool = False) -> list[str]:
    """tracked 文件清单·或仅 staged。"""
    if staged_only:
        cmd = ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM']
    else:
        cmd = ['git', 'ls-files']
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
    return [f for f in out.stdout.strip().splitlines() if f]


def L1_protected_paths(files: list[str]) -> list[tuple]:
    hits = []
    for f in files:
        for pat in PROTECTED_PATHS:
            if re.search(pat, f):
                hits.append(('L1', f, f'matches PROTECTED_PATHS /{pat}/'))
                break
    return hits


def L2_secret_content(files: list[str]) -> list[tuple]:
    hits = []
    for f in files:
        # 跳过自身 / 测试 / hook 定义
        if any(f.startswith(p) for p in ALLOWED_PATTERN_PATHS):
            continue
        path = ROOT / f
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 5_000_000:
            continue  # 大文件跳过 L2·走 L4
        try:
            content = path.read_text('utf-8', errors='ignore')
        except Exception:
            continue
        for pat, label in KEY_PATTERNS:
            for m in re.finditer(pat, content):
                # 占位符上下文 → skip
                ctx_start = max(0, m.start() - 60)
                ctx = content[ctx_start:m.end() + 30].lower()
                if any(skip in ctx for skip in (
                    'example', 'placeholder', 'fake', 'dummy', 'xxxxxx',
                    'redacted', 'your_key', 'your-key', '<api_key>', '<key>',
                    'test_key', 'sample',
                )):
                    continue
                line_no = content[:m.start()].count('\n') + 1
                hits.append(('L2', f, f'{label} at line {line_no}'))
                break  # 一个文件一个 pattern 报一次即可
    return hits


def L3_git_history() -> list[tuple]:
    """git log 扫历史 commit 的 blocklist 命中（慢·opt-in）。"""
    if not HOOKS_BLOCKLIST.exists():
        return []
    blocked = [w.strip() for w in HOOKS_BLOCKLIST.read_text('utf-8', errors='ignore').splitlines()
               if w.strip() and not w.startswith('#')]
    if not blocked:
        return []
    hits = []
    for term in blocked:
        out = subprocess.run(
            ['git', 'log', '--all', '--pretty=oneline', '-S', term, '--'],
            cwd=ROOT, capture_output=True, text=True
        )
        if out.stdout.strip():
            count = len(out.stdout.strip().splitlines())
            hits.append(('L3', '<git history>', f'"{term}" in {count} historical commits'))
    return hits


def L4_size_anomalies(files: list[str]) -> list[tuple]:
    hits = []
    for f in files:
        path = ROOT / f
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 5_000_000 and not f.startswith('.app/static/vendor/'):
            hits.append(('L4', f, f'tracked file > 5MB ({size:,} bytes) — likely data leak'))
    return hits


def fixture_contract_test(fixture_path: Path) -> int:
    """验证 scan_pii detect tests/fixtures/pii_47.txt 中所有 PII 行。"""
    if not fixture_path.is_file():
        print(f'fixture not found: {fixture_path}', file=sys.stderr)
        return 2
    lines = [l.strip() for l in fixture_path.read_text('utf-8').splitlines()
             if l.strip() and not l.startswith('#')]
    detected = 0
    missed = []
    for line in lines:
        # 1) 看 PROTECTED_PATHS
        is_path_hit = any(re.search(pat, line) for pat in PROTECTED_PATHS)
        # 2) 看 KEY_PATTERNS
        is_key_hit = any(re.search(pat, line) for pat, _ in KEY_PATTERNS)
        if is_path_hit or is_key_hit:
            detected += 1
        else:
            missed.append(line[:80])
    print(f'fixture: {detected}/{len(lines)} detected')
    if missed:
        print('missed:', file=sys.stderr)
        for m in missed:
            print(f'  - {m}', file=sys.stderr)
    return 0 if detected == len(lines) else 1


def main():
    p = argparse.ArgumentParser(description='Ome365 PII 4-layer scanner')
    p.add_argument('--history', action='store_true', help='+L3: scan git history (slow)')
    p.add_argument('--fixtures', action='store_true', help='contract test against tests/fixtures/pii_47.txt')
    p.add_argument('--staged-only', action='store_true', help='only scan staged files (pre-commit mode)')
    p.add_argument('--quiet', action='store_true')
    args = p.parse_args()

    if args.fixtures:
        return fixture_contract_test(ROOT / 'tests' / 'fixtures' / 'pii_47.txt')

    if not args.quiet:
        print(f'== Ome365 PII scan · root={ROOT} ==')

    files = get_files(staged_only=args.staged_only)
    if not args.quiet:
        print(f'   {"staged" if args.staged_only else "tracked"} files: {len(files)}')

    all_hits = []
    all_hits.extend(L1_protected_paths(files))
    all_hits.extend(L2_secret_content(files))
    all_hits.extend(L4_size_anomalies(files))
    if args.history:
        if not args.quiet:
            print('   scanning git history (this may take a minute)...')
        all_hits.extend(L3_git_history())

    if not all_hits:
        if not args.quiet:
            print('✓ 0 hits · clean')
        return 0

    for layer, f, msg in all_hits:
        print(f'  ✗ {layer} | {f} | {msg}', file=sys.stderr)
    layers_hit = sorted(set(h[0] for h in all_hits))
    print(f'\n→ {len(all_hits)} hits across {len(layers_hit)} layers ({", ".join(layers_hit)})', file=sys.stderr)
    return len(all_hits)


if __name__ == '__main__':
    sys.exit(main())
