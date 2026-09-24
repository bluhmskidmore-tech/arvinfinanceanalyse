"""Background warmup for market workbench home read endpoints."""

from __future__ import annotations

import logging
import threading
import time
from datetime import date
from typing import Any

from backend.app.api.response_cache import (
    bond_analytics_credit_spread_migration_cache_key,
    bond_analytics_position_changes_cache_key,
    campisi_four_effects_cache_key,
    home_research_reports_cache_key,
    market_home_catalog_cache_key,
    market_home_choice_latest_cache_key,
    market_home_macro_analysis_cache_key,
    market_home_rates_cache_key,
    market_home_response_cache,
    market_home_strategy_summaries_cache_key,
)
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    load_macro_toolkit_refresh_receipt_health,
)
from backend.app.services.macro_vendor_service import (
    choice_macro_formal_envelope,
    choice_macro_latest_envelope,
    macro_foundation_formal_envelope,
)

logger = logging.getLogger(__name__)

# Mirror the dashboard-home request parameters so the warmed keys are the ones
# the first page load actually asks for.
HOME_CREDIT_SPREAD_SCENARIOS = "10,25,50"
HOME_POSITION_CHANGES_TOP_N = 5
HOME_RESEARCH_REPORTS_LIMIT = 5
HOME_CAMPISI_LOOKBACK_DAYS = 30


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


def warm_market_home_cache_in_current_thread_if_configured(
    settings: object,
    *,
    force_refresh: bool = False,
) -> bool:
    if not bool(getattr(settings, "market_home_prewarm_enabled", False)):
        return False
    duckdb_path = str(getattr(settings, "duckdb_path", "") or "")
    _warm_market_home_cache_quietly(
        duckdb_path=duckdb_path,
        settings=settings,
        force_refresh=force_refresh,
    )
    return True


def _warm_market_home_cache_quietly(
    *,
    duckdb_path: str,
    settings: object | None = None,
    force_refresh: bool = False,
) -> None:
    try:
        warm_market_home_read_caches(
            duckdb_path=duckdb_path,
            settings=settings,
            force_refresh=force_refresh,
        )
    except Exception:
        logger.exception("market_home_prewarm_failed")


def warm_market_home_read_caches(
    *,
    duckdb_path: str,
    settings: object | None = None,
    force_refresh: bool = False,
) -> None:
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

    refresh_receipt_health = load_macro_toolkit_refresh_receipt_health()

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
            market_home_macro_analysis_cache_key(
                duckdb_path,
                "core",
                freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
            ),
            lambda: _build_macro_toolkit_analysis(
                "core",
                refresh_receipt_health=refresh_receipt_health,
            ),
        ),
        (
            "macro_strategy_summaries",
            market_home_strategy_summaries_cache_key(duckdb_path),
            _build_macro_toolkit_strategy_summaries,
        ),
    ]
    steps.extend(_dashboard_home_formal_steps(duckdb_path))

    total_started = time.perf_counter()
    step_count = len(steps) + (1 if settings is not None else 0)
    logger.info(
        "market_home_prewarm_start duckdb=%s steps=%d force_refresh=%s",
        duckdb_path,
        step_count,
        force_refresh,
    )
    if settings is not None:
        stock_started = time.perf_counter()
        try:
            (
                _payload,
                cache_status,
                compute_ms,
                overlay_ms,
                cache_ms,
            ) = _cached_stock_analysis_workbench(
                settings=settings,
                as_of_date=None,
                include=None,
                sector_window_days=20,
                top_k=10,
            )
        except Exception:
            logger.exception("market_home_prewarm_step_failed step=stock_analysis_workbench")
        else:
            total_ms = int((time.perf_counter() - stock_started) * 1000)
            logger.info(
                "market_home_prewarm_step ok step=stock_analysis_workbench ms=%d "
                "cache_status=%s compute_ms=%d overlay_ms=%d cache_ms=%d wait_ms=%d "
                "top_k=10 sector_window_days=20",
                total_ms,
                cache_status,
                int(compute_ms),
                int(overlay_ms),
                int(cache_ms),
                int(cache_ms) if cache_status == "wait" else 0,
            )

    for step_name, cache_key, builder in steps:
        step_started = time.perf_counter()
        try:
            if force_refresh:
                # A still-live entry short-circuits get_or_build, so a refresh pass
                # must rebuild and overwrite to actually push the expiry out. The
                # generation guard drops the result if an invalidate (e.g. a data
                # refresh endpoint) landed while the rebuild was running.
                generation = market_home_response_cache.generation()
                market_home_response_cache.set(cache_key, builder(), generation=generation)
            else:
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


