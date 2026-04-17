#!/usr/bin/env python3
"""
TicNote 导出文件清洗工具
用法：python ticnote_clean.py <md文件路径> [--title 新标题] [--participants 人名1,人名2]

自动完成：
1. 去除 TicNote UI 残留（新功能/Shadow/编辑/总结/转录/思维导图/播客等）
2. 去除总结区的录音标题行、时间戳行、标签行
3. 去除"内容由 Shadow 生成"之后的重复内容
4. 去除转录区的 TicNote UI 残留
5. 添加 YAML frontmatter（如果没有）
6. 输出清洗后的文件（覆盖原文件，或 --out 指定新路径）
"""
import argparse, re, sys
from pathlib import Path

# TicNote UI 垃圾行关键词
UI_JUNK = [
    '新功能', 'TicNote Cloud', 'Shadow 2.0', '了解 Shadow',
    '思维导图', '顿悟', '深度研究', '播客', '.record',
    '内容由 Shadow 生成', 'Ask Shadow', '我知道了',
    '个人知识库', '共享知识库', '标准版', '剩余',
]

# 独占行的垃圾（exact match after strip）
UI_JUNK_EXACT = {'编辑', '总结', '转录', '/', '0:00'}


def is_junk_line(line):
    """判断一行是否是 TicNote UI 残留"""
    s = line.strip()
    if not s:
        return False  # 空行不算垃圾，由调用方处理
    if s in UI_JUNK_EXACT:
        return True
    if any(j in s for j in UI_JUNK):
        return True
    # 时间格式: "0:00 / 48:27" 或 "48:27" 或 "35:34"
    if re.match(r'^\d{1,2}:\d{2}(\s*/\s*\d{1,2}:\d{2})?$', s):
        return True
    # 播放倍速: "1.0X" "1.5X" "2.0X"
    if re.match(r'^\d+\.\d+X$', s):
        return True
    return False


