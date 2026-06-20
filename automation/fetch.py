#!/usr/bin/env python3
"""
automation/fetch.py
====================
从 automation/sources.yaml 拉取过去 N 天的新内容，
写到 automation/output/candidates.json，供 classify.py 消费。

支持 source type：
  - web:        公开网页（用 web_search 模拟或直接 GET）
  - github_repo: GitHub 仓库（REST API）
  - rss:        标准 RSS / Atom feed（feedparser）
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests
import yaml
from dateutil import parser as dtp

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "automation" / "sources.yaml"
OUT_DIR = ROOT / "automation" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "candidates.json"
SEEN_FILE = OUT_DIR / "seen.json"   # 跨周去重

CN_TZ = timezone(timedelta(hours=8))


def now_cn() -> str:
    return datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S%08:00")


def log(*args):
    print(f"[fetch {now_cn()}]", *args, flush=True)


def load_sources() -> dict:
    with open(SOURCES, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2),
                         encoding="utf-8")


def fingerprint(title: str, url: str) -> str:
    return hashlib.sha1(f"{title.strip()}|{url.strip()}".encode("utf-8")).hexdigest()[:16]


def passes_filter(title: str, summary: str, exclude_kw: list[str]) -> bool:
    text = f"{title} {summary}".lower()
    return not any(kw.lower() in text for kw in exclude_kw)


# ---------- fetchers ----------
def fetch_web(src: dict, window_days: int) -> list[dict]:
    """抓公开网页 —— 简化策略：抓页面 → 提取标题/链接。

    真实生产环境可以接 web_search API（Bing / SerpAPI / 百度），这里先做
    'GET 页面 + 提取标题链接' 的最小可用版本。
    """
    url = src["url"]
    keywords = src.get("keywords", [])
    items: list[dict] = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ai-landing-bot/1.0; +https://github.com/FrankFang99/ai-landing-research)"
        }
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        # 提取 <a href="...">title</a> 形态的链接
        text = r.text
        # 简单正则：抓含中文标题的链接块
        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]{6,200})</a>', text)
        seen_local: set[str] = set()
        for href, title in links:
            # 过滤：相对链接补全、非站内 / 锚点跳过
            if href.startswith("#") or href.startswith("javascript:"):
                continue
            if href.startswith("/"):
                from urllib.parse import urljoin
                href = urljoin(url, href)
            if not href.startswith("http"):
                continue
            title = re.sub(r"\s+", " ", title).strip()
            if not title or len(title) < 6:
                continue
            # 关键词命中优先
            if keywords and not any(kw in title for kw in keywords):
                continue
            if href in seen_local:
                continue
            seen_local.add(href)
            items.append({
                "title": title,
                "url": href,
                "summary": "",
                "source": src["name"],
                "source_type": "web",
                "fetched_at": now_cn(),
            })
            if len(items) >= src.get("max", 20):
                break
    except Exception as e:
        log(f"[web] {src['name']} 失败：{e}")
    return items


def fetch_github_repo(src: dict, window_days: int) -> list[dict]:
    """抓 GitHub 仓库的 releases / commits / issues。"""
    url = src["url"].rstrip("/")
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)", url)
    if not m:
        return []
    owner, repo = m.group(1), m.group(2)
    track = src.get("track", "releases")
    api = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    items: list[dict] = []
    try:
        cutoff = datetime.now(CN_TZ) - timedelta(days=window_days)
        if track == "releases":
            r = requests.get(f"{api}/releases?per_page=20", headers=headers, timeout=20)
            r.raise_for_status()
            for rel in r.json():
                published = dtp.parse(rel.get("published_at") or rel.get("created_at"))
                if published.tzinfo is None:
                    published = published.replace(tzinfo=CN_TZ)
                if published < cutoff:
                    continue
                items.append({
                    "title": f"[{owner}/{repo}] {rel.get('name') or rel['tag_name']}",
                    "url": rel.get("html_url") or url,
                    "summary": (rel.get("body") or "")[:500],
                    "source": src["name"],
                    "source_type": "github_repo",
                    "fetched_at": now_cn(),
                })
        elif track == "commits":
            r = requests.get(f"{api}/commits?per_page=20", headers=headers, timeout=20)
            r.raise_for_status()
            for c in r.json():
                msg = (c.get("commit", {}).get("message") or "").splitlines()[0]
                items.append({
                    "title": f"[{owner}/{repo}] commit: {msg[:120]}",
                    "url": c.get("html_url") or url,
                    "summary": "",
                    "source": src["name"],
                    "source_type": "github_repo",
                    "fetched_at": now_cn(),
                })
    except Exception as e:
        log(f"[github_repo] {src['name']} 失败：{e}")
    return items


def fetch_rss(src: dict, window_days: int) -> list[dict]:
    """抓 RSS / Atom feed。"""
    url = src["url"]
    items: list[dict] = []
    try:
        d = feedparser.parse(url)
        cutoff = datetime.now(CN_TZ) - timedelta(days=window_days)
        for entry in d.entries[: src.get("max", 20)]:
            published = None
            for k in ("published", "updated", "created"):
                if k in entry:
                    try:
                        published = dtp.parse(entry[k])
                        break
                    except Exception:
                        pass
            if published and (published.tzinfo is None):
                published = published.replace(tzinfo=CN_TZ)
            if published and published < cutoff:
                continue
            items.append({
                "title": re.sub(r"\s+", " ", entry.get("title", "")).strip(),
                "url": entry.get("link", ""),
                "summary": re.sub(r"\s+", " ", entry.get("summary", ""))[:500].strip(),
                "source": src["name"],
                "source_type": "rss",
                "fetched_at": now_cn(),
            })
    except Exception as e:
        log(f"[rss] {src['name']} 失败：{e}")
    return items


FETCHERS = {
    "web": fetch_web,
    "github_repo": fetch_github_repo,
    "rss": fetch_rss,
}


# ---------- main ----------
def main() -> int:
    cfg = load_sources()
    sources = [s for s in cfg.get("sources", []) if s.get("enabled", True)]
    window_days = int(cfg.get("window_days", 7))
    exclude_kw = cfg.get("filters", {}).get("exclude_keywords", [])
    max_per_source = int(cfg.get("max_per_source", 20))

    seen = load_seen()
    log(f"开始抓取：{len(sources)} 个源，窗口 {window_days} 天")

    candidates: list[dict] = []
    for src in sources:
        fetcher = FETCHERS.get(src["type"])
        if not fetcher:
            log(f"未知 type: {src['type']} - {src.get('name')}")
            continue
        src["max"] = max_per_source
        raw = fetcher(src, window_days)
        kept = []
        for it in raw:
            if not passes_filter(it["title"], it.get("summary", ""), exclude_kw):
                continue
            fp = fingerprint(it["title"], it["url"])
            if fp in seen:
                continue
            seen.add(fp)
            it["fingerprint"] = fp
            kept.append(it)
        log(f"{src['name']:30s} {len(raw):3d} -> {len(kept):3d}")
        candidates.extend(kept)

    save_seen(seen)
    OUT_FILE.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"完成：{len(candidates)} 条候选 → {OUT_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())