def _latest_bond_report_date(duckdb_path: str) -> str | None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    try:
        report_dates = BondAnalyticsRepository(duckdb_path).list_report_dates()
    except Exception:
        logger.exception("market_home_prewarm_report_date_failed")
        return None
    return report_dates[0] if report_dates else None


def _dashboard_home_report_date(duckdb_path: str) -> str | None:
    """Resolve the report_date the dashboard-home page will actually request.

    The page derives every dated request from the home snapshot's unified
    report_date (the cross-domain intersection), not from the bond-domain
    maximum. Warming any other date builds cache keys the page never asks for,
    so the whole prewarm silently misses as soon as one domain lands a newer
    date than the others. Falls back to the bond-domain maximum when the
    snapshot is unavailable.
    """
    from backend.app.services.executive_service import home_snapshot_unified_report_date

    unified = home_snapshot_unified_report_date()
    if unified is not None:
        return unified
    return _latest_bond_report_date(duckdb_path)


def _dashboard_home_formal_steps(duckdb_path: str) -> list[tuple[str, str, Any]]:
    """Warm the dashboard-home endpoints that recompute from DuckDB per request."""
    from backend.app.services.bond_analytics_service import (
        get_credit_spread_migration,
        get_position_changes,
    )
    from backend.app.services.campisi_attribution_service import (
        campisi_four_effects_summary_envelope,
    )
    from backend.app.services.executive_service import home_research_reports_envelope

    today = date.today().isoformat()
    steps: list[tuple[str, str, Any]] = [
        (
            "home_research_reports",
            home_research_reports_cache_key(
                duckdb_path,
                report_date=today,
                limit=HOME_RESEARCH_REPORTS_LIMIT,
            ),
            lambda: home_research_reports_envelope(
                report_date=today,
                limit=HOME_RESEARCH_REPORTS_LIMIT,
            ),
        ),
    ]

    report_date = _dashboard_home_report_date(duckdb_path)
    if report_date is None:
        return steps

    report_date_value = date.fromisoformat(report_date)
    steps.extend(
        [
            (
                "credit_spread_migration",
                bond_analytics_credit_spread_migration_cache_key(
                    duckdb_path,
                    report_date=report_date,
                    spread_scenarios=HOME_CREDIT_SPREAD_SCENARIOS,
                ),
                lambda: get_credit_spread_migration(
                    report_date_value,
                    HOME_CREDIT_SPREAD_SCENARIOS,
                ),
            ),
            (
                "position_changes",
                bond_analytics_position_changes_cache_key(
                    duckdb_path,
                    report_date=report_date,
                    top_n=HOME_POSITION_CHANGES_TOP_N,
                ),
                lambda: get_position_changes(
                    report_date_value,
                    top_n=HOME_POSITION_CHANGES_TOP_N,
                ),
            ),
            (
                "campisi_four_effects_summary",
                campisi_four_effects_cache_key(
                    duckdb_path,
                    detail="summary",
                    start_date=None,
                    end_date=report_date,
                    lookback_days=HOME_CAMPISI_LOOKBACK_DAYS,
                ),
                lambda: campisi_four_effects_summary_envelope(
                    start_date=None,
                    end_date=report_date,
                    lookback_days=HOME_CAMPISI_LOOKBACK_DAYS,
                ),
            ),
        ]
    )
    return steps
