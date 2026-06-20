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
    return datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


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


def fetch_bilibili_user(src: dict, window_days: int) -> list[dict]:
    """抓 B 站 UP 主的最新投稿视频。

    路径：
      1) 用 B 站公开搜索 API (x/web-interface/search/type?search_type=bili_user)
         拿 UP 主信息（昵称、粉丝数）—— 验证 mid 有效（失败仅记日志、不阻塞）
      2) 用 B 站公开搜索 API (x/web-interface/search/type?search_type=video)
         搜视频 + 按 mid 二次过滤，按 pubdate 倒序拿最新 N 条投稿

    不需要登录态、不需要 wbi 签名。
    """
    mid = src.get("mid", "")
    if isinstance(mid, int):
        mid = str(mid)
    mid = mid.strip()
    if not mid:
        log(f"[bilibili] {src['name']} 缺 mid，跳过")
        return []


    name = src.get("name", mid)
    items: list[dict] = []

    # Step 1: 拿 UP 主基本信息（验证 mid + 拿昵称，仅做日志，不阻塞）
    up_name = name
    up_info_url = f"https://api.bilibili.com/x/space/acc/info?mid={mid}"
    try:
        r = requests.get(up_info_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Referer": f"https://space.bilibili.com/{mid}/",
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            log(f"[bilibili] {name} mid={mid} acc/info code={data.get('code')} msg={data.get('message')}（继续走搜索 API）")
        else:
            up_name = (data.get("data") or {}).get("name") or name
            log(f"[bilibili] {name} (mid={mid}) → UP主「{up_name}」")
    except Exception as e:
        log(f"[bilibili] {name} mid={mid} 信息接口异常：{e}（继续走搜索 API）")


    # Step 2: 用 B 站搜索 API 按 mid 拉最新视频
    # 思路：搜 sources.yaml 里的关键词 + 按 mid 字段在结果里二次过滤（实测 mid
    # 参数在 B 站搜索 API 中不可靠，必须用返回字段里的 mid 二次过滤）。
    keywords = src.get("keywords") or ["AI", "大模型"]
    query_kw = " ".join(keywords[:2])  # 关键词别太多，B 站搜索相关性会崩
    cutoff = int((datetime.now(CN_TZ) - timedelta(days=window_days)).timestamp())
    seen_bvids: set[str] = set()
    pages_fetched = 0

    for page in range(1, 4):  # 最多翻 3 页（30 条），覆盖 window 内一般够
        try:
            r = requests.get(
                "https://api.bilibili.com/x/web-interface/search/type",
                params={
                    "search_type": "video",
                    "keyword": query_kw,
                    "page": page,
                    "page_size": 10,
                    "order": "pubdate",
                    "mid": mid,  # 留作 hint，部分版本会生效
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
                    "Referer": "https://www.bilibili.com/",
                },
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("code") != 0:
                log(f"[bilibili] {name} 搜索 API page={page} code={data.get('code')} msg={data.get('message')}")
                break
            results = (data.get("data") or {}).get("result") or []
            if not results:
                break
            pages_fetched += 1
            for v in results:
                # mid 参数在 B 站搜索 API 中实际并不严格生效，必须用返回字段二次过滤
                # mid 字段可能是 int 也可能是 str
                v_mid = str(v.get("mid") or v.get("uid") or "")
                if v_mid != mid:
                    continue
                bvid = v.get("bvid") or ""
                if not bvid or bvid in seen_bvids:
                    continue
                seen_bvids.add(bvid)
                pubdate = int(v.get("pubdate") or 0)
                # 早于 window 的丢掉
                if pubdate and pubdate < cutoff:
                    continue
                title = re.sub(r"<[^>]+>", "", v.get("title", "")).strip()  # 去 <em> 高亮
                items.append({
                    "title": title,
                    "url": v.get("arcurl") or f"https://www.bilibili.com/video/{bvid}",
                    "summary": (v.get("description") or v.get("desc") or "")[:200],
                    "source": f"{src['name']}（B站）",
                    "source_type": "bilibili_user",
                    "fetched_at": now_cn(),
                    "published_ts": pubdate,
                })
                if len(items) >= src.get("max", 20):
                    break
            if len(items) >= src.get("max", 20):
                break
        except Exception as e:
            log(f"[bilibili] {name} 搜索 page={page} 异常：{e}")
            break

    if not items:
        log(f"[bilibili] {name} window 内无新视频（UP 主最近 {window_days} 天没发,翻了 {pages_fetched} 页）")
        return []

    log(f"[bilibili] {name} 抓到 {len(items)} 条新视频（翻了 {pages_fetched} 页搜索）")
    return items


def _bilibili_fallback_search(mid: str, up_name: str, src: dict, window_days: int) -> list[dict]:
    """bilibili_user 主路径拿不到数据时，用 web_search 兜底搜 UP 主最近视频。

    复用 matrix mcp 的 web_search，通过 MCP CLI 调用。
    """
    import subprocess
    import json as _json
    name = src.get("name", mid)
    keywords = src.get("keywords", []) or ["AI", "大模型"]
    query = f"{up_name} {' '.join(keywords[:3])} site:bilibili.com"
    try:
        result = subprocess.run(
            ["mavis", "mcp", "call", "matrix", "web_search", _json.dumps({"query": query, "count": 5})],
            capture_output=True, text=True, timeout=30, encoding="utf-8",
        )
        if result.returncode != 0:
            log(f"[bilibili-fallback] {name} 搜索调用失败：{result.stderr[:200]}")
            return []
        out = _json.loads(result.stdout)
        results = (out.get("results") or [])
        items = []
        for r in results:
            url = r.get("link", "")
            if "bilibili.com/video/" not in url:
                continue
            title = r.get("title", "").strip()
            if not title:
                continue
            items.append({
                "title": title,
                "url": url,
                "summary": (r.get("content") or r.get("snippet") or "")[:200],
                "source": f"{src['name']}（B站）",
                "source_type": "bilibili_user",
                "fetched_at": now_cn(),
            })
        log(f"[bilibili-fallback] {name} web_search 兜底拿到 {len(items)} 条")
        return items
    except Exception as e:
        log(f"[bilibili-fallback] {name} 异常：{e}")
        return []


FETCHERS = {
    "web": fetch_web,
    "github_repo": fetch_github_repo,
    "rss": fetch_rss,
    "bilibili_user": fetch_bilibili_user,
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