"""Background warmup for market workbench home read endpoints."""

from __future__ import annotations

import logging
import threading
import time
from contextvars import copy_context
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from backend.app.core_finance.macro.crisis_score import (
    DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
)
from backend.app.observability.response_cache import (
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
from backend.app.repositories.duckdb_read_context import resolve_effective_read_path
from backend.app.services.macro_toolkit_read_service import (
    build_macro_toolkit_analysis,
    build_macro_toolkit_strategy_summaries,
)
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    load_macro_toolkit_refresh_receipt_health,
)
from backend.app.services.macro_vendor_service import (
    choice_macro_formal_envelope,
    choice_macro_latest_envelope,
    macro_foundation_formal_envelope,
)
from backend.app.services.market_overview_service import (
    DEFAULT_MARKET_OVERVIEW_INCLUDE,
    build_market_snapshot,
    market_overview_snapshot_cache_key,
)

logger = logging.getLogger(__name__)

# Mirror the dashboard-home request parameters so the warmed keys are the ones
# the first page load actually asks for.
HOME_CREDIT_SPREAD_SCENARIOS = "10,25,50"
HOME_POSITION_CHANGES_TOP_N = 5
HOME_RESEARCH_REPORTS_LIMIT = 5
HOME_CAMPISI_LOOKBACK_DAYS = 30

# Mirrors frontend/src/features/cross-asset/lib/crossAssetKpiModel.ts
# CROSS_ASSET_KPI_SLOTS. Each inner tuple is one slot's ranked identity set.
# This is intentionally a second copy until the snapshot contract owns the
# complete cross-asset slot registry.
CROSS_ASSET_LINKAGE_SERIES_ID_GROUPS = (
    ("E1000180", "EMM00166466", "CA.CN_GOV_10Y"),
    ("E1003238", "EMG00001310", "CA.US_GOV_10Y"),
    ("EM1", "CA.CN_US_SPREAD"),
    ("EMM00167613", "CA.DR007"),
    ("EMM01843735",),
    ("CA.CSI300",),
    ("CA.CSI300_PE",),
    ("CA.MEGA_CAP_WEIGHT",),
    ("CA.MEGA_CAP_TOP5_WEIGHT",),
    ("CA.BRENT",),
    ("CA.STEEL",),
    ("CA.COPPER",),
    ("CA.ALUMINUM",),
    ("EMM00058124", "CA.USDCNY"),
)


class _EffectiveDuckDBSettingsView:
    def __init__(self, settings: object, duckdb_path: str) -> None:
        self._settings = settings
        self.duckdb_path = duckdb_path

    def __getattr__(self, name: str) -> object:
        return getattr(self._settings, name)


def _settings_for_effective_duckdb_path(settings: object, duckdb_path: str) -> object:
    if str(getattr(settings, "duckdb_path", "") or "") == duckdb_path:
        return settings
    model_copy = getattr(settings, "model_copy", None)
    if callable(model_copy):
        return model_copy(update={"duckdb_path": duckdb_path})
    return _EffectiveDuckDBSettingsView(settings, duckdb_path)


