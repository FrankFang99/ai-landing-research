#!/usr/bin/env python3
"""
automation/build_index.py
========================
读 automation/output/new_cases.json + signals.json，
合并到 docs/assets/data.js 的 latest 字段，同时把求职/创业信号
写入 09_求职信号/本周信号/ 并注入 PORTFOLIO.md 的标记块。

幂等：重复跑不会产生重复条目（用 fingerprint 去重）。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _env import load_env
load_env()

ROOT = Path(__file__).resolve().parents[1]
NEW_CASES = ROOT / "automation" / "output" / "new_cases.json"
SIGNALS_JSON = ROOT / "automation" / "output" / "signals.json"
DATA_JS = ROOT / "docs" / "assets" / "data.js"
PORTFOLIO = ROOT / "PORTFOLIO.md"
SIGNAL_WEEKLY_DIR = ROOT / "09_求职信号" / "本周信号"

CN_TZ = timezone(timedelta(hours=8))

SIGNAL_BLOCK_START = "<!-- AUTO:WEEKLY_SIGNAL_START -->"
SIGNAL_BLOCK_END = "<!-- AUTO:WEEKLY_SIGNAL_END -->"


def now_cn() -> str:
    # ISO8601 with +08:00 offset
    return datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def today_cn() -> str:
    return datetime.now(CN_TZ).strftime("%Y-%m-%d")


def log(*args):
    print(f"[build_index {now_cn()}]", *args, flush=True)


# ============================================================
# 原有：data.js 维护（保持向后兼容）
# ============================================================
def update_data_js(new_cases: list[dict], signals: list[dict]) -> None:
    """维护 docs/assets/data.js：latest 字段 + 新增 signals 字段。"""
    if not DATA_JS.exists():
        log("data.js 不存在，跳过")
        return

    src = DATA_JS.read_text(encoding="utf-8")
    m = re.search(r"^window\.SITE_DATA\s*=\s*\{", src, re.MULTILINE)
    if not m:
        log("data.js 解析失败：找不到赋值行")
        return
    brace_start = m.end() - 1
    depth = 0
    end = -1
    in_str = False
    esc = False
    for i in range(brace_start, len(src)):
        ch = src[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        log("data.js 解析失败：花括号未闭合")
        return
    data = json.loads(src[brace_start : end + 1])

    # latest 字段：原 8 行业案例
    existing = data.get("latest", [])
    existing_fps = {c.get("fingerprint") for c in existing if c.get("fingerprint")}
    added = 0
    for nc in new_cases:
        fp = nc.get("fingerprint")
        if fp and fp in existing_fps:
            continue
        existing.append({
            "title": nc.get("title", ""),
            "url": nc.get("url", ""),
            "industry": nc.get("industry", "未分类"),
            "summary": nc.get("summary", ""),
            "source": nc.get("source", ""),
            "date": nc.get("date", ""),
            "fingerprint": fp,
        })
        existing_fps.add(fp)
        added += 1

    existing.sort(key=lambda x: x.get("date", ""), reverse=True)
    existing = existing[:24]

    # signals 字段：求职/创业信号（新增 2026-06-22）
    existing_signals = data.get("signals", [])
    sig_fps = {s.get("fingerprint") for s in existing_signals if s.get("fingerprint")}
    sig_added = 0
    for s in signals:
        fp = s.get("fingerprint")
        if fp and fp in sig_fps:
            continue
        existing_signals.append({
            "title": s.get("title", ""),
            "url": s.get("url", ""),
            "signal_type": s.get("signal_type", ""),
            "signal_strength": s.get("signal_strength", 1),
            "summary": s.get("summary", ""),
            "source": s.get("source", ""),
            "date": s.get("date", ""),
            "fingerprint": fp,
        })
        sig_fps.add(fp)
        sig_added += 1

    existing_signals.sort(
        key=lambda x: (x.get("signal_strength", 0), x.get("date", "")),
        reverse=True,
    )
    existing_signals = existing_signals[:50]   # 信号保留多一些，求职/创业时效性强

    data["latest"] = existing
    data["signals"] = existing_signals
    data["generated_at"] = now_cn()
    if existing:
        data["stats"]["last_update"] = existing[0].get("date", "")
    data["stats"]["total_cases"] = len(existing)
    data["stats"]["total_signals"] = len(existing_signals)

    new_js = f"""/* docs/assets/data.js
 * 自动由 automation/build_index.py 生成，请勿手动编辑
 * 格式：window.SITE_DATA = {{ generated_at, industries, latest, signals, stats }}
 */
