"""Ingest Tushare news rows into `choice_news_event` for dashboard News Digest."""

from __future__ import annotations

import logging
import os

from backend.app.governance.settings import get_settings
from backend.app.repositories.tushare_adapter import (
    TUSHARE_TOKEN_ENV,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.tasks.tushare_news_ingest import materialize_tushare_news_to_choice_news

logger = logging.getLogger(__name__)

TUSHARE_NEWS_SRC_ENV = "MOSS_TUSHARE_NEWS_SRC"


def _resolve_tushare_token() -> str:
    """Read token from process env first; fall back to MOSS Settings."""
    try:
        return resolve_tushare_token_with_settings_fallback(get_settings())
    except Exception:
        logger.warning("Failed to resolve tushare token from settings, returning empty", exc_info=True)
        return ""


def _resolve_tushare_news_src(default: str = "sina") -> str:
    explicit = os.getenv(TUSHARE_NEWS_SRC_ENV, "").strip()
    if explicit:
        return explicit
    try:
        configured = str(getattr(get_settings(), "tushare_news_src", "") or "").strip()
        if configured:
            return configured
    except Exception:
        logger.debug("Failed to read tushare_news_src from settings", exc_info=True)
    return default


def ingest_tushare_npr_to_choice_news(
    duckdb_path: str,
    *,
    limit: int = 20,
    news_limit: int = 100,
    news_src: str | None = None,
    news_lookback_hours: int = 48,
    cctv_lookback_days: int = 3,
    major_lookback_hours: int = 48,
    research_lookback_days: int = 3,
) -> dict[str, object]:
    """
    Pull five Tushare news streams into the Choice news tables.

    The service keeps the public synchronous contract and vendor client setup.
    DuckDB writes are delegated to the task layer.
    """
    token = _resolve_tushare_token()
    if not token:
        raise RuntimeError(
            f"{TUSHARE_TOKEN_ENV} is not set; add it to config/.env or export it before calling Tushare pro API."
        )

    import tushare as ts  # lazy: optional dependency at runtime

    pro = ts.pro_api(token)
    src_resolved = (news_src or _resolve_tushare_news_src()).strip() or "sina"
    return materialize_tushare_news_to_choice_news(
        duckdb_path=duckdb_path,
        pro=pro,
        news_src=src_resolved,
        limit=limit,
        news_limit=news_limit,
        news_lookback_hours=news_lookback_hours,
        cctv_lookback_days=cctv_lookback_days,
        major_lookback_hours=major_lookback_hours,
        research_lookback_days=research_lookback_days,
    )
