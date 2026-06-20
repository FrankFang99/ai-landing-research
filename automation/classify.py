#!/usr/bin/env python3
"""
automation/classify.py
======================
读 automation/output/candidates.json，
用 LLM 判断每条是否值得入库 → 归到 8 行业之一 → 生成 Markdown 案例。
输出：
  - automation/output/new_cases.json    新增案例元数据
  - automation/output/_card_*.md        卡片正文（待 build_index 整合）
  - automation/output/skipped.json      被 LLM 拒绝的（带原因）
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "automation" / "sources.yaml"
OUT = ROOT / "automation" / "output"
CANDIDATES = OUT / "candidates.json"
NEW_CASES = OUT / "new_cases.json"
SKIPPED = OUT / "skipped.json"

CN_TZ = timezone(timedelta(hours=8))

# 8 行业 + 4 类资产目录
INDUSTRIES = ["金融", "医疗", "零售", "教育", "制造", "政务", "文娱", "物流"]
ASSET_DIRS = {
    "案例": "06_案例库/成功案例_v2",
    "案例-成功": "06_案例库/成功案例_v2",
    "案例-失败": "06_案例库/失败案例_v2",
    "行业洞察": "01_行业地图",
}


def now_cn() -> str:
    # ISO8601 with +08:00 offset
    return datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def log(*args):
    print(f"[classify {now_cn()}]", *args, flush=True)


def llm_client():
    """OpenAI 协议客户端（兼容 OpenAI / DeepSeek / 月之暗面 / Ollama）。"""
    try:
        from openai import OpenAI
    except ImportError:
        log("缺 openai 包，pip install -r automation/requirements.txt")
        sys.exit(1)
    api_key = os.environ.get("LLM_API_KEY", "ollama")
    base_url = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
    model = os.environ.get("LLM_MODEL", "qwen2.5:7b")
    return OpenAI(api_key=api_key, base_url=base_url), model


PROMPT_SYSTEM = """你是 AI 项目落地研究助理。给定一条候选信息，判断它是否值得入库到"AI 项目落地研究"知识库。

【入库标准】
- 主题明确是 AI / 大模型 / 机器学习在某个具体行业的应用、案例、解决方案、产品落地。
- 信息可验证（公开来源、有公司名/产品名/场景/数据）。
- 非营销软文、非求职招聘、非纯学术论文（除非有强落地信号）。

【拒绝标准】
- 标题党 / 营销稿 / 没有实质内容
- 与 AI 行业落地无关
- 重复信息
- 内容太短无法判断

【输出 JSON 格式】（严格遵守，不要任何额外文字）
{
  "accept": true|false,
  "reason": "判断理由（一句话）",
  "industry": "金融|医疗|零售|教育|制造|政务|文娱|物流|null",
  "asset_type": "案例-成功|案例-失败|行业洞察|null",
  "summary": "100 字以内的中文摘要",
  "tags": ["tag1", "tag2"]
}"""


PROMPT_USER = """【标题】
{title}

【链接】
{url}

【来源】
{source}

【原文摘要】
{summary}

请判断并返回 JSON。"""


def classify_one(client, model: str, item: dict) -> dict:
    """调用 LLM 分类单条。"""
    user = PROMPT_USER.format(
        title=item.get("title", ""),
        url=item.get("url", ""),
        source=item.get("source", ""),
        summary=item.get("summary", "") or "(无摘要)",
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        text = resp.choices[0].message.content.strip()
        # 尝试提取 JSON
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {"accept": False, "reason": f"LLM 输出无 JSON: {text[:100]}"}
        data = json.loads(m.group(0))
        return data
    except Exception as e:
        return {"accept": False, "reason": f"LLM 调用失败: {e}"}


def to_markdown_card(item: dict, classification: dict, today: str) -> str:
    """生成单条案例的 Markdown 卡片正文。"""
    title = item.get("title", "(无标题)")
    url = item.get("url", "")
    industry = classification.get("industry") or "未分类"
    summary = classification.get("summary", "")
    tags = classification.get("tags") or []
    source = item.get("source", "")
    reason = classification.get("reason", "")

    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:80]
    tags_line = " ".join([f"`{t}`" for t in tags])

    return f"""# {title}

- **行业**：{industry}
- **来源**：[{source}]({url})
- **入库日期**：{today}
- **标签**：{tags_line or "(无)"}

## 摘要

{summary}

## LLM 判断依据

{reason}

## 原文链接

[{url}]({url})
"""


def safe_filename(name: str, fp: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|\s]', "_", name)[:60]
    return f"{safe}_{fp}.md"


def main() -> int:
    if not CANDIDATES.exists():
        log("无 candidates.json，跳过")
        return 0
    cands = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    if not cands:
        log("无候选，跳过")
        NEW_CASES.write_text("[]", encoding="utf-8")
        SKIPPED.write_text("[]", encoding="utf-8")
        return 0

    client, model = llm_client()
    log(f"使用模型：{model}")
    log(f"待分类：{len(cands)} 条")

    new_cases: list[dict] = []
    skipped: list[dict] = []
    today = datetime.now(CN_TZ).strftime("%Y-%m-%d")

    for i, item in enumerate(cands, 1):
        log(f"[{i}/{len(cands)}] {item.get('title', '')[:50]}...")
        cls = classify_one(client, model, item)
        if not cls.get("accept"):
            skipped.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "reason": cls.get("reason", "未知"),
            })
            continue

        industry = cls.get("industry") or "未分类"
        asset_type = cls.get("asset_type") or "案例-成功"
        # 校验 industry 在 8 大类里
        if industry not in INDUSTRIES:
            industry = "未分类"
        # 校验 asset_type
        if asset_type not in ASSET_DIRS:
            asset_type = "案例-成功"

        fp = item.get("fingerprint") or "x"
        target_dir = ASSET_DIRS[asset_type]
        fname = safe_filename(item.get("title", ""), fp)
        target_path = ROOT / target_dir / fname

        md = to_markdown_card(item, cls, today)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(md, encoding="utf-8")

        new_cases.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "industry": industry,
            "asset_type": asset_type,
            "summary": cls.get("summary", ""),
            "tags": cls.get("tags", []),
            "source": item.get("source"),
            "date": today,
            "file": str(target_path.relative_to(ROOT)),
            "fingerprint": fp,
        })
        log(f"  ✓ 入库 → {target_path.relative_to(ROOT)}")

    NEW_CASES.write_text(json.dumps(new_cases, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    SKIPPED.write_text(json.dumps(skipped, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    log(f"完成：{len(new_cases)} 条入库，{len(skipped)} 条跳过")
    return 0


if __name__ == "__main__":
    sys.exit(main())