def warm_market_home_cache_if_configured(settings: object) -> bool:
    if not bool(getattr(settings, "market_home_prewarm_enabled", False)):
        return False
    duckdb_path = str(resolve_effective_read_path(getattr(settings, "duckdb_path", "") or ""))
    read_context = copy_context()
    thread = threading.Thread(
        target=lambda **kwargs: read_context.run(
            _warm_market_home_cache_quietly,
            **kwargs,
        ),
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
    duckdb_path = str(resolve_effective_read_path(getattr(settings, "duckdb_path", "") or ""))
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
    from backend.app.services.market_data_livermore_route_support import _cached_stock_analysis_workbench

    read_settings = (
        _settings_for_effective_duckdb_path(settings, duckdb_path)
        if settings is not None
        else None
    )
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
            lambda: build_macro_toolkit_analysis(
                "core",
                refresh_receipt_health=refresh_receipt_health,
            ),
        ),
        # Keep this aligned with MacroToolkitPage's full/430 crisis-history request.
        (
            "macro_analysis_full",
            market_home_macro_analysis_cache_key(
                duckdb_path,
                "full",
                history_limit=DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
                freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
            ),
            lambda: build_macro_toolkit_analysis(
                "full",
                history_limit=DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
                refresh_receipt_health=refresh_receipt_health,
            ),
        ),
        (
            "macro_strategy_summaries",
            market_home_strategy_summaries_cache_key(duckdb_path),
            build_macro_toolkit_strategy_summaries,
        ),
    ]
    home_steps = _dashboard_home_formal_steps(duckdb_path)
    steps.append(
        (
            "market_overview_snapshot",
            market_overview_snapshot_cache_key(
                include=DEFAULT_MARKET_OVERVIEW_INCLUDE,
                duckdb_path=duckdb_path,
                freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
            ),
            lambda: build_market_snapshot(
                include=DEFAULT_MARKET_OVERVIEW_INCLUDE,
                duckdb_path=duckdb_path,
                refresh_receipt_health=refresh_receipt_health,
            ),
        )
    )

    total_started = time.perf_counter()
    step_count = len(home_steps) + len(steps) + (15 if settings is not None else 0)
    logger.info(
        "market_home_prewarm_start duckdb=%s steps=%d force_refresh=%s",
        duckdb_path,
        step_count,
        force_refresh,
    )
    step_payloads: dict[str, object] = {}

    def warm_steps(selected_steps: list[tuple[str, str, Any]]) -> None:
        for step_name, cache_key, builder in selected_steps:
            step_started = time.perf_counter()
            try:
                if force_refresh:
                    # Keep the live entry readable during rebuilding; the generation
                    # guard discards results invalidated by a concurrent data refresh.
                    generation = market_home_response_cache.generation()
                    payload = builder()
                    market_home_response_cache.set(cache_key, payload, generation=generation)
                else:
                    payload = market_home_response_cache.get_or_build(cache_key, builder)
            except Exception:
                logger.exception("market_home_prewarm_step_failed step=%s", step_name)
                continue
            step_payloads[step_name] = payload
            logger.info(
                "market_home_prewarm_step ok step=%s ms=%d",
                step_name,
                int((time.perf_counter() - step_started) * 1000),
            )

    # The homepage must not wait behind stock-workbench or macro rebuilds.
    # Keep all reads sequential and preserve each page's exact request key.
    warm_steps(home_steps)
    if read_settings is not None:
        source_dir = str(getattr(read_settings, "product_category_source_dir", "") or "").strip()
        if source_dir:
            candidate_started = time.perf_counter()
            try:
                from backend.app.services.candidate_financial_indicator_service import (
                    candidate_financial_indicator_envelope,
                )

                candidate_date = _dashboard_home_report_date(duckdb_path)
                if candidate_date is not None:
                    candidate_financial_indicator_envelope(
                        source_dir=source_dir,
                        report_month=date.fromisoformat(candidate_date).strftime("%Y%m"),
                        include_lineage=False,
                        metric_id="income.operating.mother_bank",
                    )
                    logger.info(
                        "market_home_prewarm_step ok step=home_operating_revenue_candidate ms=%d",
                        int((time.perf_counter() - candidate_started) * 1000),
                    )
            except Exception:
                logger.exception("market_home_prewarm_step_failed step=home_operating_revenue_candidate")
        # These services own versioned caches. Refresh their exact default-page
        # keys before the heavy workbench reads, leaving valid entries readable.
        from backend.app.services.bond_analytics_service import (
            get_krd_curve_risk,
            get_portfolio_headlines,
            get_return_decomposition_summary,
            get_top_holdings,
        )
        from backend.app.services.bond_dashboard_service import get_bond_dashboard_home_summary
        from backend.app.services.pnl_attribution_service import (
            attribution_analysis_summary_envelope,
            volume_rate_attribution_envelope,
        )
        from backend.app.services.yield_curve_term_structure_service import get_yield_curve_term_structure

        try:
            page_report_date = _dashboard_home_report_date(duckdb_path)
            page_date = date.fromisoformat(page_report_date) if page_report_date else None
        except Exception:
            logger.exception("market_home_prewarm_step_failed step=default_page_report_date")
            page_date = None
        if page_date is not None:
            page_read_steps = [
                ("bond_home_summary", lambda: get_bond_dashboard_home_summary(
                    page_date, force_refresh=force_refresh,
                )),
                ("return_decomposition_summary", lambda: get_return_decomposition_summary(
                    page_date, force_refresh=force_refresh,
                )),
                ("volume_rate", lambda: volume_rate_attribution_envelope(
                    report_date=page_date.isoformat(), compare_type="mom", force_refresh=force_refresh,
                )),
                ("attribution_summary", lambda: attribution_analysis_summary_envelope(
                    report_date=page_date.isoformat(), force_refresh=force_refresh,
                )),
                ("yield_curve_term_structure", lambda: get_yield_curve_term_structure(
                    report_date=page_date,
                    curve_types=("treasury", "cdb", "aaa_credit"),
                    force_refresh=force_refresh,
                )),
                ("krd_curve_risk", lambda: get_krd_curve_risk(
                    page_date, scenario_set="standard", force_refresh=force_refresh,
                )),
                ("top_holdings", lambda: get_top_holdings(page_date, top_n=14)),
                ("portfolio_headlines", lambda: get_portfolio_headlines(
                    page_date, force_refresh=force_refresh,
                )),
            ]
            for step_name, builder in page_read_steps:
                step_started = time.perf_counter()
                try:
                    builder()
                except Exception:
                    logger.exception("market_home_prewarm_step_failed step=%s", step_name)
                    continue
                logger.info(
                    "market_home_prewarm_step ok step=%s ms=%d",
                    step_name,
                    int((time.perf_counter() - step_started) * 1000),
                )

        # Balance decisions use the balance domain's latest date. Only the
        # workbook is cached by this service; manual statuses stay live reads.
        governance_dir = str(getattr(read_settings, "governance_path", "") or "").strip()
        if governance_dir:
            from backend.app.services.balance_analysis_service import (
                balance_analysis_dates_envelope,
                balance_analysis_decision_items_envelope,
            )

            balance_started = time.perf_counter()
            try:
                balance_result = balance_analysis_dates_envelope(
                    duckdb_path=duckdb_path, governance_dir=governance_dir,
                ).get("result")
                balance_dates = balance_result.get("report_dates") if isinstance(balance_result, dict) else None
                if isinstance(balance_dates, list) and balance_dates:
                    balance_date = date.fromisoformat(balance_dates[0]).isoformat()
                    balance_analysis_decision_items_envelope(
                        duckdb_path=duckdb_path,
                        governance_dir=governance_dir,
                        report_date=balance_date,
                        position_scope="all",
                        currency_basis="CNY",
                        force_refresh=force_refresh,
                    )
                    logger.info(
                        "market_home_prewarm_step ok step=balance_decisions ms=%d",
                        int((time.perf_counter() - balance_started) * 1000),
                    )
            except Exception:
                logger.exception("market_home_prewarm_step_failed step=balance_decisions")

        macro_started = time.perf_counter()
        try:
            from backend.app.repositories.home_macro_release_context_repo import HomeMacroReleaseContextRepository
            from backend.app.services.home_macro_release_context_service import HomeMacroReleaseContextService

            today = date.today()
            HomeMacroReleaseContextService(
                repository=HomeMacroReleaseContextRepository(duckdb_path),
                bindings_path=Path(__file__).resolve().parents[3] / "config" / "home_macro_release_bindings.json",
            ).build_envelope(
                window_start_date=today,
                window_end_date=today + timedelta(days=45),
                history_limit=8,
                force_refresh=force_refresh,
            )
            logger.info(
                "market_home_prewarm_step ok step=home_macro_release_context ms=%d",
                int((time.perf_counter() - macro_started) * 1000),
            )
        except Exception:
            logger.exception("market_home_prewarm_step_failed step=home_macro_release_context")
        stock_started = time.perf_counter()
        try:
            (
                _payload,
                cache_status,
                compute_ms,
                overlay_ms,
                cache_ms,
            ) = _cached_stock_analysis_workbench(
                settings=read_settings,
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

    warm_steps(steps)

    if read_settings is not None:
        report_date = _cross_asset_headline_report_date(step_payloads.get("choice_latest"))
        if report_date is None:
            logger.warning(
                "market_home_prewarm_step_skipped step=livermore_signal_confluence "
                "reason=cross_asset_report_date_unavailable"
            )
            logger.warning(
                "market_home_prewarm_step_skipped step=macro_bond_linkage "
                "reason=cross_asset_report_date_unavailable"
            )
        else:
            _warm_livermore_signal_confluence(
                settings=read_settings,
                requested_as_of_date=report_date,
                force_refresh=force_refresh,
            )
            _warm_macro_bond_linkage(report_date)

    logger.info(
        "market_home_prewarm_done duckdb=%s total_ms=%d",
        duckdb_path,
        int((time.perf_counter() - total_started) * 1000),
    )


def _cross_asset_headline_report_date(choice_latest_envelope: object) -> str | None:
    if not isinstance(choice_latest_envelope, dict):
        return None
    result = choice_latest_envelope.get("result")
    if not isinstance(result, dict):
        return None
    series = result.get("series")
    if not isinstance(series, list):
        return None

    by_id = {
        str(item.get("series_id")): item
        for item in series
        if isinstance(item, dict) and item.get("series_id") and item.get("trade_date")
    }
    selected_dates: list[str] = []
    for candidates in CROSS_ASSET_LINKAGE_SERIES_ID_GROUPS:
        ranked = [
            (by_id[series_id], priority)
            for priority, series_id in enumerate(candidates)
            if series_id in by_id
        ]
        usable = [item for item in ranked if str(item[0].get("quality_flag") or "") != "stale"]
        pool = usable or ranked
        if not pool:
            continue
        point, _priority = max(
            pool,
            key=lambda item: (str(item[0].get("trade_date") or ""), -item[1]),
        )
        selected_dates.append(str(point["trade_date"]))
    return max(selected_dates) if selected_dates else None


def _warm_livermore_signal_confluence(
    *,
    settings: object,
    requested_as_of_date: str,
    force_refresh: bool,
) -> None:
    from backend.app.services.market_data_livermore_route_support import (
        _cached_livermore_signal_confluence,
        _livermore_strategy_cache_key,
        _selected_pretrade_external_read,
        _theme_overlay_fingerprint,
        _theme_overlay_reader_from_settings,
        _with_livermore_workbench_summary,
    )
    from backend.app.services.market_data_livermore_service import (
        livermore_strategy_envelope_from_catalog,
    )

    duckdb_path = str(
        resolve_effective_read_path(settings.duckdb_path)  # type: ignore[attr-defined]
    )
    catalog_file = settings.choice_stock_catalog_file  # type: ignore[attr-defined]
    theme_overlay_reader = _theme_overlay_reader_from_settings(settings)
    overlay_fingerprint = _theme_overlay_fingerprint(theme_overlay_reader)

    def load_cached(key: str, builder: Any) -> object:
        if not force_refresh:
            return market_home_response_cache.get_or_build(key, builder)
        generation = market_home_response_cache.generation()
        payload = builder()
        market_home_response_cache.set(key, payload, generation=generation)
        return payload

    step_started = time.perf_counter()
    try:
        strategy = load_cached(
            _livermore_strategy_cache_key(
                duckdb_path=duckdb_path,
                catalog_file=catalog_file,
                as_of_date=requested_as_of_date,
                theme_overlay_fingerprint=overlay_fingerprint,
            ),
            lambda: _with_livermore_workbench_summary(
                livermore_strategy_envelope_from_catalog(
                    duckdb_path=duckdb_path,
                    as_of_date=requested_as_of_date,
                    choice_stock_catalog_file=catalog_file,
                    theme_overlay_reader=theme_overlay_reader,
                ),
                summary_kind="strategy",
            ),
        )
        strategy_result = strategy.get("result") if isinstance(strategy, dict) else None
        resolved_as_of_date = (
            str(strategy_result.get("as_of_date") or "").strip()
            if isinstance(strategy_result, dict)
            else ""
        )
        if not resolved_as_of_date:
            logger.warning(
                "market_home_prewarm_step_skipped step=livermore_signal_confluence "
                "reason=livermore_resolved_as_of_date_unavailable"
            )
            return
        selected_pretrade_read = _selected_pretrade_external_read(
            catalog_file=catalog_file,
            as_of_date=resolved_as_of_date,
        )
        _cached_livermore_signal_confluence(
            duckdb_path=duckdb_path,
            as_of_date=resolved_as_of_date,
            catalog_file=catalog_file,
            theme_overlay_reader=theme_overlay_reader,
            theme_overlay_fingerprint=overlay_fingerprint,
            selected_pretrade_read=selected_pretrade_read,
            force_refresh=force_refresh,
        )
    except Exception:
        logger.exception("market_home_prewarm_step_failed step=livermore_signal_confluence")
        return
    logger.info(
        "market_home_prewarm_step ok step=livermore_signal_confluence ms=%d",
        int((time.perf_counter() - step_started) * 1000),
    )


def _warm_macro_bond_linkage(report_date: str) -> None:
    from backend.app.services.macro_bond_linkage_service import get_macro_bond_linkage

    step_started = time.perf_counter()
    try:
        get_macro_bond_linkage(date.fromisoformat(report_date))
    except Exception:
        logger.exception("market_home_prewarm_step_failed step=macro_bond_linkage")
        return
    logger.info(
        "market_home_prewarm_step ok step=macro_bond_linkage ms=%d",
        int((time.perf_counter() - step_started) * 1000),
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