window.SITE_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};
"""
    DATA_JS.write_text(new_js, encoding="utf-8")
    log(f"写入 data.js：案例新增 {added} 条 / 信号新增 {sig_added} 条")


# ============================================================
# 新增：09_求职信号/本周信号/YYYYMMDD.md 维护
# ============================================================
def _fmt_signal_line(s: dict) -> str:
    """单条信号渲染成 Markdown bullet。"""
    strength = s.get("signal_strength", 1)
    type_ = s.get("signal_type", "未分类")
    type_emoji = {
        "job_market": "💼 招聘",
        "startup_opportunity": "🚀 创业",
        "industry_trend": "📈 趋势",
    }.get(type_, type_)
    stars = "★" * strength + "☆" * (5 - strength)
    title = s.get("title", "(无标题)")
    url = s.get("url", "")
    summary = s.get("summary", "")
    source = s.get("source", "")
    reason = s.get("reason", "")
    line = f"- {stars} **{type_emoji}** [{title}]({url})"
    if summary:
        line += f"\n  - {summary}"
    if reason:
        line += f"\n  - _LLM 判断依据：{reason}_"
    if source:
        line += f"\n  - 来源：{source}"
    return line


def write_signals_weekly(signals: list[dict]) -> None:
    """把本周信号写到 09_求职信号/本周信号/本周信号_YYYYMMDD.md。"""
    SIGNAL_WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    today = today_cn()
    out_path = SIGNAL_WEEKLY_DIR / f"本周信号_{today.replace('-', '')}.md"

    if not signals:
        out_path.write_text(
            f"# 本周信号 · {today}\n\n> 本周无新信号（周更 cron 已跑完）。\n",
            encoding="utf-8",
        )
        log(f"信号为空，写占位 → {out_path.relative_to(ROOT)}")
        return

    by_type: dict[str, list[dict]] = {"job_market": [], "startup_opportunity": [], "industry_trend": []}
    for s in signals:
        t = s.get("signal_type") or "industry_trend"
        by_type.setdefault(t, []).append(s)

    lines: list[str] = [f"# 本周信号 · {today}", ""]
    lines.append(f"> 共 {len(signals)} 条信号 · 自动由周更 cron 写入")
    lines.append("")

    section_titles = {
        "job_market": "💼 招聘动向（求职用）",
        "startup_opportunity": "🚀 创业信号（创业用）",
        "industry_trend": "📈 行业趋势（求职+创业都看）",
    }
    for t in ("job_market", "startup_opportunity", "industry_trend"):
        items = by_type.get(t, [])
        if not items:
            continue
        items.sort(key=lambda x: x.get("signal_strength", 0), reverse=True)
        lines.append(f"## {section_titles[t]}（{len(items)} 条）")
        lines.append("")
        for s in items:
            lines.append(_fmt_signal_line(s))
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    log(f"写入本周信号 → {out_path.relative_to(ROOT)}（{len(signals)} 条）")


# ============================================================
# 新增：PORTFOLIO.md 自动注入（标记块保护人工编辑）
# ============================================================
def _build_portfolio_block(signals: list[dict], today: str, prev_block: str = "") -> str:
    """生成 PORTFOLIO.md 标记块内的内容（Top 3 + 简表）。

    signals 为空时：保留 prev_block 主体，只更新日期戳（避免覆盖历史信号）。
    """
    if not signals:
        # 空信号策略：保留旧内容 + 加一行「本次 cron 已跑过但无新信号」提示
        # 提取 prev_block 的第一行（通常是日期戳）替换为今天
        if prev_block:
            # 移除 prev 里旧的"最后更新：YYYY-MM-DD..."行，再插入新的
            import re as _re
            cleaned = _re.sub(r"^_最后更新：\d{4}-\d{2}-\d{2}[^\n]*\n", "", prev_block, flags=_re.MULTILINE).strip()
        else:
            cleaned = "> 暂无本周信号 —— 周一 09:00 (UTC+8) 周更 cron 跑完后会自动更新。"
        return f"_最后更新：{today} · 本次 cron 跑过但本周无新信号_\n\n{cleaned}"

    by_type: dict[str, list[dict]] = {"job_market": [], "startup_opportunity": [], "industry_trend": []}
    for s in signals:
        t = s.get("signal_type") or "industry_trend"
        by_type.setdefault(t, []).append(s)
    for t in by_type:
        by_type[t].sort(key=lambda x: x.get("signal_strength", 0), reverse=True)

    lines: list[str] = []
    lines.append(f"_最后更新：{today} · 本周共 {len(signals)} 条信号_")
    lines.append("")
    sections = [
        ("💼 本周招聘动向（Top 3）", by_type.get("job_market", []), "job_market"),
        ("🚀 本周创业信号（Top 3）", by_type.get("startup_opportunity", []), "startup_opportunity"),
        ("📈 本周行业趋势（Top 3）", by_type.get("industry_trend", []), "industry_trend"),
    ]
    for title, items, _ in sections:
        lines.append(f"### {title}")
        lines.append("")
        if not items:
            lines.append("> 本周无相关信号。")
            lines.append("")
            continue
        for s in items[:3]:
            strength = s.get("signal_strength", 1)
            stars = "★" * strength + "☆" * (5 - strength)
            lines.append(f"- {stars} [{s.get('title', '')}]({s.get('url', '')})")
            if s.get("summary"):
                lines.append(f"  - {s['summary']}")
        lines.append("")

    lines.append("---")
    lines.append(f"_完整 {len(signals)} 条信号见 [`09_求职信号/本周信号/本周信号_{today.replace('-', '')}.md`](09_求职信号/本周信号/)_")
    return "\n".join(lines)


def inject_portfolio_signal(signals: list[dict]) -> None:
    """替换 PORTFOLIO.md 中 AUTO:WEEKLY_SIGNAL 标记块之间的内容。

    空信号策略：保留旧内容主体，只刷新日期戳，避免覆盖历史信号。
    """
    if not PORTFOLIO.exists():
        log("PORTFOLIO.md 不存在，跳过注入")
        return

    src = PORTFOLIO.read_text(encoding="utf-8")
    start = src.find(SIGNAL_BLOCK_START)
    end = src.find(SIGNAL_BLOCK_END)
    if start < 0 or end < 0 or end < start:
        log(f"PORTFOLIO.md 找不到 {SIGNAL_BLOCK_START}/{SIGNAL_BLOCK_END} 标记块，跳过注入")
        return

    today = today_cn()
    prev_block = src[start + len(SIGNAL_BLOCK_START) : end].strip()
    new_block = _build_portfolio_block(signals, today, prev_block=prev_block)
    # 保留标记行本身
    before = src[: start + len(SIGNAL_BLOCK_START)]
    after = src[end:]
    new_src = f"{before}\n{new_block}\n{after}"
    PORTFOLIO.write_text(new_src, encoding="utf-8")
    log(f"PORTFOLIO.md 注入完成（{len(signals)} 条信号）")


def main() -> int:
    # 读新案例
    new_cases: list[dict] = []
    if NEW_CASES.exists():
        try:
            new_cases = json.loads(NEW_CASES.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"new_cases.json 读取失败: {e}")

    # 读新信号
    signals: list[dict] = []
    if SIGNALS_JSON.exists():
        try:
            signals = json.loads(SIGNALS_JSON.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"signals.json 读取失败: {e}")

    # 1. data.js 维护
    update_data_js(new_cases, signals)
    # 2. 本周信号文件
    write_signals_weekly(signals)
    # 3. PORTFOLIO.md 注入
    inject_portfolio_signal(signals)

    log(f"build_index 完成：案例 {len(new_cases)} / 信号 {len(signals)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())