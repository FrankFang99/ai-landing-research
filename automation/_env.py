"""automation/_env.py · 统一从 .env / env var 加载 LLM 配置

放在 automation/ 目录下，fetch.py / classify.py / build_index.py 共用。
约定：
  - 已存在的 env var 不覆盖（CI 走 GitHub Secrets 注入优先）
  - .env 在仓库根目录（automation 的上一级）
  - 如果 python-dotenv 未装或 .env 不存在，静默 fallback 到现有 env var
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _ROOT / ".env"


def load_env() -> None:
    """从 .env 加载未设置的 LLM_* env var。失败静默。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return   # 没装 python-dotenv 就算了（CI 不需要 .env）
    if not _ENV_FILE.exists():
        return
    # override=False：已存在的 env var 不覆盖（CI Secrets 优先）
    load_dotenv(_ENV_FILE, override=False)
