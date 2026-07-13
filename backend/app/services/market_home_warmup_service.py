"""Background warmup for market workbench home read endpoints."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from backend.app.api.response_cache import (
    market_home_catalog_cache_key,
    market_home_choice_latest_cache_key,
    market_home_macro_analysis_cache_key,
    market_home_rates_cache_key,
    market_home_response_cache,
    market_home_strategy_summaries_cache_key,
)
from backend.app.services.macro_vendor_service import (
    choice_macro_formal_envelope,
    choice_macro_latest_envelope,
    macro_foundation_formal_envelope,
)

logger = logging.getLogger(__name__)


def warm_market_home_cache_if_configured(settings: object) -> bool:
    if not bool(getattr(settings, "market_home_prewarm_enabled", False)):
        return False
    duckdb_path = str(getattr(settings, "duckdb_path", "") or "")
    thread = threading.Thread(
        target=_warm_market_home_cache_quietly,
        kwargs={"duckdb_path": duckdb_path, "settings": settings},
        daemon=True,
        name="moss-market-home-warmup",
    )
    thread.start()
    return True


def _warm_market_home_cache_quietly(*, duckdb_path: str, settings: object | None = None) -> None:
    try:
        warm_market_home_read_caches(duckdb_path=duckdb_path, settings=settings)
    except Exception:
        logger.exception("market_home_prewarm_failed")


def warm_market_home_read_caches(*, duckdb_path: str, settings: object | None = None) -> None:
    """Populate the market-home TTL cache sequentially.

    Sequential DuckDB reads avoid Windows file-lock contention when several
    heavy endpoints would otherwise start at once on first page load.
    """
    # Import route builders lazily to keep module import graph shallow.
    from backend.app.api.routes.macro_toolkit import (
        _build_macro_toolkit_analysis,
        _build_macro_toolkit_strategy_summaries,
    )
    from backend.app.api.routes.market_data_livermore import _cached_stock_analysis_workbench

    steps: list[tuple[str, str, Any]] = [
        (
            "choice_latest",
            market_home_choice_latest_cache_key(duckdb_path),
            lambda: choice_macro_latest_envelope(duckdb_path, category=None),
        ),
        (
            "market_rates",
            market_home_rates_cache_key(duckdb_path),
            lambda: choice_macro_formal_envelope(duckdb_path),
        ),
        (
            "market_catalog",
            market_home_catalog_cache_key(duckdb_path),
            lambda: macro_foundation_formal_envelope(duckdb_path),
        ),
        (
            "macro_analysis_core",
            market_home_macro_analysis_cache_key(duckdb_path, "core"),
            lambda: _build_macro_toolkit_analysis("core"),
        ),
        (
            "macro_strategy_summaries",
            market_home_strategy_summaries_cache_key(duckdb_path),
            _build_macro_toolkit_strategy_summaries,
        ),
    ]

    total_started = time.perf_counter()
    step_count = len(steps) + (1 if settings is not None else 0)
    logger.info("market_home_prewarm_start duckdb=%s steps=%d", duckdb_path, step_count)
    if settings is not None:
        stock_started = time.perf_counter()
        try:
            _cached_stock_analysis_workbench(
                settings=settings,
                as_of_date=None,
                include=None,
                sector_window_days=20,
                top_k=3,
            )
        except Exception:
            logger.exception("market_home_prewarm_step_failed step=stock_analysis_workbench")
        else:
            logger.info(
                "market_home_prewarm_step ok step=stock_analysis_workbench ms=%d",
                int((time.perf_counter() - stock_started) * 1000),
            )

    for step_name, cache_key, builder in steps:
        step_started = time.perf_counter()
        try:
            market_home_response_cache.get_or_build(cache_key, builder)
        except Exception:
            logger.exception("market_home_prewarm_step_failed step=%s", step_name)
            continue
        logger.info(
            "market_home_prewarm_step ok step=%s ms=%d",
            step_name,
            int((time.perf_counter() - step_started) * 1000),
        )

    logger.info(
        "market_home_prewarm_done duckdb=%s total_ms=%d",
        duckdb_path,
        int((time.perf_counter() - total_started) * 1000),
    )
