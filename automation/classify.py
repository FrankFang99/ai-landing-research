#!/usr/bin/env python3
"""
automation/classify.py
======================
读 automation/output/candidates.json，
用 LLM 判断每条是否值得入库 → 归到 8 行业之一 → 生成 Markdown 案例。

对带 signal_type 的源（job_signal / startup_signal / industry_trend），
额外走 PROMPT_SIGNAL_SYSTEM 判断「求职/创业信号强度」，结果写到
automation/output/signals.json。

输出：
  - automation/output/new_cases.json    新增案例元数据（原有）
  - automation/output/_card_*.md        卡片正文（原有）
  - automation/output/skipped.json      被 LLM 拒绝的（原有）
  - automation/output/signals.json      周更求职/创业信号（新增，2026-06-22）
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from _env import load_env
load_env()

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "automation" / "sources.yaml"
OUT = ROOT / "automation" / "output"
CANDIDATES = OUT / "candidates.json"
NEW_CASES = OUT / "new_cases.json"
SKIPPED = OUT / "skipped.json"
SIGNALS = OUT / "signals.json"   # 新增：求职/创业信号输出

CN_TZ = timezone(timedelta(hours=8))

# 8 行业 + 4 类资产目录
INDUSTRIES = ["金融", "医疗", "零售", "教育", "制造", "政务", "文娱", "物流"]
ASSET_DIRS = {
    "案例": "06_案例库/成功案例_v2",
    "案例-成功": "06_案例库/成功案例_v2",
    "案例-失败": "06_案例库/失败案例_v2",
    "行业洞察": "01_行业地图",
}

# 信号类型常量（与 sources.yaml signal_type 字段对应）
SIGNAL_TYPES = {"job_signal", "startup_signal", "industry_trend"}


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


# ============================================================
# 新增：求职/创业信号分类 prompt（2026-06-22 启用）
# ============================================================
PROMPT_SIGNAL_SYSTEM = """你是「求职 + 创业」双线信号识别助理。

用户背景：求职方向是 AI 产品经理 / AI 应用 PM；正在评估 AI 方向创业机会。
用户场景：想知道这条信息对求职或创业是否有信号价值。

【你的任务】
判断这条信息是否包含「求职」或「创业」维度的有效信号，并给信号强度打分（1-5）。

【信号类型】（三选一）
- "job_market"：招聘动向（岗位、行业、薪资、地点、招聘方画像）
- "startup_opportunity"：创业机会（融资、PMF、上下游缺口、可复制商业模式）
- "industry_trend"：行业趋势（监管变化、模型能力跃升、格局变动，影响求职+创业）

【信号强度 1-5】
- 5：直接相关 + 强时效 + 高信号密度（必看）
- 4：相关 + 中等时效（值得看）
- 3：间接相关（参考）
- 2：弱相关（可忽略）
- 1：几乎无关（兜底）

【拒绝标准】
- 标题党 / 营销稿 / 没有实质内容
- 与 AI / 大模型行业无关的招聘信息（如传统行业普工）
- 内容太短无法判断
- 重复信号

【输出 JSON】（严格遵守，不要任何额外文字）
{
  "accept": true|false,
  "signal_type": "job_market|startup_opportunity|industry_trend|null",
  "signal_strength": 1-5,
  "reason": "判断理由（一句话，重点说为什么是这个强度）",
  "summary": "100 字以内的中文摘要",
  "tags": ["tag1", "tag2"]
}"""


PROMPT_SIGNAL_USER = """【信号类型预判】
{signal_type_hint}

【标题】
{title}

【链接】
{url}

【来源】
{source}

【原文摘要】
{summary}

请判断并返回 JSON。"""


def classify_one(client, model: str, item: dict) -> dict:
    """调用 LLM 分类单条（原有 8 行业路径）。"""
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


def classify_signal_one(client, model: str, item: dict, signal_type_hint: str) -> dict:
    """调用 LLM 判断求职/创业信号（新增路径，2026-06-22）。"""
    user = PROMPT_SIGNAL_USER.format(
        signal_type_hint=signal_type_hint,
        title=item.get("title", ""),
        url=item.get("url", ""),
        source=item.get("source", ""),
        summary=item.get("summary", "") or "(无摘要)",
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PROMPT_SIGNAL_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        text = resp.choices[0].message.content.strip()
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
        SIGNALS.write_text("[]", encoding="utf-8")
        return 0

    client, model = llm_client()
    log(f"使用模型：{model}")
    log(f"待分类：{len(cands)} 条")

    new_cases: list[dict] = []
    skipped: list[dict] = []
    signals: list[dict] = []
    today = datetime.now(CN_TZ).strftime("%Y-%m-%d")

    for i, item in enumerate(cands, 1):
        log(f"[{i}/{len(cands)}] {item.get('title', '')[:50]}...")
        signal_type_hint = item.get("signal_type", "")

        # 新增：求职/创业信号路径（2026-06-22）
        # signal 类条目走 PROMPT_SIGNAL_SYSTEM，结果写 signals.json，**不进 8 行业分类**
        if signal_type_hint in SIGNAL_TYPES:
            cls_sig = classify_signal_one(client, model, item, signal_type_hint)
            if not cls_sig.get("accept"):
                skipped.append({
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "reason": f"[signal] {cls_sig.get('reason', '未知')}",
                })
                continue
            strength = cls_sig.get("signal_strength", 1)
            try:
                strength = int(strength)
            except Exception:
                strength = 1
            strength = max(1, min(5, strength))
            signals.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "signal_type_hint": signal_type_hint,
                "signal_type": cls_sig.get("signal_type") or signal_type_hint,
                "signal_strength": strength,
                "summary": cls_sig.get("summary", ""),
                "tags": cls_sig.get("tags", []),
                "source": item.get("source"),
                "date": today,
                "reason": cls_sig.get("reason", ""),
                "fingerprint": item.get("fingerprint") or "",
            })
            log(f"  ✓ signal[{signal_type_hint}|s={strength}] → signals.json")
            continue

        # 原有路径：8 行业 + 案例 / 行业洞察
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
    SIGNALS.write_text(json.dumps(signals, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    log(f"完成：{len(new_cases)} 条案例入库，{len(signals)} 条信号，{len(skipped)} 条跳过")
    return 0


if __name__ == "__main__":
    sys.exit(main())