def is_metadata_line(line, recording_title=""):
    """判断是否是总结区的元数据行（录音标题/时间戳/标签）"""
    s = line.strip()
    if not s:
        return False
    # 时间戳行: "2026-04-15 13:27:39|48m 28s|CaptainWyon"
    if re.match(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\|', s):
        return True
    # 录音标题行（和文件名相同或接近）
    if recording_title and s == recording_title:
        return True
    # 短标签行（如"成本管控"、"AI工具应用"——2-6字纯中文无标点，出现在出席人员之前）
    # 这个在 clean_summary 中通过上下文判断
    return False


def extract_recording_title(raw):
    """从原始内容中提取 TicNote 录音标题（用于过滤重复标题行）"""
    m = re.search(r'([^\n/]+)\.record', raw)
    if m:
        return m.group(1).strip()
    # 也从时间戳行前一行提取: "<录音标题>\n2026-04-15 13:27:39|..."
    m2 = re.search(r'\n([^\n]{4,80})\n\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\|', raw)
    if m2:
        return m2.group(1).strip()
    return ""


def clean_section(text, recording_title=""):
    """清洗一个 section 的内容"""
    lines = text.split('\n')
    result = []
    past_header = False  # 是否已经过了"出席人员"行

    for line in lines:
        # 跳过 UI 垃圾
        if is_junk_line(line):
            continue
        # 跳过 "内容由 Shadow 生成" 及之后的所有内容（重复区）
        if '内容由 Shadow 生成' in line:
            break
        # 录音标题行
        if not past_header and recording_title and line.strip() == recording_title:
            continue
        # 时间戳行
        if not past_header and is_metadata_line(line, recording_title):
            continue
        # 短标签行（在出席人员之前的2-8字纯文本行，无标点）
        s = line.strip()
        if not past_header and s and len(s) <= 12 and re.match(r'^[\u4e00-\u9fff\w]+$', s):
            # 可能是标签如"成本管控"、"AI工具应用"
            # 但也可能是正文，需要看上下文——如果紧跟在时间戳后面，大概率是标签
            continue

        if '出席人员' in line:
            past_header = True

        result.append(line)

    # 去尾空行
    while result and not result[-1].strip():
        result.pop()

    # 去重：TicNote 会把总结导出两遍（简版 + Cornell详版）
    # 策略：找到第一个 emoji 前缀的顶层 section header（会议概述/访谈基本信息/会议概要等）
    # 如果同一行又出现第二次，从第二次开始截断
    result = dedup_summary(result)

    # 合并连续空行（最多保留 1 个）
    collapsed = []
    blank = 0
    for line in result:
        if not line.strip():
            blank += 1
            if blank <= 1:
                collapsed.append(line)
        else:
            blank = 0
            collapsed.append(line)
    # 去尾空行
    while collapsed and not collapsed[-1].strip():
        collapsed.pop()

    return '\n'.join(collapsed)


# 匹配顶层 section header：emoji 前缀 + 概述/概要/基本信息
_TOP_SECTION_RE = re.compile(
    r'^([\U0001F300-\U0001FAFF\u2600-\u27BF])\s*(会议概述|访谈基本信息|会议概要|访谈概述|基本信息|概述)\s*$'
)


def dedup_summary(lines):
    """去除 TicNote 导出的重复总结块。

    TicNote 会在一份文件里导出两遍同一场会议的总结：
    前半是简版、后半是详版，两段都以同一个 emoji 前缀的顶层 section
    开头（如 "📝 会议概述" / "📋会议概述" / "📝访谈基本信息"）。

    这里定位第一个顶层 section header，在它**第二次**出现的位置截断。
    """
    first_header = None
    first_idx = None
    for i, line in enumerate(lines):
        s = line.strip()
        if _TOP_SECTION_RE.match(s):
            if first_header is None:
                first_header = s
                first_idx = i
            elif s == first_header and i > first_idx:
                # 截断到第二次出现的前一行
                trimmed = lines[:i]
                # 去尾空行
                while trimmed and not trimmed[-1].strip():
                    trimmed.pop()
                return trimmed
    return lines


def clean_transcript(text):
    """清洗转录区：只保留 SPEAKER 开头的内容"""
    lines = text.split('\n')
    result = []
    started = False
    for line in lines:
        if not started:
            if line.startswith('SPEAKER_'):
                started = True
                result.append(line)
            continue
        # 跳过尾部垃圾
        if '内容由 Shadow 生成' in line:
            break
        result.append(line)

    while result and not result[-1].strip():
        result.pop()

    return '\n'.join(result)


def parse_duration(raw):
    """从原始内容中提取录音时长"""
    m = re.search(r'\d{4}-\d{2}-\d{2}\s[\d:]+\|(.+?)\|', raw[:800])
    if m:
        return m.group(1).strip()
    return ""


def main():
    parser = argparse.ArgumentParser(description="TicNote 导出文件清洗")
    parser.add_argument("files", nargs="+", help="要清洗的 .md 文件路径")
    parser.add_argument("--title", help="覆盖标题（用于文件重命名）")
    parser.add_argument("--participants", help="参与者列表，逗号分隔")
    parser.add_argument("--out", help="输出路径（默认覆盖原文件）")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    args = parser.parse_args()

    for fpath in args.files:
        fp = Path(fpath)
        if not fp.exists():
            print(f"❌ 文件不存在: {fp}", file=sys.stderr)
            continue

        raw = fp.read_text("utf-8")
        recording_title = extract_recording_title(raw)
        duration = parse_duration(raw)

        # 分离总结和转录
        parts = re.split(r'\n---\n+## 转录\n', raw)
        summary_raw = parts[0]
        transcript_raw = parts[1] if len(parts) > 1 else ""

        # 检查是否已有 frontmatter
        has_fm = summary_raw.strip().startswith('---\n')
        if has_fm:
            # 去掉 frontmatter 再清洗
            fm_end = summary_raw.index('---', 4) + 3
            frontmatter_block = summary_raw[:fm_end]
            summary_body = summary_raw[fm_end:]
        else:
            frontmatter_block = None
            summary_body = summary_raw

        # 去掉原始头部（# 标题行 + 导出时间等）
        header_lines = []
        body_start = 0
        lines = summary_body.split('\n')
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith('## 总结'):
                body_start = i + 1
                break
            # 保留头部元数据行
            if s.startswith('# ') or s.startswith('导出时间') or s.startswith('来源文件夹') or s.startswith('URL:') or s == '---' or not s:
                header_lines.append(line)
                body_start = i + 1

        summary_content = '\n'.join(lines[body_start:])
        clean_summary = clean_section(summary_content, recording_title)

        clean_trans = clean_transcript(transcript_raw) if transcript_raw else ""

        # 提取标题和日期
        stem = fp.stem
        title = args.title or stem
        date_m = re.search(r'(\d{4}-\d{2}-\d{2})', stem)
        date_str = date_m.group(1) if date_m else ""
        participants = args.participants.split(',') if args.participants else []

        # 构建输出
        out_parts = []

        # Frontmatter
        if not has_fm:
            fm_lines = ['---']
            fm_lines.append(f'title: {title}')
            if date_str:
                fm_lines.append(f'date: {date_str}')
            fm_lines.append('source: TicNote')
            if participants:
                fm_lines.append(f'participants: [{", ".join(participants)}]')
            if duration:
                fm_lines.append(f'duration: {duration}')
            fm_lines.append('---')
            out_parts.append('\n'.join(fm_lines))
        else:
            out_parts.append(frontmatter_block)

        out_parts.append('')
        out_parts.append(f'# {title}')
        out_parts.append('')
        # Keep minimal metadata
        if date_str:
            from datetime import datetime
            out_parts.append(f'导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        out_parts.append('')
        out_parts.append('---')
        out_parts.append('')
        out_parts.append('## 总结')
        out_parts.append('')
        out_parts.append(clean_summary)

        if clean_trans:
            out_parts.append('')
            out_parts.append('---')
            out_parts.append('')
            out_parts.append('## 转录')
            out_parts.append('')
            out_parts.append(clean_trans)

        out_parts.append('')  # trailing newline

        output = '\n'.join(out_parts)

        if args.dry_run:
            print(f"{'=' * 40}")
            print(f"📄 {fp.name} → {len(output):,} bytes (was {len(raw):,})")
            print(output[:500])
            print("...")
        else:
            out_path = Path(args.out) if args.out else fp
            out_path.write_text(output, "utf-8")
            print(f"✅ {fp.name} → {out_path.name} ({len(output):,} B, was {len(raw):,} B)")


if __name__ == "__main__":
    main()
