#!/usr/bin/env python3
"""
automation/build_index.py
=========================
读 automation/output/new_cases.json，
合并到 docs/assets/data.js 的 latest 字段。

幂等：重复跑不会产生重复条目（用 fingerprint 去重）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_CASES = ROOT / "automation" / "output" / "new_cases.json"
DATA_JS = ROOT / "docs" / "assets" / "data.js"

CN_TZ = timezone(timedelta(hours=8))


def now_cn() -> str:
    # ISO8601 with +08:00 offset
    return datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def log(*args):
    print(f"[build_index {now_cn()}]", *args, flush=True)


def main() -> int:
    if not DATA_JS.exists():
        log("data.js 不存在，跳过")
        return 1

    src = DATA_JS.read_text(encoding="utf-8")

    # 解析已有数据。data.js 形如：
    #   /* 注释，可能含花括号/分号 */
    #   window.SITE_DATA = { ... };
    # 用 sentinel 法：从第一个 "window.SITE_DATA" 起，括号配对找完整 JSON 对象
    import re
    sentinel = "window.SITE_DATA"
    idx = src.find(sentinel)
    if idx < 0:
        log("data.js 解析失败：找不到 window.SITE_DATA")
        return 1
    brace_start = src.find("{", idx)
    if brace_start < 0:
        log("data.js 解析失败：找不到 {")
        return 1
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
        return 1
    data = json.loads(src[brace_start : end + 1])

    # 读新案例
    new_cases: list[dict] = []
    if NEW_CASES.exists():
        try:
            new_cases = json.loads(NEW_CASES.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"new_cases.json 读取失败: {e}")

    # 用 fingerprint 去重 + 拼接 GitHub 链接
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

    # 按日期倒序，最多保留 24 条
    existing.sort(key=lambda x: x.get("date", ""), reverse=True)
    existing = existing[:24]

    data["latest"] = existing
    data["generated_at"] = now_cn()
    if existing:
        data["stats"]["last_update"] = existing[0].get("date", "")
    # 总案例数 = latest 条数（简化，精确需要扫描目录）
    data["stats"]["total_cases"] = len(existing)

    new_js = f"""/* docs/assets/data.js
 * 自动由 automation/build_index.py 生成，请勿手动编辑
 * 格式：window.SITE_DATA = {{ generated_at, industries, latest, stats }}
 */
window.SITE_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};
"""
    DATA_JS.write_text(new_js, encoding="utf-8")
    log(f"写入 data.js：新增 {added} 条，累计 {len(existing)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())