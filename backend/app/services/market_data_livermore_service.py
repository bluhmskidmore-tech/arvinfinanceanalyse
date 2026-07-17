from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
import uuid
from calendar import monthrange
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import cast

import duckdb
from backend.app.core_finance.cycle_macro_score import (
    CN10Y_SERIES_ID,
    CSI300_PE_SERIES_ID,
    M2_YOY_SERIES_ID,
    PMI_SERIES_ID,
    SOCIAL_FINANCING_YOY_SERIES_ID,
    CycleMacroSnapshot,
    build_cycle_macro_snapshot,
)
from backend.app.core_finance.data_freshness import (
    FRESHNESS_TIER_EXPIRED,
    FRESHNESS_TIER_FRESH,
    FRESHNESS_TIER_STALE,
    assess_freshness,
)
from backend.app.core_finance.factor_screen_candidates import (
    compute_factor_screen_candidates,
)
from backend.app.core_finance.fresh_trend_watchlist_candidates import (
    FreshTrendWatchlistSnapshot,
    compute_fresh_trend_watchlist_candidates,
)
from backend.app.core_finance.gate_macro_overlay import (
    MacroCycleObservation,
    apply_macro_gate_overlay,
)
from backend.app.core_finance.hybrid_fusion_candidates import (
    compute_hybrid_fusion_candidates,
)
from backend.app.core_finance.hybrid_fusion_config import (
    DEFAULT_STRATEGY_YAML,
    load_hybrid_fusion_thresholds,
)
from backend.app.core_finance.livermore_risk_exit import (
    MVP_RULE_LABEL,
    RiskExitSnapshot,
    compute_risk_exit,
)
from backend.app.core_finance.livermore_risk_exit import (
    REQUIRED_INPUTS as RISK_EXIT_REQUIRED_INPUTS,
)
from backend.app.core_finance.livermore_sector_rank import (
    SectorRankConstituent,
    compute_sector_rank,
)
from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
    StockCandidateSnapshot,
    compute_stock_candidates,
    is_stock_candidate_policy_active,
    stock_candidate_policy_active_market_states,
)
from backend.app.core_finance.livermore_strategy import (
    BroadIndexObservation,
    MarketGateSupplement,
    evaluate_market_gate,
)
from backend.app.core_finance.livermore_theme_breakout import (
    ThemeBreakoutSnapshot,
    compute_theme_breakout,
)
from backend.app.core_finance.mean_reversion_candidates import (
    MeanReversionSnapshot,
    compute_mean_reversion_candidates,
)
from backend.app.core_finance.uptrend_momentum_candidates import (
    UptrendMomentumSnapshot,
    compute_uptrend_momentum_candidates,
)
from backend.app.repositories.choice_stock_adapter import (
    ChoiceStockReadiness,
    choice_stock_optional_input_status,
    choice_stock_readiness_missing,
    load_choice_stock_readiness,
)
from backend.app.repositories.livermore_gate_supplement_repo import fetch_market_gate_supplement
from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    StockAnalysisThemeOverlayReader,
    ThemeOverlayReadResult,
)
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)
from backend.app.services.runtime_cache import get_runtime_cache
from backend.app.tasks.choice_stock_materialize import (
    ChoiceStockMaterializationCoverage,
    load_choice_stock_materialization_coverage,
)

logger = logging.getLogger(__name__)

RULE_VERSION = "rv_livermore_strategy_v1"
CACHE_VERSION = "cv_livermore_strategy_v1"
PAYLOAD_CACHE_NAME = "livermore_strategy_payload"
PAYLOAD_CACHE_TTL_SECONDS = 120.0
RESULT_KIND = "market_data.livermore"
STRATEGY_NAME = "Livermore A-Share Defended Trend"
EXECUTION_STOCK_CANDIDATE_POLICY = EXP3B_STOCK_CANDIDATE_POLICY
EMPTY_SOURCE_VERSION = "sv_livermore_empty"
EMPTY_VENDOR_VERSION = "vv_none"
BROAD_INDEX_SERIES_ID = "CA.CSI300"
HISTORY_LIMIT = 260
CHOICE_STOCK_HISTORY_WINDOW = 130
STOCK_CANDIDATE_LIMIT_RATIO_BLOCK_REASON = (
    "No price-field or rule-derived limit_ratio source is available for Livermore stock pivot filters."
)
STOCK_CANDIDATE_POLICY_INACTIVE_INPUT_FAMILY = "stock_candidate_policy"
STOCK_CANDIDATE_POLICY_INACTIVE_REASON_PREFIX = "Stock candidate policy "
MAINBOARD_RISK_WARNING_LIMIT_RATIO_10_START = date(2026, 7, 6)
SECTOR_REQUIRED_ITEMS: tuple[tuple[str, str], ...] = (
    ("sector_membership", "sw2021_industry_membership"),
    ("sector_strength", "daily_return_turnover_amplitude"),
)
LIVERMORE_OUTPUT_KEYS: tuple[str, ...] = (
    "market_gate",
    "sector_rank",
    "stock_candidates",
    "uptrend_momentum_candidates",
    "fresh_trend_watchlist",
    "mean_reversion_candidates",
    "factor_screen_candidates",
    "theme_breakout",
    "hybrid_fusion",
    "risk_exit",
)
STOCK_MODULE_FRESHNESS_THRESHOLD_DAYS = 3
STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD = 0.8
STOCK_MODULE_PARTIAL_COVERAGE_THRESHOLD = 0.5
INPUT_FRESHNESS_DEGRADED_DIAGNOSTIC_CODE = "LIVERMORE_INPUT_FRESHNESS_DEGRADED"
INPUT_FRESHNESS_LOOK_AHEAD_STATUS = "look_ahead"
INPUT_FRESHNESS_DEGRADED_TIERS = frozenset({FRESHNESS_TIER_STALE, FRESHNESS_TIER_EXPIRED})
_INPUT_FRESHNESS_TIER_RANK = {
    FRESHNESS_TIER_EXPIRED: 3,
    FRESHNESS_TIER_STALE: 2,
    FRESHNESS_TIER_FRESH: 1,
}
# Cycle-input families forwarded into the market-gate macro_context disclosure block.
_MACRO_CONTEXT_INPUT_FAMILIES = frozenset({"PMI", "credit_impulse", "price_spread"})
_INPUT_FRESHNESS_NOTE_CATEGORY_BY_FAMILY = {
    "PMI": "宏观输入",
    "credit_impulse": "宏观输入",
    "price_spread": "宏观输入",
    "turnover_persistence": "股票日线输入",
    "valuation_percentile_history": "因子快照输入",
}


def livermore_strategy_envelope(
    *,
    duckdb_path: str,
    as_of_date: str | None = None,
    stock_readiness: ChoiceStockReadiness | None = None,
    stock_candidate_policy: str | None = None,
    theme_overlay_reader: StockAnalysisThemeOverlayReader | None = None,
) -> dict[str, object]:
    requested_date = _parse_optional_date(as_of_date)
    payload, meta = load_livermore_strategy_payload(
        duckdb_path=duckdb_path,
        as_of_date=requested_date,
        stock_readiness=stock_readiness,
        stock_candidate_policy=stock_candidate_policy,
        theme_overlay_reader=theme_overlay_reader,
    )
    filters_applied = {
        "requested_as_of_date": None if requested_date is None else requested_date.isoformat(),
        "as_of_date": payload["as_of_date"],
        "stock_candidate_policy": stock_candidate_policy or EXECUTION_STOCK_CANDIDATE_POLICY,
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=cast(str, meta["source_version"]),
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, meta["quality_flag"]),
        vendor_version=cast(str, meta["vendor_version"]),
        vendor_status=cast(VendorStatus, meta["vendor_status"]),
        fallback_mode=cast(FallbackMode, meta["fallback_mode"]),
        filters_applied=filters_applied,
        tables_used=cast(list[str], meta["tables_used"]),
        evidence_rows=cast(int, meta["evidence_rows"]),
        result_payload=payload,
    )


def livermore_strategy_envelope_from_catalog(
    *,
    duckdb_path: str,
    choice_stock_catalog_file: str | Path,
    as_of_date: str | None = None,
    stock_candidate_policy: str | None = None,
    theme_overlay_reader: StockAnalysisThemeOverlayReader | None = None,
) -> dict[str, object]:
    strategy_kwargs: dict[str, object] = {
        "duckdb_path": duckdb_path,
        "as_of_date": as_of_date,
        "stock_readiness": load_choice_stock_readiness(choice_stock_catalog_file),
        "stock_candidate_policy": stock_candidate_policy,
    }
    if theme_overlay_reader is not None:
        strategy_kwargs["theme_overlay_reader"] = theme_overlay_reader
    return livermore_strategy_envelope(**strategy_kwargs)


def load_livermore_strategy_payload(
    *,
    duckdb_path: str,
    as_of_date: date | None,
    stock_readiness: ChoiceStockReadiness | None = None,
    backfill_mode: bool = False,
    stock_candidate_policy: str | None = None,
    theme_overlay_reader: StockAnalysisThemeOverlayReader | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    resolved_stock_readiness = stock_readiness or choice_stock_readiness_missing("")
    theme_overlay_fingerprint = (
        theme_overlay_reader.fingerprint(backfill_mode=backfill_mode)
        if theme_overlay_reader is not None
        else "theme-overlay-reader:not-configured"
    )
    cache_key = _livermore_strategy_payload_cache_key(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        stock_readiness=resolved_stock_readiness,
        backfill_mode=backfill_mode,
        stock_candidate_policy=stock_candidate_policy,
        theme_overlay_fingerprint=theme_overlay_fingerprint,
    )
    if cache_key is not None:
        cache = get_runtime_cache(
            PAYLOAD_CACHE_NAME,
            ttl_seconds=PAYLOAD_CACHE_TTL_SECONDS,
        )
        return cache.get_or_set(
            cache_key,
            lambda: _load_livermore_strategy_payload_uncached(
                duckdb_path=duckdb_path,
                as_of_date=as_of_date,
                stock_readiness=resolved_stock_readiness,
                backfill_mode=backfill_mode,
                stock_candidate_policy=stock_candidate_policy,
                theme_overlay_reader=theme_overlay_reader,
            ),
        )

    return _load_livermore_strategy_payload_uncached(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        stock_readiness=resolved_stock_readiness,
        backfill_mode=backfill_mode,
        stock_candidate_policy=stock_candidate_policy,
        theme_overlay_reader=theme_overlay_reader,
    )


def _load_livermore_strategy_payload_uncached(
    *,
    duckdb_path: str,
    as_of_date: date | None,
    stock_readiness: ChoiceStockReadiness,
    backfill_mode: bool,
    stock_candidate_policy: str | None,
    theme_overlay_reader: StockAnalysisThemeOverlayReader | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    resolved_stock_readiness = stock_readiness
    # Reuse one read-only connection for the macro history + cycle-evidence
    # loaders instead of opening the DuckDB file once per loader.
    with _shared_read_only_connection(duckdb_path) as shared_conn:
        history_rows, broad_index_tables = _load_broad_index_history(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            conn=shared_conn,
        )
        latest_trade_date: date | None = history_rows[-1].trade_date if history_rows else None
        cycle_input_evidence = _load_cycle_input_evidence(
            duckdb_path=duckdb_path,
            as_of_date=latest_trade_date,
            conn=shared_conn,
        )
    supplement: MarketGateSupplement | None = None
    if latest_trade_date is not None:
        supplement = fetch_market_gate_supplement(duckdb_path=duckdb_path, trade_date=latest_trade_date)

    market_gate = evaluate_market_gate(cast(list[BroadIndexObservation], history_rows), supplement=supplement)
    market_gate = apply_macro_gate_overlay(
        market_gate,
        gate_as_of_date=latest_trade_date.isoformat() if latest_trade_date is not None else None,
        macro=MacroCycleObservation(
            macro_score=cycle_input_evidence.macro_score,
            component_dates=tuple(
                row for row in cycle_input_evidence.input_business_dates if row[0] in _MACRO_CONTEXT_INPUT_FAMILIES
            ),
            evidence=cycle_input_evidence.macro_score_evidence,
        ),
    )
    requested_text = None if as_of_date is None else as_of_date.isoformat()
    resolved_as_of_date = history_rows[-1].trade_date.isoformat() if history_rows else None
    effective_as_of_date = resolved_as_of_date or requested_text
    theme_overlay_result = (
        theme_overlay_reader.read(
            requested_as_of_date=requested_text,
            effective_as_of_date=resolved_as_of_date,
            backfill_mode=backfill_mode,
        )
        if theme_overlay_reader is not None
        else None
    )
    stock_outputs = _load_choice_stock_outputs(
        duckdb_path=duckdb_path,
        as_of_date=effective_as_of_date,
        market_state=str(market_gate["state"]),
        stock_readiness=resolved_stock_readiness,
        backfill_mode=backfill_mode,
        stock_candidate_policy=stock_candidate_policy,
        macro_score=cycle_input_evidence.macro_score,
        theme_overlay_result=theme_overlay_result,
    )
    diagnostics = _build_diagnostics(
        requested_as_of_date=requested_text,
        resolved_as_of_date=resolved_as_of_date,
        market_gate=market_gate,
        history_count=len(history_rows),
        stock_readiness=resolved_stock_readiness,
        stock_outputs=stock_outputs,
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    data_gaps = _build_data_gaps(
        market_gate=market_gate,
        history_count=len(history_rows),
        resolved_as_of_date=resolved_as_of_date,
        stock_readiness=resolved_stock_readiness,
        stock_outputs=stock_outputs,
        cycle_input_evidence=cycle_input_evidence,
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    input_freshness = _assess_input_freshness(
        cycle_input_evidence=cycle_input_evidence,
        as_of_date=latest_trade_date,
    )
    _merge_input_freshness_into_data_gaps(
        data_gaps=cast(list[dict[str, object]], data_gaps),
        input_freshness=input_freshness,
    )
    diagnostics.extend(_input_freshness_degradation_notes(input_freshness))
    rule_readiness = _build_rule_readiness(
        market_gate=market_gate,
        history_count=len(history_rows),
        stock_readiness=resolved_stock_readiness,
        stock_outputs=stock_outputs,
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    supported_outputs, unsupported_outputs = _build_supported_outputs(
        str(market_gate["state"]),
        stock_readiness=resolved_stock_readiness,
        stock_outputs=stock_outputs,
    )
    module_states = _build_module_states(
        page_as_of_date=resolved_as_of_date,
        market_dates=[row.trade_date for row in history_rows],
        unsupported_outputs=unsupported_outputs,
        stock_outputs=stock_outputs,
    )
    quality_flag = _degrade_quality_flag_for_input_freshness(
        _quality_flag_for_market_gate(str(market_gate["state"])),
        input_freshness,
    )
    payload: dict[str, object] = {
        "as_of_date": resolved_as_of_date,
        "requested_as_of_date": requested_text,
        "strategy_name": STRATEGY_NAME,
        "basis": "analytical",
        "market_gate": market_gate,
        "rule_readiness": rule_readiness,
        "data_gaps": data_gaps,
        "diagnostics": diagnostics,
        "supported_outputs": supported_outputs,
        "unsupported_outputs": unsupported_outputs,
        "module_states": module_states,
        "cycle_rotation_framework": _build_cycle_rotation_framework(
            market_gate=market_gate,
            stock_outputs=stock_outputs,
            cycle_input_evidence=cycle_input_evidence,
        ),
    }
    if stock_outputs.sector_rank_payload is not None:
        payload["sector_rank"] = stock_outputs.sector_rank_payload
    if stock_outputs.stock_candidates_payload is not None:
        payload["stock_candidates"] = stock_outputs.stock_candidates_payload
    if stock_outputs.uptrend_momentum_payload is not None:
        payload["uptrend_momentum_candidates"] = stock_outputs.uptrend_momentum_payload
    if stock_outputs.fresh_trend_watchlist_payload is not None:
        payload["fresh_trend_watchlist"] = stock_outputs.fresh_trend_watchlist_payload
    if stock_outputs.mean_reversion_payload is not None:
        payload["mean_reversion_candidates"] = stock_outputs.mean_reversion_payload
    if stock_outputs.factor_screen_payload is not None:
        payload["factor_screen_candidates"] = stock_outputs.factor_screen_payload
    if stock_outputs.theme_breakout_payload is not None:
        payload["theme_breakout"] = stock_outputs.theme_breakout_payload
    if stock_outputs.hybrid_fusion_payload is not None:
        payload["hybrid_fusion_candidates"] = stock_outputs.hybrid_fusion_payload
    if stock_outputs.risk_exit_payload is not None:
        payload["risk_exit"] = stock_outputs.risk_exit_payload
    source_versions = [row.source_version for row in history_rows if row.source_version] + stock_outputs.source_versions
    vendor_versions = [row.vendor_version for row in history_rows if row.vendor_version] + stock_outputs.vendor_versions
    tables_used = [*broad_index_tables, *stock_outputs.tables_used]
    if supplement is not None:
        tables_used.append("fact_livermore_gate_supplement_daily")
    tables_used.extend(cycle_input_evidence.tables_used)
    meta: dict[str, object] = {
        "quality_flag": quality_flag,
        "vendor_status": _vendor_status_for_state(str(market_gate["state"])),
        "fallback_mode": "latest_snapshot" if quality_flag == "stale" else "none",
        "source_version": _aggregate_lineage(
            source_versions + list(cycle_input_evidence.source_versions),
            empty_value=EMPTY_SOURCE_VERSION,
        ),
        "vendor_version": _aggregate_lineage(
            vendor_versions + list(cycle_input_evidence.vendor_versions),
            empty_value=EMPTY_VENDOR_VERSION,
        ),
        "tables_used": _unique_preserving_order(tables_used),
        "evidence_rows": len(history_rows) + stock_outputs.evidence_rows + cycle_input_evidence.evidence_rows,
    }
    return payload, meta


def _livermore_strategy_payload_cache_key(
    *,
    duckdb_path: str,
    as_of_date: date | None,
    stock_readiness: ChoiceStockReadiness,
    backfill_mode: bool,
    stock_candidate_policy: str | None,
    theme_overlay_fingerprint: str = "theme-overlay-reader:not-configured",
) -> tuple[object, ...] | None:
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        stat = path.stat()
        resolved_path = str(path.resolve())
    except OSError:
        return None
    readiness_fingerprint = json.dumps(
        stock_readiness.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return (
        resolved_path,
        stat.st_mtime_ns,
        stat.st_size,
        livermore_data_version(duckdb_path),
        as_of_date.isoformat() if as_of_date is not None else "",
        readiness_fingerprint,
        backfill_mode,
        stock_candidate_policy or "",
        theme_overlay_fingerprint,
        livermore_business_inputs_version(),
        RULE_VERSION,
    )


def _parse_optional_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(str(value))


@contextmanager
def _shared_read_only_connection(duckdb_path: str) -> Iterator[duckdb.DuckDBPyConnection | None]:
    """Open one read-only connection for a request and reuse it across loaders.

    Yields ``None`` (instead of raising) when the file is missing or cannot be
    opened, so each loader can fall back to its own connection or degrade to an
    empty result. The connection closes when the ``with`` block exits, keeping
    the file-lock window short for separate writer processes.
    """
    path = Path(duckdb_path)
    if not path.exists():
        yield None
        return
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        yield None
        return
    try:
        yield conn
    finally:
        conn.close()


def _load_broad_index_history(
    *,
    duckdb_path: str,
    as_of_date: date | None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> tuple[list[_LoadedObservation], list[str]]:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return [], []

    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(duckdb_file), read_only=True)
        except duckdb.Error:
            return [], []

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        queries: list[str] = []
        params: list[object] = []
        tables_used: list[str] = []
        date_filter = "and cast(trade_date as date) <= ?" if as_of_date is not None else ""
        if "fact_choice_macro_daily" in tables:
            tables_used.append("fact_choice_macro_daily")
            queries.append(
                f"""
                select
                  cast(trade_date as date) as trade_date,
                  cast(value_numeric as double) as close_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(vendor_version, '') as vendor_version,
                  coalesce(quality_flag, 'ok') as quality_flag,
                  0 as source_rank
                from fact_choice_macro_daily
                where series_id = ?
                  and value_numeric is not null
                  {date_filter}
                """
            )
            params.append(BROAD_INDEX_SERIES_ID)
            if as_of_date is not None:
                params.append(as_of_date.isoformat())
        if "choice_market_snapshot" in tables:
            tables_used.append("choice_market_snapshot")
            queries.append(
                f"""
                select
                  cast(trade_date as date) as trade_date,
                  cast(value_numeric as double) as close_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(vendor_version, '') as vendor_version,
                  'ok' as quality_flag,
                  1 as source_rank
                from choice_market_snapshot
                where series_id = ?
                  and value_numeric is not null
                  {date_filter}
                """
            )
            params.append(BROAD_INDEX_SERIES_ID)
            if as_of_date is not None:
                params.append(as_of_date.isoformat())
        if not queries:
            return [], []
        rows = conn.execute(
            f"""
            with unioned as (
              {" union all ".join(queries)}
            ),
            deduped as (
              select
                trade_date,
                close_value,
                source_version,
                vendor_version,
                quality_flag,
                row_number() over (
                  partition by trade_date
                  order by source_rank asc, source_version desc
                ) as rn
              from unioned
            )
            select
              trade_date,
              close_value,
              source_version,
              vendor_version,
              quality_flag
            from deduped
            where rn = 1
            order by trade_date desc
            limit {HISTORY_LIMIT}
            """,
            params,
        ).fetchall()
    except duckdb.Error:
        return [], tables_used if "tables_used" in locals() else []
    finally:
        if owns_conn:
            conn.close()

    ordered = [
        _LoadedObservation(
            trade_date=row[0],
            close=float(row[1]),
            source_version=str(row[2] or ""),
            vendor_version=str(row[3] or ""),
            quality_flag=str(row[4] or "ok"),
        )
        for row in reversed(rows)
        if row[0] is not None and row[1] is not None
    ]
    return ordered, tables_used


def _latest_common_trade_date_pair(
    left_points: list[tuple[str, float]],
    right_points: list[tuple[str, float]],
) -> tuple[str, float, float] | None:
    """Return (trade_date, left_value, right_value) for the latest trade_date landed in both series.

    Guards against pairing a stale point from one series with a fresher point from the other
    (e.g. lagging PE with the latest CN10Y) when the two series' most recent landed dates differ.
    """
    right_by_date = {trade_date: value for trade_date, value in right_points}
    for trade_date, left_value in sorted(left_points, key=lambda row: row[0], reverse=True):
        if trade_date in right_by_date:
            return trade_date, left_value, right_by_date[trade_date]
    return None


_CYCLE_INPUT_ROW_CONTRACTS: dict[str, tuple[str, str, bool]] = {
    PMI_SERIES_ID: ("monthly", "index", True),
    SOCIAL_FINANCING_YOY_SERIES_ID: ("monthly", "%", True),
    M2_YOY_SERIES_ID: ("monthly", "%", True),
    CSI300_PE_SERIES_ID: ("daily", "x", False),
    CN10Y_SERIES_ID: ("daily", "%", False),
}
_BACKFILL_RUN_ID_PATTERN = re.compile(r"^backfill_macro_v1:(\d{8})T\d{6}Z$")
_OFFICIAL_AVAILABILITY_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "cycle_rotation_macro_official_availability.json"
)
_OFFICIAL_RELEASES_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "cycle_rotation_macro_official_releases.json"
)
_OFFICIAL_AVAILABILITY_MANIFEST_VERSION = "cycle_macro_official_availability.v1"
_OFFICIAL_BACKFILL_RULE_VERSION = "rv_backfill_macro_v1"
_OFFICIAL_MAPPING_VERSION_BY_SOURCE = {
    "nbs_pmi_release": "rv_nbs_pmi_release_v1",
    "pbc_financial_statistics_release": "rv_pbc_financial_statistics_release_v1",
}
_OFFICIAL_VENDOR_VERSION_PATTERN = re.compile(
    r"^vv_backfill_macro_"
    r"(nbs_pmi_release|pbc_financial_statistics_release)_"
    r"\d{8}_([0-9a-f]{16})_[0-9a-f]{16}$"
)
_FULL_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _strict_manifest_date(value: object) -> date | None:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def _strict_manifest_timestamp_date(value: object) -> date | None:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.date()


def _pbc_release_evidence_latest_available_date(
    *,
    releases: list[object],
    series_id: str,
    covered_period_start: date,
    covered_period_end: date,
    artifact_manifest_sha256: str,
    artifact_record: dict[str, object],
) -> date | None:
    if covered_period_start.day != 1 or covered_period_end.day != 1:
        return None
    canonical_artifacts: list[dict[str, str]] = []
    observed_months: list[date] = []
    available_dates: list[date] = []
    for raw in releases:
        if not isinstance(raw, dict):
            continue
        if raw.get("source") != "pbc_financial_statistics_release":
            continue
        if raw.get("series_id") != series_id:
            continue
        report_month = str(raw.get("report_month") or "")
        if re.fullmatch(r"\d{4}-\d{2}", report_month) is None:
            return None
        report_date = _strict_manifest_date(f"{report_month}-01")
        if report_date is None:
            return None
        if not covered_period_start <= report_date <= covered_period_end:
            continue
        release_url = str(raw.get("release_url") or "")
        published_at = str(raw.get("published_at") or "")
        available_at = str(raw.get("available_at") or published_at)
        artifact_sha256 = str(raw.get("artifact_sha256") or "")
        published_date = _strict_manifest_timestamp_date(published_at)
        available_date = _strict_manifest_timestamp_date(available_at)
        if (
            not release_url
            or published_date is None
            or available_date is None
            or available_date < published_date
            or _FULL_SHA256_PATTERN.fullmatch(artifact_sha256) is None
        ):
            return None
        observed_months.append(report_date)
        available_dates.append(available_date)
        canonical_artifacts.append(
            {
                "report_month": report_month,
                "release_url": release_url,
                "published_at": published_at,
                "available_at": available_at,
                "artifact_sha256": artifact_sha256,
            }
        )
    if not canonical_artifacts:
        return None
    canonical_artifacts.sort(key=lambda row: row["report_month"])
    observed_months.sort()
    expected_month_count = (
        (covered_period_end.year - covered_period_start.year) * 12
        + covered_period_end.month
        - covered_period_start.month
        + 1
    )
    if (
        len(set(observed_months)) != len(observed_months)
        or len(observed_months) != expected_month_count
        or observed_months[0] != covered_period_start
        or observed_months[-1] != covered_period_end
    ):
        return None
    artifacts_json = json.dumps(
        canonical_artifacts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected_artifact_manifest_sha256 = hashlib.sha256(
        artifacts_json.encode("utf-8")
    ).hexdigest()
    if artifact_manifest_sha256 != expected_artifact_manifest_sha256:
        return None
    if artifact_record.get("artifact_kind") != "artifact_set_manifest":
        return None
    component_hashes = artifact_record.get("component_artifact_sha256s")
    expected_component_hashes = [row["artifact_sha256"] for row in canonical_artifacts]
    if component_hashes != expected_component_hashes:
        return None
    return max(available_dates)


def _nbs_release_evidence_latest_available_date(
    *,
    releases: list[object],
    series_id: str,
    covered_period_start: date,
    covered_period_end: date,
    artifact_manifest_sha256: str,
    artifact_record: dict[str, object],
) -> date | None:
    matching_releases = [
        row
        for row in releases
        if isinstance(row, dict)
        and row.get("source") == "nbs_pmi_release"
        and row.get("series_id") == series_id
        and row.get("artifact_sha256") == artifact_manifest_sha256
        and row.get("covered_period_start") == covered_period_start.isoformat()
        and row.get("covered_period_end") == covered_period_end.isoformat()
    ]
    if len(matching_releases) != 1:
        return None
    if artifact_record.get("artifact_kind") != "official_release_artifact":
        return None
    release = matching_releases[0]
    published_at = str(release.get("published_at") or "")
    available_at = str(release.get("available_at") or published_at)
    published_date = _strict_manifest_timestamp_date(published_at)
    available_date = _strict_manifest_timestamp_date(available_at)
    if (
        published_date is None
        or available_date is None
        or available_date < published_date
    ):
        return None
    return available_date


def _official_release_evidence_latest_available_date(
    *,
    payload: object,
    source: str,
    series_id: str,
    covered_period_start: date,
    covered_period_end: date,
    artifact_manifest_sha256: str,
    artifact_record: dict[str, object],
) -> date | None:
    if not isinstance(payload, dict):
        return None
    releases = payload.get("releases")
    if not isinstance(releases, list):
        return None
    if source == "pbc_financial_statistics_release":
        return _pbc_release_evidence_latest_available_date(
            releases=releases,
            series_id=series_id,
            covered_period_start=covered_period_start,
            covered_period_end=covered_period_end,
            artifact_manifest_sha256=artifact_manifest_sha256,
            artifact_record=artifact_record,
        )
    if source == "nbs_pmi_release":
        return _nbs_release_evidence_latest_available_date(
            releases=releases,
            series_id=series_id,
            covered_period_start=covered_period_start,
            covered_period_end=covered_period_end,
            artifact_manifest_sha256=artifact_manifest_sha256,
            artifact_record=artifact_record,
        )
    return None


def _official_availability_binding_allows(
    *,
    series_id: str,
    business_date: date,
    vendor_version: object,
    rule_version: object,
    as_of_date: date,
    availability_manifest_path: str | Path | None,
    official_releases_manifest_path: str | Path | None,
) -> bool:
    manifest_path = Path(availability_manifest_path or _OFFICIAL_AVAILABILITY_MANIFEST_PATH)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    releases_manifest_path = Path(
        official_releases_manifest_path or _OFFICIAL_RELEASES_MANIFEST_PATH
    )
    try:
        releases_payload = json.loads(
            releases_manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("manifest_version") != _OFFICIAL_AVAILABILITY_MANIFEST_VERSION:
        return False

    vendor_text = str(vendor_version or "").strip()
    vendor_match = _OFFICIAL_VENDOR_VERSION_PATTERN.fullmatch(vendor_text)
    if vendor_match is None:
        return False
    source = vendor_match.group(1)
    artifact_prefix = vendor_match.group(2)

    bindings = payload.get("bindings")
    if not isinstance(bindings, list):
        return False
    matching_bindings = [
        row
        for row in bindings
        if isinstance(row, dict)
        and row.get("series_id") == series_id
        and row.get("vendor_version") == vendor_text
    ]
    if len(matching_bindings) != 1:
        return False
    binding = matching_bindings[0]
    if binding.get("source") != source:
        return False
    if binding.get("mapping_version") != _OFFICIAL_MAPPING_VERSION_BY_SOURCE[source]:
        return False
    row_rule_version = str(rule_version or "").strip()
    if (
        row_rule_version != _OFFICIAL_BACKFILL_RULE_VERSION
        or binding.get("rule_version") != row_rule_version
    ):
        return False

    artifact_manifest_sha256 = str(binding.get("artifact_manifest_sha256") or "").strip()
    if (
        _FULL_SHA256_PATTERN.fullmatch(artifact_manifest_sha256) is None
        or not artifact_manifest_sha256.startswith(artifact_prefix)
    ):
        return False
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    matching_artifacts = [
        row
        for row in artifacts
        if isinstance(row, dict)
        and row.get("source") == source
        and row.get("artifact_manifest_sha256") == artifact_manifest_sha256
    ]
    if len(matching_artifacts) != 1:
        return False
    artifact_record = matching_artifacts[0]

    covered_period_start = _strict_manifest_date(binding.get("covered_period_start"))
    covered_period_end = _strict_manifest_date(binding.get("covered_period_end"))
    first_usable_trade_date = _strict_manifest_date(binding.get("first_usable_trade_date"))
    if (
        covered_period_start is None
        or covered_period_end is None
        or first_usable_trade_date is None
        or covered_period_start > covered_period_end
        or not covered_period_start <= business_date <= covered_period_end
        or first_usable_trade_date < business_date
        or first_usable_trade_date > as_of_date
    ):
        return False
    latest_official_available_date = _official_release_evidence_latest_available_date(
        payload=releases_payload,
        source=source,
        series_id=series_id,
        covered_period_start=covered_period_start,
        covered_period_end=covered_period_end,
        artifact_manifest_sha256=artifact_manifest_sha256,
        artifact_record=artifact_record,
    )
    if (
        latest_official_available_date is None
        or first_usable_trade_date <= latest_official_available_date
    ):
        return False
    return True


def _cycle_input_row_issue(
    *,
    series_id: str,
    trade_date: object,
    frequency: object,
    unit: object,
    quality_flag: object,
    source_version: object,
    run_id: object,
    as_of_date: date,
    vendor_version: object = "",
    rule_version: object = "",
    availability_manifest_path: str | Path | None = None,
    official_releases_manifest_path: str | Path | None = None,
) -> str | None:
    contract = _CYCLE_INPUT_ROW_CONTRACTS.get(series_id)
    if contract is None:
        return f"{series_id} is not a recognized cycle-input series."
    expected_frequency, expected_unit, requires_availability = contract
    try:
        business_date = date.fromisoformat(str(trade_date)[:10])
    except ValueError:
        return f"{series_id} has an invalid business date."
    if business_date > as_of_date:
        return f"{series_id} business date {business_date.isoformat()} is after evaluation date."
    if str(frequency or "").strip().lower() != expected_frequency:
        return f"{series_id} frequency must be {expected_frequency}."
    if str(unit or "").strip() != expected_unit:
        return f"{series_id} unit must be {expected_unit}."
    if str(quality_flag or "").strip().lower() != "ok":
        return f"{series_id} quality_flag is not ok."
    if not requires_availability:
        return None
    if str(source_version or "").strip() != "backfill_macro_v1":
        return f"{series_id} source_version is not the production macro backfill lineage marker."
    match = _BACKFILL_RUN_ID_PATTERN.fullmatch(str(run_id or "").strip())
    if match is None:
        return f"{series_id} availability date is not proven by materialization run_id."
    try:
        available_date = date.fromisoformat(f"{match.group(1)[:4]}-{match.group(1)[4:6]}-{match.group(1)[6:8]}")
    except ValueError:
        return f"{series_id} availability date in materialization run_id is invalid."
    if available_date > as_of_date:
        if _official_availability_binding_allows(
            series_id=series_id,
            business_date=business_date,
            vendor_version=vendor_version,
            rule_version=rule_version,
            as_of_date=as_of_date,
            availability_manifest_path=availability_manifest_path,
            official_releases_manifest_path=official_releases_manifest_path,
        ):
            return None
        return (
            f"{series_id} availability date {available_date.isoformat()} is after "
            f"evaluation date {as_of_date.isoformat()}."
        )
    return None


def _load_cycle_input_evidence(
    *,
    duckdb_path: str,
    as_of_date: date | None,
    conn: duckdb.DuckDBPyConnection | None = None,
    availability_manifest_path: str | Path | None = None,
    official_releases_manifest_path: str | Path | None = None,
) -> _CycleInputEvidence:
    path = Path(duckdb_path)
    if as_of_date is None or not path.exists():
        return _CycleInputEvidence()
    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            return _CycleInputEvidence()
    tables_used: list[str] = []
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    evidence_rows = 0
    input_business_dates: list[tuple[str, str, str, str]] = []
    pmi_input_evidence = ""
    credit_input_evidence = ""
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        price_spread_evidence = ""
        pe_value: float | None = None
        cn10y_value: float | None = None
        if "fact_choice_macro_daily" in tables:
            price_rows = conn.execute(
                """
                with ranked as (
                  select
                    series_id,
                    trade_date,
                    value_numeric,
                    coalesce(source_version, '') as source_version,
                    coalesce(vendor_version, '') as vendor_version,
                    coalesce(rule_version, '') as rule_version,
                    coalesce(frequency, '') as frequency,
                    coalesce(unit, '') as unit,
                    coalesce(quality_flag, '') as quality_flag,
                    coalesce(run_id, '') as run_id,
                    row_number() over (
                      partition by series_id
                      order by try_cast(trade_date as date) desc
                    ) as rn
                  from fact_choice_macro_daily
                  where series_id in (?, ?, ?, ?, ?)
                    and try_cast(trade_date as date) <= cast(? as date)
                    and value_numeric is not null
                )
                select series_id, trade_date, value_numeric, source_version, vendor_version, rule_version, frequency, unit, quality_flag, run_id
                from ranked
                where rn <= 5
                order by series_id, try_cast(trade_date as date)
                """,
                [
                    CSI300_PE_SERIES_ID,
                    CN10Y_SERIES_ID,
                    PMI_SERIES_ID,
                    SOCIAL_FINANCING_YOY_SERIES_ID,
                    M2_YOY_SERIES_ID,
                    as_of_date.isoformat(),
                ],
            ).fetchall()
            points_by_series: dict[str, list[tuple[str, float]]] = {}
            rejected_by_series: dict[str, list[str]] = {}
            for (
                series_id,
                trade_date,
                value_numeric,
                source_version,
                vendor_version,
                rule_version,
                frequency,
                unit,
                quality_flag,
                run_id,
            ) in price_rows:
                series_key = str(series_id)
                value = _safe_float(value_numeric)
                if value is None or not math.isfinite(value):
                    rejected_by_series.setdefault(series_key, []).append(f"{series_key} value_numeric is not finite.")
                    continue
                issue = _cycle_input_row_issue(
                    series_id=series_key,
                    trade_date=trade_date,
                    frequency=frequency,
                    unit=unit,
                    quality_flag=quality_flag,
                    source_version=source_version,
                    run_id=run_id,
                    as_of_date=as_of_date,
                    vendor_version=vendor_version,
                    rule_version=rule_version,
                    availability_manifest_path=availability_manifest_path,
                    official_releases_manifest_path=official_releases_manifest_path,
                )
                if issue is not None:
                    rejected_by_series.setdefault(series_key, []).append(issue)
                    continue
                points_by_series.setdefault(series_key, []).append((str(trade_date), value))
                if source_version:
                    source_versions.append(str(source_version))
                if vendor_version:
                    vendor_versions.append(str(vendor_version))
                evidence_rows += 1
            tables_used.append("fact_choice_macro_daily")

            pe_points = points_by_series.get(CSI300_PE_SERIES_ID, [])
            cn10y_points = points_by_series.get(CN10Y_SERIES_ID, [])
            aligned_price_spread = _latest_common_trade_date_pair(pe_points, cn10y_points)
            if aligned_price_spread is not None:
                price_spread_trade_date, pe_value, cn10y_value = aligned_price_spread
                if pe_value > 0:
                    earnings_yield = 100.0 / pe_value
                    spread = earnings_yield - cn10y_value
                    price_spread_evidence = (
                        f"{CSI300_PE_SERIES_ID} {pe_value:.2f} and {CN10Y_SERIES_ID} 10Y yield {cn10y_value:.2f}% "
                        f"both landed on trade_date {price_spread_trade_date} "
                        f"(<= {as_of_date.isoformat()}); proxy price_spread is {spread:.2f}ppt."
                    )
            # else: PE and CN10Y have no shared landed trade_date <= as_of_date; leave pe_value/cn10y_value
            # unset so build_cycle_macro_snapshot marks price_spread as missing and reweights, instead of
            # pairing a lagging point from one series with a fresher point from the other.

            pmi_points = points_by_series.get(PMI_SERIES_ID)
            sf_points = points_by_series.get(SOCIAL_FINANCING_YOY_SERIES_ID)
            m2_points = points_by_series.get(M2_YOY_SERIES_ID)
            credit_series_id = SOCIAL_FINANCING_YOY_SERIES_ID
            credit_points = sf_points
            macro_snapshot = build_cycle_macro_snapshot(
                pmi_points=pmi_points,
                social_financing_yoy_points=credit_points,
                credit_impulse_series_id=credit_series_id,
                pe=pe_value,
                cn10y=cn10y_value,
                as_of_date=as_of_date.isoformat(),
            )
            if not macro_snapshot.credit_impulse_ready and m2_points:
                fallback_snapshot = build_cycle_macro_snapshot(
                    pmi_points=pmi_points,
                    social_financing_yoy_points=m2_points,
                    credit_impulse_series_id=M2_YOY_SERIES_ID,
                    pe=pe_value,
                    cn10y=cn10y_value,
                    as_of_date=as_of_date.isoformat(),
                )
                if fallback_snapshot.credit_impulse_ready:
                    macro_snapshot = fallback_snapshot
                    credit_series_id = M2_YOY_SERIES_ID
                    credit_points = m2_points

            for freshness_family, freshness_series_id, freshness_cadence, freshness_points in (
                ("PMI", PMI_SERIES_ID, "monthly", pmi_points),
                ("credit_impulse", credit_series_id, "monthly", credit_points),
                ("price_spread", CSI300_PE_SERIES_ID, "daily", pe_points),
                ("price_spread", CN10Y_SERIES_ID, "daily", cn10y_points),
            ):
                if freshness_points:
                    freshness_date = _cycle_input_freshness_date(
                        str(freshness_points[-1][0])[:10],
                        cadence=freshness_cadence,
                    )
                    input_business_dates.append(
                        (
                            freshness_family,
                            freshness_series_id,
                            freshness_cadence,
                            freshness_date,
                        )
                    )
            if not macro_snapshot.pmi_ready:
                pmi_input_evidence = "; ".join(rejected_by_series.get(PMI_SERIES_ID, []))
            if not macro_snapshot.credit_impulse_ready:
                credit_input_evidence = "; ".join(
                    rejected_by_series.get(SOCIAL_FINANCING_YOY_SERIES_ID, [])
                    + rejected_by_series.get(M2_YOY_SERIES_ID, [])
                )
        else:
            macro_snapshot = build_cycle_macro_snapshot(
                pmi_points=None,
                social_financing_yoy_points=None,
                pe=None,
                cn10y=None,
                as_of_date=as_of_date.isoformat(),
            )

        turnover_ready = False
        turnover_evidence = ""
        if _table_has_columns(conn, "choice_stock_daily_observation", ["trade_date", "stock_code", "turn"]):
            turnover_row = conn.execute(
                """
                select count(*) as row_count, count(distinct stock_code) as stock_count, coalesce(max(source_version), '')
                from choice_stock_daily_observation
                where cast(trade_date as date) <= cast(? as date)
                  and cast(trade_date as date) >= cast(? as date) - interval 20 day
                  and turn is not null
                """,
                [as_of_date.isoformat(), as_of_date.isoformat()],
            ).fetchone()
            row_count = _safe_int(turnover_row[0]) if turnover_row else 0
            stock_count = _safe_int(turnover_row[1]) if turnover_row else 0
            if row_count and row_count > 0:
                turnover_ready = True
                turnover_evidence = (
                    f"choice_stock_daily_observation has {row_count} turn rows for {stock_count or 0} stocks "
                    f"in the 20-day window ending {as_of_date.isoformat()}."
                )
                tables_used.append("choice_stock_daily_observation")
                if turnover_row and turnover_row[2]:
                    source_versions.append(str(turnover_row[2]))
                evidence_rows += int(row_count)

        if _table_has_columns(conn, "choice_stock_daily_observation", ["trade_date"]):
            stock_daily_latest = conn.execute(
                """
                select max(cast(trade_date as date))
                from choice_stock_daily_observation
                where cast(trade_date as date) <= cast(? as date)
                """,
                [as_of_date.isoformat()],
            ).fetchone()
            if stock_daily_latest and stock_daily_latest[0] is not None:
                input_business_dates.append(
                    (
                        "turnover_persistence",
                        "choice_stock_daily_observation",
                        "daily",
                        str(stock_daily_latest[0])[:10],
                    )
                )

        valuation_ready = False
        valuation_evidence = ""
        if _table_has_columns(conn, "choice_stock_factor_snapshot", ["as_of_date", "stock_code", "pe", "pb"]):
            valuation_source_expr = (
                "coalesce(max(source_version), '')"
                if "source_version" in _table_columns(conn, "choice_stock_factor_snapshot")
                else "''"
            )
            valuation_row = conn.execute(
                f"""
                select as_of_date, count(*) as row_count, {valuation_source_expr}
                from choice_stock_factor_snapshot
                where cast(as_of_date as date) <= ?
                  and pe is not null
                  and pb is not null
                group by as_of_date
                order by cast(as_of_date as date) desc
                limit 1
                """,
                [as_of_date.isoformat()],
            ).fetchone()
            if valuation_row:
                if valuation_row[0]:
                    input_business_dates.append(
                        (
                            "valuation_percentile_history",
                            "choice_stock_factor_snapshot",
                            "daily",
                            str(valuation_row[0])[:10],
                        )
                    )
                row_count = _safe_int(valuation_row[1]) or 0
                if row_count > 0:
                    valuation_ready = True
                    valuation_evidence = (
                        f"choice_stock_factor_snapshot has {row_count} PE/PB rows on {valuation_row[0]} "
                        "for valuation percentile proxy history."
                    )
                    tables_used.append("choice_stock_factor_snapshot")
                    if len(valuation_row) > 2 and valuation_row[2]:
                        source_versions.append(str(valuation_row[2]))
                    evidence_rows += row_count

        return _CycleInputEvidence(
            price_spread_ready=macro_snapshot.price_spread_ready,
            price_spread_evidence=price_spread_evidence or macro_snapshot.evidence,
            pmi_ready=macro_snapshot.pmi_ready,
            pmi_evidence=(
                f"PMI {macro_snapshot.pmi_value:.1f} ({PMI_SERIES_ID})"
                if macro_snapshot.pmi_ready and macro_snapshot.pmi_value is not None
                else pmi_input_evidence
            ),
            credit_impulse_ready=macro_snapshot.credit_impulse_ready,
            credit_impulse_evidence=(
                f"credit_impulse {macro_snapshot.credit_impulse_value:+.2f}ppt ({credit_series_id})"
                if macro_snapshot.credit_impulse_ready and macro_snapshot.credit_impulse_value is not None
                else credit_input_evidence
            ),
            macro_score=macro_snapshot.macro_score,
            macro_score_ready=macro_snapshot.macro_score is not None,
            macro_score_evidence=macro_snapshot.evidence,
            macro_snapshot=macro_snapshot,
            turnover_persistence_ready=turnover_ready,
            turnover_persistence_evidence=turnover_evidence,
            valuation_percentile_history_ready=valuation_ready,
            valuation_percentile_history_evidence=valuation_evidence,
            input_business_dates=tuple(input_business_dates),
            tables_used=tuple(_unique_preserving_order(tables_used)),
            source_versions=tuple(_unique_preserving_order(source_versions)),
            vendor_versions=tuple(_unique_preserving_order(vendor_versions)),
            evidence_rows=evidence_rows,
        )
    except duckdb.Error:
        return _CycleInputEvidence()
    finally:
        if owns_conn:
            conn.close()


class _LoadedObservation(BroadIndexObservation):
    pass


@dataclass(frozen=True)
class _ChoiceStockOutputs:
    sector_coverage: ChoiceStockMaterializationCoverage | None
    stock_coverage: ChoiceStockMaterializationCoverage | None
    sector_rank_payload: dict[str, object] | None
    stock_candidates_payload: dict[str, object] | None
    uptrend_momentum_payload: dict[str, object] | None
    fresh_trend_watchlist_payload: dict[str, object] | None
    mean_reversion_payload: dict[str, object] | None
    factor_screen_payload: dict[str, object] | None
    factor_screen_block_reason: str
    theme_breakout_payload: dict[str, object] | None
    hybrid_fusion_payload: dict[str, object] | None
    hybrid_fusion_block_reason: str
    risk_exit_payload: dict[str, object] | None
    risk_exit_block_reason: str
    stock_candidate_block_reason: str
    tables_used: list[str]
    source_versions: list[str]
    vendor_versions: list[str]
    evidence_rows: int


@dataclass(frozen=True)
class _FreshTrendWatchlistLoadResult:
    snapshots: list[FreshTrendWatchlistSnapshot]
    tables_used: list[str]


@dataclass(frozen=True)
class _TradingStockDailyRow:
    stock_code: str
    stock_name: str
    sector_code: str
    sector_name: str
    close_value: object
    low_value: object
    high_value: object
    volume: object
    pctchange: object
    turn: object
    amplitude: object


@dataclass(frozen=True)
class _TradingStockSnapshotInputs:
    current_rows: list[_TradingStockDailyRow]
    history_by_code: dict[str, dict[str, list[object]]]
    concepts_by_code: dict[str, list[object]]
    hlimitedays_by_code: dict[str, object]
    tables_used: list[str]


@dataclass(frozen=True)
class _DualStockHistoryInputs:
    candidate_history_by_code: dict[str, dict[str, list[float]]]
    trading_history_by_code: dict[str, dict[str, list[object]]]


@dataclass(frozen=True)
class _CycleInputEvidence:
    price_spread_ready: bool = False
    price_spread_evidence: str = ""
    pmi_ready: bool = False
    pmi_evidence: str = ""
    credit_impulse_ready: bool = False
    credit_impulse_evidence: str = ""
    macro_score: float | None = None
    macro_score_ready: bool = False
    macro_score_evidence: str = ""
    macro_snapshot: CycleMacroSnapshot | None = None
    turnover_persistence_ready: bool = False
    turnover_persistence_evidence: str = ""
    valuation_percentile_history_ready: bool = False
    valuation_percentile_history_evidence: str = ""
    # (input_family, input_label, cadence, business_date) rows captured from the
    # same trade_date-bounded queries; consumed by _assess_input_freshness.
    input_business_dates: tuple[tuple[str, str, str, str], ...] = ()
    tables_used: tuple[str, ...] = ()
    source_versions: tuple[str, ...] = ()
    vendor_versions: tuple[str, ...] = ()
    evidence_rows: int = 0


@dataclass(frozen=True)
class _ThemeBreakoutEvidenceProvenance:
    concept_date_row_count: int = 0
    concept_matched_row_count: int = 0
    concept_fallback_row_count: int = 0
    movement_date_row_count: int = 0
    movement_matched_row_count: int = 0
    concept_source_kind: str = ""
    overlay_status: str = "not_configured"
    overlay_reason: str = "Current theme overlay reader is not configured."
    overlay_run_id: str = ""
    overlay_source_version: str = ""
    overlay_vendor_version: str = ""
    overlay_source_kind: str = ""
    overlay_member_count: int = 0


@dataclass(frozen=True)
class _FactorScreenLoadResult:
    rows: list[dict[str, object]]
    snapshot_as_of_date: str | None
    tables_used: list[str]
    unavailable_reason: str = ""
    coverage_denominator: int | None = None
    coverage_denominator_as_of_date: str | None = None


def _choice_stock_dependency_summary(
    *,
    stock_readiness: ChoiceStockReadiness,
    families: list[str],
    ready_summary: str,
) -> str:
    if stock_readiness.ready:
        return ready_summary

    relevant = [family for family in families if family in stock_readiness.missing_input_families]
    if not relevant:
        relevant = list(stock_readiness.missing_input_families)
    formatted = ", ".join(relevant) if relevant else "stock input families"
    status_text = "missing" if stock_readiness.status == "missing_catalog" else "incomplete"
    return f"Choice stock catalog is {status_text}; missing or unconfirmed required input families: {formatted}."


def _choice_stock_missing_inputs(*, stock_readiness: ChoiceStockReadiness, families: list[str]) -> list[str]:
    relevant = [family for family in families if family in stock_readiness.missing_input_families]
    return [str(family) for family in relevant] or list(families)


def _load_choice_stock_outputs(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    backfill_mode: bool = False,
    stock_candidate_policy: str | None = None,
    macro_score: float | None = None,
    theme_overlay_result: ThemeOverlayReadResult | None = None,
) -> _ChoiceStockOutputs:
    if not stock_readiness.ready or as_of_date is None:
        return _ChoiceStockOutputs(
            sector_coverage=None,
            stock_coverage=None,
            sector_rank_payload=None,
            stock_candidates_payload=None,
            uptrend_momentum_payload=None,
            fresh_trend_watchlist_payload=None,
            mean_reversion_payload=None,
            factor_screen_payload=None,
            factor_screen_block_reason="choice_stock_factor_snapshot is unavailable because no resolved as_of_date is available.",
            theme_breakout_payload=None,
            hybrid_fusion_payload=None,
            hybrid_fusion_block_reason=(
                "Hybrid fusion requires at least one landed candidate source: "
                "stock_candidates, factor_screen_candidates, or theme_breakout."
            ),
            risk_exit_payload=None,
            risk_exit_block_reason="",
            stock_candidate_block_reason="",
            tables_used=[],
            source_versions=[],
            vendor_versions=[],
            evidence_rows=0,
        )

    if backfill_mode:
        # 回填模式：跳过 audit 表的精确日期检查，直接用最近可用快照
        sector_coverage = ChoiceStockMaterializationCoverage(
            as_of_date=as_of_date,
            full_coverage=True,
            status="ready",
            completed_request_items=[],
            missing_request_items=[],
            message=f"backfill_mode: skipping coverage check for {as_of_date}",
        )
        stock_coverage = sector_coverage
    else:
        sector_coverage = load_choice_stock_materialization_coverage(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            required_items=SECTOR_REQUIRED_ITEMS,
        )
        stock_coverage = load_choice_stock_materialization_coverage(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
        )
    # Reuse one read-only connection for every stock loader in this request
    # instead of opening the DuckDB file once per loader.
    with _shared_read_only_connection(duckdb_path) as stock_conn:
        return _load_choice_stock_outputs_on_conn(
            stock_conn,
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            market_state=market_state,
            stock_readiness=stock_readiness,
            backfill_mode=backfill_mode,
            stock_candidate_policy=stock_candidate_policy,
            macro_score=macro_score,
            theme_overlay_result=theme_overlay_result,
            sector_coverage=sector_coverage,
            stock_coverage=stock_coverage,
        )


def _load_choice_stock_outputs_on_conn(
    stock_conn: duckdb.DuckDBPyConnection | None,
    *,
    duckdb_path: str,
    as_of_date: str,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    backfill_mode: bool,
    stock_candidate_policy: str | None,
    macro_score: float | None,
    sector_coverage: ChoiceStockMaterializationCoverage,
    stock_coverage: ChoiceStockMaterializationCoverage,
    theme_overlay_result: ThemeOverlayReadResult | None = None,
) -> _ChoiceStockOutputs:
    tables_used: list[str] = []
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    evidence_rows = 0
    trading_snapshot_inputs: _TradingStockSnapshotInputs | None = None
    dual_stock_history_inputs: _DualStockHistoryInputs | None = None

    def load_trading_snapshot_inputs(*, load_history: bool) -> _TradingStockSnapshotInputs:
        trading_started = time.perf_counter()
        inputs = _load_trading_stock_snapshot_inputs(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            include_concepts=True,
            include_limit_quality=True,
            load_history=load_history,
            conn=stock_conn,
        )
        logger.info(
            "livermore_stock_loader_timing stage=trading_snapshot_inputs ms=%d rows=%d history_codes=%d",
            int((time.perf_counter() - trading_started) * 1000),
            len(inputs.current_rows),
            len(inputs.history_by_code),
        )
        return inputs

    def shared_trading_snapshot_inputs() -> _TradingStockSnapshotInputs:
        nonlocal trading_snapshot_inputs
        if trading_snapshot_inputs is None:
            trading_snapshot_inputs = load_trading_snapshot_inputs(load_history=True)
        return trading_snapshot_inputs

    sector_rank_payload: dict[str, object] | None = None
    if sector_coverage.full_coverage:
        sector_rows, sector_tables, sector_sources, sector_vendors = _load_sector_rank_inputs(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            conn=stock_conn,
        )
        evidence_rows += len(sector_rows)
        tables_used.extend(sector_tables)
        source_versions.extend(sector_sources)
        vendor_versions.extend(sector_vendors)
        sector_result = compute_sector_rank(as_of_date=as_of_date, rows=sector_rows)
        sector_rank_payload = sector_result.payload if sector_result.ready else None

    stock_candidates_payload: dict[str, object] | None = None
    stock_candidate_block_reason = ""
    resolved_stock_candidate_policy = stock_candidate_policy or EXECUTION_STOCK_CANDIDATE_POLICY
    if (
        stock_coverage.full_coverage
        and sector_rank_payload is not None
        and market_state not in {"NO_DATA", "PENDING_DATA", "STALE"}
    ):
        if not is_stock_candidate_policy_active(
            policy_name=resolved_stock_candidate_policy,
            market_state=market_state,
        ):
            stock_candidate_block_reason = _stock_candidate_policy_inactive_reason(
                policy_name=resolved_stock_candidate_policy,
                market_state=market_state,
            )
        else:
            candidate_history_loader: (
                Callable[
                    [list[str]],
                    dict[str, dict[str, list[float]]] | None,
                ]
                | None
            ) = None
            if stock_conn is not None and market_state in {"WARM", "HOT"}:
                trading_snapshot_inputs = load_trading_snapshot_inputs(load_history=False)
                trading_stock_codes = [
                    row.stock_code for row in trading_snapshot_inputs.current_rows if row.stock_code
                ]
                if trading_stock_codes:

                    def load_shared_history(
                        candidate_stock_codes: list[str],
                    ) -> dict[str, dict[str, list[float]]] | None:
                        nonlocal dual_stock_history_inputs, trading_snapshot_inputs
                        history_started = time.perf_counter()
                        try:
                            dual_stock_history_inputs = _load_dual_stock_history_inputs(
                                conn=stock_conn,
                                as_of_date=as_of_date,
                                candidate_stock_codes=candidate_stock_codes,
                                trading_stock_codes=trading_stock_codes,
                            )
                        except duckdb.Error:
                            logger.exception(
                                "livermore_stock_loader_fallback stage=dual_stock_history_inputs"
                            )
                            return None
                        trading_snapshot_inputs = replace(
                            trading_snapshot_inputs,
                            history_by_code=dual_stock_history_inputs.trading_history_by_code,
                        )
                        logger.info(
                            "livermore_stock_loader_timing stage=dual_stock_history_inputs ms=%d "
                            "candidate_codes=%d trading_codes=%d",
                            int((time.perf_counter() - history_started) * 1000),
                            len(dual_stock_history_inputs.candidate_history_by_code),
                            len(dual_stock_history_inputs.trading_history_by_code),
                        )
                        return dual_stock_history_inputs.candidate_history_by_code

                    candidate_history_loader = load_shared_history
            stock_candidate_started = time.perf_counter()
            snapshots, stock_tables, stock_sources, stock_vendors = _load_stock_candidate_snapshots(
                duckdb_path=duckdb_path,
                as_of_date=as_of_date,
                sector_rank_payload=sector_rank_payload,
                history_loader=candidate_history_loader,
                conn=stock_conn,
            )
            if (
                candidate_history_loader is not None
                and dual_stock_history_inputs is None
                and trading_snapshot_inputs.current_rows
            ):
                trading_snapshot_inputs = None
            logger.info(
                "livermore_stock_loader_timing stage=stock_candidate_snapshots ms=%d rows=%d",
                int((time.perf_counter() - stock_candidate_started) * 1000),
                len(snapshots),
            )
            evidence_rows += len(snapshots)
            tables_used.extend(stock_tables)
            source_versions.extend(stock_sources)
            vendor_versions.extend(stock_vendors)
            if snapshots and not any(_safe_float(snapshot.limit_ratio) is not None for snapshot in snapshots):
                stock_candidate_block_reason = STOCK_CANDIDATE_LIMIT_RATIO_BLOCK_REASON
            else:
                stock_candidates_payload = compute_stock_candidates(
                    as_of_date=as_of_date,
                    market_state=market_state,
                    snapshots=snapshots,
                    include_universe=backfill_mode,
                    policy_name=resolved_stock_candidate_policy,
                ).payload

    uptrend_momentum_payload: dict[str, object] | None = None
    if stock_coverage.full_coverage and market_state in {"WARM", "HOT"}:
        uptrend_snapshots = _uptrend_momentum_snapshots_from_inputs(shared_trading_snapshot_inputs())
        if uptrend_snapshots:
            uptrend_result = compute_uptrend_momentum_candidates(
                as_of_date=as_of_date,
                market_state=market_state,
                snapshots=uptrend_snapshots,
            )
            evidence_rows += len(uptrend_snapshots)
            uptrend_momentum_payload = uptrend_result.payload
            tables_used.extend(
                [
                    "choice_stock_daily_observation",
                    "choice_stock_universe",
                    "choice_stock_sector_membership",
                ]
            )

    fresh_trend_watchlist_payload: dict[str, object] | None = None
    if stock_coverage.full_coverage and market_state in {"WARM", "HOT", "OVERHEAT"}:
        fresh_trend_load = _fresh_trend_watchlist_snapshots_from_inputs(shared_trading_snapshot_inputs())
        if fresh_trend_load.snapshots:
            fresh_trend_result = compute_fresh_trend_watchlist_candidates(
                as_of_date=as_of_date,
                market_state=market_state,
                snapshots=fresh_trend_load.snapshots,
            )
            evidence_rows += len(fresh_trend_load.snapshots)
            fresh_trend_watchlist_payload = fresh_trend_result.payload
            tables_used.extend(fresh_trend_load.tables_used)

    mean_reversion_payload: dict[str, object] | None = None
    if stock_coverage.full_coverage and market_state in {"OFF", "WARM"}:
        mr_snapshots = _mean_reversion_snapshots_from_inputs(shared_trading_snapshot_inputs())
        if mr_snapshots:
            mr_result = compute_mean_reversion_candidates(
                as_of_date=as_of_date,
                market_state=market_state,
                snapshots=mr_snapshots,
            )
            evidence_rows += len(mr_snapshots)
            mean_reversion_payload = mr_result.payload
            tables_used.extend(
                [
                    "choice_stock_daily_observation",
                    "choice_stock_universe",
                    "choice_stock_sector_membership",
                ]
            )

    factor_screen_payload: dict[str, object] | None = None
    factor_screen_block_reason = ""
    factor_load = _load_factor_screen_rows(duckdb_path=duckdb_path, as_of_date=as_of_date, conn=stock_conn)
    if factor_load.rows and factor_load.snapshot_as_of_date is not None:
        fs_result = compute_factor_screen_candidates(
            as_of_date=factor_load.snapshot_as_of_date,
            market_state=market_state,
            rows=factor_load.rows,
        )
        factor_screen_payload = {
            **fs_result.payload,
            "factor_snapshot_as_of_date": factor_load.snapshot_as_of_date,
            "observation_only": True,
            "coverage_count": len(factor_load.rows),
            "coverage_denominator": factor_load.coverage_denominator,
            "coverage_denominator_as_of_date": factor_load.coverage_denominator_as_of_date,
            "coverage_ratio": _coverage_ratio(len(factor_load.rows), factor_load.coverage_denominator),
            "coverage_threshold": STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD,
        }
        tables_used.extend(factor_load.tables_used)
        evidence_rows += len(factor_load.rows)
    else:
        factor_screen_block_reason = factor_load.unavailable_reason

    theme_breakout_payload: dict[str, object] | None = None
    if (
        stock_coverage.full_coverage
        and sector_rank_payload is not None
        and market_state not in {"NO_DATA", "PENDING_DATA", "STALE", "OVERHEAT"}
    ):
        theme_snapshots, theme_tables, theme_sources, theme_vendors, theme_provenance = _load_theme_breakout_snapshots(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            sector_rank_payload=sector_rank_payload,
            conn=stock_conn,
            theme_overlay_result=theme_overlay_result,
        )
        evidence_rows += len(theme_snapshots)
        tables_used.extend(theme_tables)
        source_versions.extend(theme_sources)
        vendor_versions.extend(theme_vendors)
        theme_breakout_payload = {
            **compute_theme_breakout(
                as_of_date=as_of_date,
                snapshots=theme_snapshots,
            ).payload,
            "evidence_state": _build_theme_breakout_evidence_state(
                stock_readiness=stock_readiness,
                tables_used=theme_tables,
                provenance=theme_provenance,
            ),
        }

    hybrid_fusion_payload: dict[str, object] | None = None
    hybrid_fusion_block_reason = _hybrid_fusion_unavailable_reason_from_payloads(
        market_state=market_state,
        stock_candidates_payload=stock_candidates_payload,
        factor_screen_payload=factor_screen_payload,
        theme_breakout_payload=theme_breakout_payload,
    )
    if _has_hybrid_fusion_candidate_source(
        stock_candidates_payload=stock_candidates_payload,
        factor_screen_payload=factor_screen_payload,
        theme_breakout_payload=theme_breakout_payload,
    ):
        hybrid_fusion_payload = compute_hybrid_fusion_candidates(
            as_of_date=as_of_date,
            market_state=market_state,
            sector_rank_payload=sector_rank_payload,
            stock_candidates_payload=stock_candidates_payload,
            factor_screen_payload=factor_screen_payload,
            theme_breakout_payload=theme_breakout_payload,
            macro_score=macro_score,
            thresholds=load_hybrid_fusion_thresholds(),
        ).payload

    risk_exit_payload: dict[str, object] | None = None
    risk_exit_block_reason = ""
    if stock_coverage.full_coverage:
        risk_snapshots, risk_tables, risk_sources, risk_vendors = _load_risk_exit_snapshots(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            conn=stock_conn,
        )
        if risk_snapshots:
            evidence_rows += len(risk_snapshots)
            tables_used.extend(risk_tables)
            source_versions.extend(risk_sources)
            vendor_versions.extend(risk_vendors)
            risk_exit_payload = compute_risk_exit(
                as_of_date=as_of_date,
                snapshots=risk_snapshots,
            ).payload
        else:
            risk_exit_block_reason = _risk_exit_input_block_reason(
                duckdb_path=duckdb_path,
                as_of_date=as_of_date,
                conn=stock_conn,
            )

    return _ChoiceStockOutputs(
        sector_coverage=sector_coverage,
        stock_coverage=stock_coverage,
        sector_rank_payload=sector_rank_payload,
        stock_candidates_payload=stock_candidates_payload,
        uptrend_momentum_payload=uptrend_momentum_payload,
        fresh_trend_watchlist_payload=fresh_trend_watchlist_payload,
        mean_reversion_payload=mean_reversion_payload,
        factor_screen_payload=factor_screen_payload,
        factor_screen_block_reason=factor_screen_block_reason,
        theme_breakout_payload=theme_breakout_payload,
        hybrid_fusion_payload=hybrid_fusion_payload,
        hybrid_fusion_block_reason=hybrid_fusion_block_reason,
        risk_exit_payload=risk_exit_payload,
        risk_exit_block_reason=risk_exit_block_reason,
        stock_candidate_block_reason=stock_candidate_block_reason,
        tables_used=_unique_preserving_order(tables_used),
        source_versions=source_versions,
        vendor_versions=vendor_versions,
        evidence_rows=evidence_rows,
    )


def _load_sector_rank_inputs(
    *,
    duckdb_path: str,
    as_of_date: str,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> tuple[list[SectorRankConstituent], list[str], list[str], list[str]]:
    path = Path(duckdb_path)
    if not path.exists():
        return [], [], [], []
    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            return [], [], [], []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {"choice_stock_sector_membership", "choice_stock_daily_observation"}
        if not required_tables.issubset(tables):
            return [], [], [], []
        membership_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_sector_membership",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        if membership_snapshot_date is None:
            return [], list(required_tables), [], []
        universe_snapshot_date = None
        if "choice_stock_universe" in tables:
            universe_snapshot_date = _latest_table_date_on_or_before(
                conn,
                table_name="choice_stock_universe",
                column_name="as_of_date",
                as_of_date=as_of_date,
            )
        stock_name_expr = (
            "coalesce(universe.stock_name, membership.stock_code)"
            if universe_snapshot_date is not None
            else "membership.stock_code"
        )
        universe_join = (
            """
            left join choice_stock_universe universe
              on universe.stock_code = membership.stock_code
             and universe.as_of_date = ?
            """
            if universe_snapshot_date is not None
            else ""
        )
        params: list[object] = [as_of_date]
        if universe_snapshot_date is not None:
            params.append(universe_snapshot_date)
        params.append(membership_snapshot_date)
        rows = conn.execute(
            f"""
            select
              membership.stock_code,
              {stock_name_expr} as stock_name,
              membership.sw2021code,
              membership.sw2021,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              daily.vendor_version
            from choice_stock_sector_membership membership
            join choice_stock_daily_observation daily
              on daily.stock_code = membership.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            {universe_join}
            where membership.as_of_date = ?
            """,
            params,
        ).fetchall()
    except duckdb.Error:
        return [], ["choice_stock_sector_membership", "choice_stock_daily_observation"], [], []
    finally:
        if owns_conn:
            conn.close()

    constituents = [
        SectorRankConstituent(
            stock_code=str(row[0] or ""),
            sector_code=str(row[2] or ""),
            sector_name=str(row[3] or ""),
            pctchange=row[4],
            turn=row[5],
            amplitude=row[6],
            stock_name=str(row[1] or ""),
        )
        for row in rows
    ]
    source_versions = [str(value) for row in rows for value in (row[7], row[9]) if value]
    vendor_versions = [str(value) for row in rows for value in (row[8], row[10]) if value]
    tables_used = ["choice_stock_sector_membership", "choice_stock_daily_observation"]
    if universe_snapshot_date is not None:
        tables_used.append("choice_stock_universe")
    return constituents, tables_used, source_versions, vendor_versions


def _load_dual_stock_history_inputs(
    *,
    conn: duckdb.DuckDBPyConnection,
    as_of_date: str,
    candidate_stock_codes: list[str],
    trading_stock_codes: list[str],
) -> _DualStockHistoryInputs:
    target_flags: dict[str, list[bool]] = {}
    for stock_code in candidate_stock_codes:
        normalized = str(stock_code or "").strip()
        if normalized:
            target_flags.setdefault(normalized, [False, False])[0] = True
    for stock_code in trading_stock_codes:
        normalized = str(stock_code or "").strip()
        if normalized:
            target_flags.setdefault(normalized, [False, False])[1] = True
    if not target_flags:
        return _DualStockHistoryInputs(
            candidate_history_by_code={},
            trading_history_by_code={},
        )

    target_values = ",".join("(?, ?, ?)" for _ in target_flags)
    params: list[object] = []
    for stock_code, (want_candidate, want_trading) in target_flags.items():
        params.extend([stock_code, want_candidate, want_trading])
    params.extend(
        [
            as_of_date,
            CHOICE_STOCK_HISTORY_WINDOW,
            CHOICE_STOCK_HISTORY_WINDOW,
        ]
    )
    rows = conn.execute(
        f"""
        with targets(stock_code, want_candidate, want_trading) as (
          values {target_values}
        ),
        ranked_history as (
          select
            daily.stock_code,
            daily.close_value,
            daily.turn,
            daily.amount,
            daily.volume,
            targets.want_candidate,
            targets.want_trading,
            trim(coalesce(daily.tradestatus, '')) = 'Trading' as is_trading,
            row_number() over (
              partition by daily.stock_code
              order by cast(daily.trade_date as date) desc
            ) as candidate_rn,
            count(*) filter (
              where trim(coalesce(daily.tradestatus, '')) = 'Trading'
            ) over (
              partition by daily.stock_code
              order by cast(daily.trade_date as date) desc
              rows between unbounded preceding and current row
            ) as trading_rn
          from choice_stock_daily_observation daily
          join targets on targets.stock_code = daily.stock_code
          where cast(daily.trade_date as date) <= cast(? as date)
        )
        select
          stock_code,
          close_value,
          turn,
          amount,
          volume,
          want_candidate,
          want_trading,
          is_trading,
          candidate_rn,
          trading_rn
        from ranked_history
        where (want_candidate and candidate_rn <= ?)
           or (want_trading and is_trading and trading_rn <= ?)
        """,
        params,
    ).fetchall()

    candidate_ranked: dict[str, list[tuple[int, float, float]]] = {}
    trading_ranked: dict[str, list[tuple[int, object, object, object]]] = {}
    for row in rows:
        stock_code = str(row[0] or "")
        if not stock_code:
            continue
        if bool(row[5]) and int(row[8]) <= CHOICE_STOCK_HISTORY_WINDOW:
            close_value = _safe_float(row[1])
            turn_value = _safe_float(row[2])
            if close_value is not None and turn_value is not None:
                candidate_ranked.setdefault(stock_code, []).append(
                    (int(row[8]), close_value, turn_value)
                )
        if (
            bool(row[6])
            and bool(row[7])
            and int(row[9]) <= CHOICE_STOCK_HISTORY_WINDOW
        ):
            trading_ranked.setdefault(stock_code, []).append(
                (int(row[9]), row[1], row[3], row[4])
            )

    candidate_history_by_code: dict[str, dict[str, list[float]]] = {}
    for stock_code, ranked_rows in candidate_ranked.items():
        ranked_rows.sort(key=lambda item: item[0], reverse=True)
        candidate_history_by_code[stock_code] = {
            "close": [item[1] for item in ranked_rows],
            "turn": [item[2] for item in ranked_rows],
        }
    trading_history_by_code: dict[str, dict[str, list[object]]] = {}
    for stock_code, ranked_rows in trading_ranked.items():
        ranked_rows.sort(key=lambda item: item[0], reverse=True)
        trading_history_by_code[stock_code] = {
            "close": [item[1] for item in ranked_rows],
            "amount": [item[2] for item in ranked_rows],
            "volume": [item[3] for item in ranked_rows],
        }
    return _DualStockHistoryInputs(
        candidate_history_by_code=candidate_history_by_code,
        trading_history_by_code=trading_history_by_code,
    )


def _load_stock_candidate_snapshots(
    *,
    duckdb_path: str,
    as_of_date: str,
    sector_rank_payload: dict[str, object],
    history_loader: (
        Callable[[list[str]], dict[str, dict[str, list[float]]] | None] | None
    ) = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> tuple[list[StockCandidateSnapshot], list[str], list[str], list[str]]:
    path = Path(duckdb_path)
    if not path.exists():
        return [], [], [], []
    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            return [], [], [], []
    history_rows: list[tuple[object, ...]] = []
    history_by_code: dict[str, dict[str, list[float]]] | None = None
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {
            "choice_stock_universe",
            "choice_stock_sector_membership",
            "choice_stock_daily_observation",
            "choice_stock_limit_quality",
        }
        if not required_tables.issubset(tables):
            return [], [], [], []
        universe_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_universe",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        membership_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_sector_membership",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        limit_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_limit_quality",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        if universe_snapshot_date is None or membership_snapshot_date is None or limit_snapshot_date is None:
            return [], list(required_tables), [], []
        factor_columns = [
            "as_of_date",
            "stock_code",
            "pe",
            "pb",
            "ps",
            "roe",
            "gross_margin",
            "three_month_return",
            "twelve_month_return",
            "volatility",
            "dividend_yield",
        ]
        factor_snapshot_date: str | None = None
        if "choice_stock_factor_snapshot" in tables and _table_has_columns(
            conn,
            "choice_stock_factor_snapshot",
            factor_columns,
        ):
            latest_factor = conn.execute(
                """
                select max(as_of_date)
                from choice_stock_factor_snapshot
                where as_of_date <= ?
                """,
                [as_of_date],
            ).fetchone()
            if latest_factor and latest_factor[0]:
                factor_snapshot_date = str(latest_factor[0])
        factor_select = (
            """
              f.pe,
              f.pb,
              f.ps,
              f.roe,
              f.gross_margin,
              f.three_month_return,
              f.twelve_month_return,
              f.volatility,
              f.dividend_yield
            """
            if factor_snapshot_date is not None
            else """
              null as pe,
              null as pb,
              null as ps,
              null as roe,
              null as gross_margin,
              null as three_month_return,
              null as twelve_month_return,
              null as volatility,
              null as dividend_yield
            """
        )
        factor_join = (
            """
            left join choice_stock_factor_snapshot f
              on f.stock_code = universe.stock_code
             and f.as_of_date = ?
            """
            if factor_snapshot_date is not None
            else ""
        )
        daily_amount_select = (
            "daily.amount"
            if _table_has_columns(conn, "choice_stock_daily_observation", ["amount"])
            else "cast(null as double) as amount"
        )
        params: list[object] = [membership_snapshot_date, as_of_date, limit_snapshot_date]
        if factor_snapshot_date is not None:
            params.append(factor_snapshot_date)
        params.append(universe_snapshot_date)
        current_rows = conn.execute(
            f"""
            select
              universe.stock_code,
              universe.stock_name,
              membership.sw2021code,
              membership.sw2021,
              daily.open_value,
              daily.high_value,
              daily.low_value,
              daily.close_value,
              daily.turn,
              daily.highlimit,
              daily.lowlimit,
              limits.issurgedlimit,
              universe.source_version,
              universe.vendor_version,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              daily.vendor_version,
              limits.source_version,
              limits.vendor_version,
              {factor_select},
              {daily_amount_select}
            from choice_stock_universe universe
            join choice_stock_sector_membership membership
              on membership.stock_code = universe.stock_code
             and membership.as_of_date = ?
            join choice_stock_daily_observation daily
              on daily.stock_code = universe.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            join choice_stock_limit_quality limits
              on limits.stock_code = universe.stock_code
             and limits.as_of_date = ?
            {factor_join}
            where universe.as_of_date = ?
            """,
            params,
        ).fetchall()
        stock_codes = [str(row[0]) for row in current_rows if row[0]]
        if not stock_codes:
            return [], list(required_tables), [], []
        placeholders = ",".join("?" for _ in stock_codes)
        loaded_history = history_loader(stock_codes) if history_loader is not None else None
        if loaded_history is None:
            history_rows = conn.execute(
                f"""
                with ranked_history as (
                  select
                    stock_code,
                    close_value,
                    turn,
                    row_number() over (
                      partition by stock_code
                      order by cast(trade_date as date) desc
                    ) as rn
                  from choice_stock_daily_observation
                  where stock_code in ({placeholders})
                    and cast(trade_date as date) <= cast(? as date)
                )
                select stock_code, close_value, turn
                from ranked_history
                where rn <= ?
                order by stock_code asc, rn desc
                """,
                [*stock_codes, as_of_date, CHOICE_STOCK_HISTORY_WINDOW],
            ).fetchall()
        else:
            history_by_code = loaded_history
    except duckdb.Error:
        return [], list(required_tables), [], []
    finally:
        if owns_conn:
            conn.close()

    if history_by_code is None:
        history_by_code = {}
        for row in history_rows:
            stock_code = str(row[0] or "")
            close_value = _safe_float(row[1])
            turn_value = _safe_float(row[2])
            if not stock_code or close_value is None or turn_value is None:
                continue
            history = history_by_code.setdefault(stock_code, {"close": [], "turn": []})
            history["close"].append(close_value)
            history["turn"].append(turn_value)

    sector_rank_by_key: dict[tuple[str, str], int] = {}
    for item in cast(list[dict[str, object]], sector_rank_payload["items"]):
        rank = _safe_int(item.get("rank"))
        if rank is None:
            continue
        sector_rank_by_key[(str(item["sector_code"]), str(item["sector_name"]))] = rank
    snapshots: list[StockCandidateSnapshot] = []
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    for row in current_rows:
        stock_code = str(row[0] or "")
        sector_code = str(row[2] or "")
        sector_name = str(row[3] or "")
        history = history_by_code.get(stock_code, {"close": [], "turn": []})
        prior_close = history["close"][-2] if len(history["close"]) >= 2 else None
        stock_name = str(row[1] or "")
        limit_ratio = _limit_ratio(
            highlimit=row[9],
            lowlimit=row[10],
            prior_close=prior_close,
            stock_code=stock_code,
            stock_name=stock_name,
            as_of_date=as_of_date,
        )
        open_value = _safe_float(row[4])
        high_value = _safe_float(row[5])
        low_value = _safe_float(row[6])
        close_value = _safe_float(row[7])
        one_word_board = (
            open_value is not None
            and high_value is not None
            and low_value is not None
            and close_value is not None
            and abs(open_value - high_value) < 1e-9
            and abs(high_value - low_value) < 1e-9
            and abs(low_value - close_value) < 1e-9
        )
        highlimit = _safe_float(row[9])
        closed_up_limit = bool(
            _truthy(row[11]) and highlimit is not None and close_value is not None and close_value >= highlimit - 1e-9
        )
        snapshots.append(
            StockCandidateSnapshot(
                stock_code=stock_code,
                stock_name=stock_name,
                sector_code=sector_code,
                sector_name=sector_name,
                sector_rank=sector_rank_by_key.get((sector_code, sector_name)),
                open_value=row[4],
                high_value=row[5],
                low_value=row[6],
                close_value=row[7],
                turnover_free=row[8],
                limit_ratio=limit_ratio,
                daily_amount=row[29],
                one_word_board=one_word_board,
                closed_up_limit=closed_up_limit,
                close_history=history["close"],
                turnover_history=history["turn"],
                pe=row[20],
                pb=row[21],
                ps=row[22],
                roe=row[23],
                gross_margin=row[24],
                three_month_return=row[25],
                twelve_month_return=row[26],
                volatility=row[27],
                dividend_yield=row[28],
            )
        )
        source_versions.extend(str(value) for value in (row[12], row[14], row[16], row[18]) if value)
        vendor_versions.extend(str(value) for value in (row[13], row[15], row[17], row[19]) if value)

    tables_used = [
        "choice_stock_universe",
        "choice_stock_sector_membership",
        "choice_stock_daily_observation",
        "choice_stock_limit_quality",
    ]
    if factor_snapshot_date is not None:
        tables_used.append("choice_stock_factor_snapshot")
    return snapshots, tables_used, source_versions, vendor_versions


def _load_trading_stock_snapshot_inputs(
    *,
    duckdb_path: str,
    as_of_date: str,
    include_concepts: bool = False,
    include_limit_quality: bool = False,
    load_history: bool = True,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> _TradingStockSnapshotInputs:
    empty = _TradingStockSnapshotInputs(
        current_rows=[],
        history_by_code={},
        concepts_by_code={},
        hlimitedays_by_code={},
        tables_used=[],
    )
    path = Path(duckdb_path)
    if not path.exists():
        return empty
    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            return empty
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {
            "choice_stock_universe",
            "choice_stock_sector_membership",
            "choice_stock_daily_observation",
        }
        if not required_tables.issubset(tables):
            return empty
        tables_used = [
            "choice_stock_daily_observation",
            "choice_stock_universe",
            "choice_stock_sector_membership",
        ]
        universe_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_universe",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        membership_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_sector_membership",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        if universe_snapshot_date is None or membership_snapshot_date is None:
            return empty
        current_raw_rows = conn.execute(
            """
            select
              daily.stock_code,
              coalesce(nullif(trim(universe.stock_name), ''), daily.stock_code) as stock_name,
              coalesce(nullif(trim(membership.sw2021code), ''), '') as sector_code,
              coalesce(nullif(trim(membership.sw2021), ''), '') as sector_name,
              daily.close_value,
              daily.low_value,
              daily.high_value,
              daily.volume,
              daily.pctchange,
              daily.turn,
              daily.amplitude
            from choice_stock_daily_observation daily
            left join choice_stock_universe universe
              on universe.stock_code = daily.stock_code
             and universe.as_of_date = ?
            left join choice_stock_sector_membership membership
              on membership.stock_code = daily.stock_code
             and membership.as_of_date = ?
            where cast(daily.trade_date as date) = cast(? as date)
              and trim(coalesce(daily.tradestatus, '')) = 'Trading'
            """,
            [universe_snapshot_date, membership_snapshot_date, as_of_date],
        ).fetchall()
        stock_codes = [str(row[0] or "") for row in current_raw_rows if row[0]]
        if not stock_codes:
            return _TradingStockSnapshotInputs(
                current_rows=[],
                history_by_code={},
                concepts_by_code={},
                hlimitedays_by_code={},
                tables_used=tables_used,
            )
        placeholders = ",".join("?" for _ in stock_codes)
        history_rows = []
        if load_history:
            history_rows = conn.execute(
                f"""
                with ranked_history as (
                  select
                    stock_code,
                    close_value,
                    amount,
                    volume,
                    row_number() over (
                      partition by stock_code
                      order by cast(trade_date as date) desc
                    ) as rn
                  from choice_stock_daily_observation
                  where stock_code in ({placeholders})
                    and cast(trade_date as date) <= cast(? as date)
                    and trim(coalesce(tradestatus, '')) = 'Trading'
                )
                select stock_code, close_value, amount, volume
                from ranked_history
                where rn <= ?
                order by stock_code asc, rn desc
                """,
                [*stock_codes, as_of_date, CHOICE_STOCK_HISTORY_WINDOW],
            ).fetchall()
        concept_rows: list[tuple[object, object]] = []
        if include_concepts and "choice_stock_concept_membership" in tables:
            concept_snapshot_date = _latest_table_date_on_or_before(
                conn,
                table_name="choice_stock_concept_membership",
                column_name="as_of_date",
                as_of_date=as_of_date,
            )
            if concept_snapshot_date is not None:
                concept_rows = conn.execute(
                    f"""
                    select stock_code, concept_name
                    from choice_stock_concept_membership
                    where stock_code in ({placeholders})
                      and as_of_date = ?
                    order by stock_code asc, concept_name asc
                    """,
                    [*stock_codes, concept_snapshot_date],
                ).fetchall()
                tables_used.append("choice_stock_concept_membership")
        limit_rows: list[tuple[object, object]] = []
        if include_limit_quality and "choice_stock_limit_quality" in tables:
            limit_snapshot_date = _latest_table_date_on_or_before(
                conn,
                table_name="choice_stock_limit_quality",
                column_name="as_of_date",
                as_of_date=as_of_date,
            )
            if limit_snapshot_date is not None:
                limit_rows = conn.execute(
                    f"""
                    select stock_code, hlimitedays
                    from choice_stock_limit_quality
                    where stock_code in ({placeholders})
                      and as_of_date = ?
                    """,
                    [*stock_codes, limit_snapshot_date],
                ).fetchall()
                tables_used.append("choice_stock_limit_quality")
    except duckdb.Error:
        return empty
    finally:
        if owns_conn:
            conn.close()

    history_by_code: dict[str, dict[str, list[object]]] = {}
    for row in history_rows:
        code = str(row[0] or "")
        if not code:
            continue
        bucket = history_by_code.setdefault(code, {"close": [], "amount": [], "volume": []})
        bucket["close"].append(row[1])
        bucket["amount"].append(row[2])
        bucket["volume"].append(row[3])

    concepts_by_code: dict[str, list[object]] = {}
    for code_raw, concept_name in concept_rows:
        code = str(code_raw or "")
        if code:
            concepts_by_code.setdefault(code, []).append(concept_name)

    current_rows = [
        _TradingStockDailyRow(
            stock_code=str(row[0] or ""),
            stock_name=str(row[1] or row[0] or ""),
            sector_code=str(row[2] or ""),
            sector_name=str(row[3] or ""),
            close_value=row[4],
            low_value=row[5],
            high_value=row[6],
            volume=row[7],
            pctchange=row[8],
            turn=row[9],
            amplitude=row[10],
        )
        for row in current_raw_rows
        if row[0]
    ]
    return _TradingStockSnapshotInputs(
        current_rows=current_rows,
        history_by_code=history_by_code,
        concepts_by_code=concepts_by_code,
        hlimitedays_by_code={str(code or ""): hlimitedays for code, hlimitedays in limit_rows if code},
        tables_used=_unique_preserving_order(tables_used),
    )


def _mean_reversion_snapshots_from_inputs(inputs: _TradingStockSnapshotInputs) -> list[MeanReversionSnapshot]:
    snapshots: list[MeanReversionSnapshot] = []
    for row in inputs.current_rows:
        bucket = inputs.history_by_code.get(row.stock_code, {"close": [], "volume": []})
        closes = bucket["close"]
        volumes = bucket["volume"]
        if len(closes) > 65:
            closes = closes[-65:]
            volumes = volumes[-65:]
        if len(closes) != len(volumes):
            continue
        snapshots.append(
            MeanReversionSnapshot(
                stock_code=row.stock_code,
                stock_name=row.stock_name or row.stock_code,
                sector_code=row.sector_code,
                sector_name=row.sector_name,
                close_value=row.close_value,
                low_value=row.low_value,
                high_value=row.high_value,
                volume=row.volume,
                close_history=closes,
                volume_history=volumes,
            )
        )
    return snapshots


def _uptrend_momentum_snapshots_from_inputs(inputs: _TradingStockSnapshotInputs) -> list[UptrendMomentumSnapshot]:
    snapshots: list[UptrendMomentumSnapshot] = []
    for row in inputs.current_rows:
        bucket = inputs.history_by_code.get(row.stock_code, {"close": [], "amount": []})
        closes = bucket["close"]
        amounts = bucket["amount"]
        if len(closes) > CHOICE_STOCK_HISTORY_WINDOW:
            closes = closes[-CHOICE_STOCK_HISTORY_WINDOW:]
            amounts = amounts[-CHOICE_STOCK_HISTORY_WINDOW:]
        if len(closes) != len(amounts):
            continue
        snapshots.append(
            UptrendMomentumSnapshot(
                stock_code=row.stock_code,
                stock_name=row.stock_name or row.stock_code,
                sector_code=row.sector_code,
                sector_name=row.sector_name,
                close_value=row.close_value,
                pctchange=row.pctchange,
                turn=row.turn,
                amplitude=row.amplitude,
                close_history=closes,
                amount_history=amounts,
            )
        )
    return snapshots


def _fresh_trend_watchlist_snapshots_from_inputs(
    inputs: _TradingStockSnapshotInputs,
) -> _FreshTrendWatchlistLoadResult:
    snapshots: list[FreshTrendWatchlistSnapshot] = []
    for row in inputs.current_rows:
        bucket = inputs.history_by_code.get(row.stock_code, {"close": [], "amount": []})
        closes = bucket["close"]
        amounts = bucket["amount"]
        if len(closes) > CHOICE_STOCK_HISTORY_WINDOW:
            closes = closes[-CHOICE_STOCK_HISTORY_WINDOW:]
            amounts = amounts[-CHOICE_STOCK_HISTORY_WINDOW:]
        if len(closes) != len(amounts):
            continue
        snapshots.append(
            FreshTrendWatchlistSnapshot(
                stock_code=row.stock_code,
                stock_name=row.stock_name or row.stock_code,
                sector_code=row.sector_code,
                sector_name=row.sector_name,
                concepts=inputs.concepts_by_code.get(row.stock_code, []),
                close_value=row.close_value,
                pctchange=row.pctchange,
                turn=row.turn,
                amplitude=row.amplitude,
                hlimitedays=inputs.hlimitedays_by_code.get(row.stock_code),
                close_history=closes,
                amount_history=amounts,
            )
        )
    return _FreshTrendWatchlistLoadResult(snapshots=snapshots, tables_used=inputs.tables_used)


def _load_mean_reversion_snapshots(
    *,
    duckdb_path: str,
    as_of_date: str,
) -> list[MeanReversionSnapshot]:
    path = Path(duckdb_path)
    if not path.exists():
        return []
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {
            "choice_stock_universe",
            "choice_stock_sector_membership",
            "choice_stock_daily_observation",
        }
        if not required_tables.issubset(tables):
            return []
        universe_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_universe",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        membership_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_sector_membership",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        if universe_snapshot_date is None or membership_snapshot_date is None:
            return []
        current_rows = conn.execute(
            """
            select
              daily.stock_code,
              coalesce(nullif(trim(universe.stock_name), ''), daily.stock_code) as stock_name,
              coalesce(nullif(trim(membership.sw2021code), ''), '') as sector_code,
              coalesce(nullif(trim(membership.sw2021), ''), '') as sector_name,
              daily.close_value,
              daily.low_value,
              daily.high_value,
              daily.volume
            from choice_stock_daily_observation daily
            left join choice_stock_universe universe
              on universe.stock_code = daily.stock_code
             and universe.as_of_date = ?
            left join choice_stock_sector_membership membership
              on membership.stock_code = daily.stock_code
             and membership.as_of_date = ?
            where cast(daily.trade_date as date) = cast(? as date)
              and trim(coalesce(daily.tradestatus, '')) = 'Trading'
            """,
            [universe_snapshot_date, membership_snapshot_date, as_of_date],
        ).fetchall()
        stock_codes = [str(row[0] or "") for row in current_rows if row[0]]
        if not stock_codes:
            return []
        placeholders = ",".join("?" for _ in stock_codes)
        history_rows = conn.execute(
            f"""
            select stock_code, close_value, volume
            from choice_stock_daily_observation
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
              and trim(coalesce(tradestatus, '')) = 'Trading'
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()
    except duckdb.Error:
        return []
    finally:
        conn.close()

    history_by_code: dict[str, dict[str, list[object]]] = {}
    for row in history_rows:
        code = str(row[0] or "")
        if not code:
            continue
        bucket = history_by_code.setdefault(code, {"close": [], "volume": []})
        bucket["close"].append(row[1])
        bucket["volume"].append(row[2])

    snapshots: list[MeanReversionSnapshot] = []
    for row in current_rows:
        code = str(row[0] or "")
        if not code:
            continue
        bucket = history_by_code.get(code, {"close": [], "volume": []})
        closes = bucket["close"]
        vols = bucket["volume"]
        if len(closes) > 65:
            closes = closes[-65:]
            vols = vols[-65:]
        if len(closes) != len(vols):
            continue
        snapshots.append(
            MeanReversionSnapshot(
                stock_code=code,
                stock_name=str(row[1] or code),
                sector_code=str(row[2] or ""),
                sector_name=str(row[3] or ""),
                close_value=row[4],
                low_value=row[5],
                high_value=row[6],
                volume=row[7],
                close_history=closes,
                volume_history=vols,
            )
        )
    return snapshots


def _load_uptrend_momentum_snapshots(
    *,
    duckdb_path: str,
    as_of_date: str,
) -> list[UptrendMomentumSnapshot]:
    path = Path(duckdb_path)
    if not path.exists():
        return []
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {
            "choice_stock_universe",
            "choice_stock_sector_membership",
            "choice_stock_daily_observation",
        }
        if not required_tables.issubset(tables):
            return []
        universe_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_universe",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        membership_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_sector_membership",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        if universe_snapshot_date is None or membership_snapshot_date is None:
            return []
        current_rows = conn.execute(
            """
            select
              daily.stock_code,
              coalesce(nullif(trim(universe.stock_name), ''), daily.stock_code) as stock_name,
              coalesce(nullif(trim(membership.sw2021code), ''), '') as sector_code,
              coalesce(nullif(trim(membership.sw2021), ''), '') as sector_name,
              daily.close_value,
              daily.pctchange,
              daily.turn,
              daily.amplitude
            from choice_stock_daily_observation daily
            left join choice_stock_universe universe
              on universe.stock_code = daily.stock_code
             and universe.as_of_date = ?
            left join choice_stock_sector_membership membership
              on membership.stock_code = daily.stock_code
             and membership.as_of_date = ?
            where cast(daily.trade_date as date) = cast(? as date)
              and trim(coalesce(daily.tradestatus, '')) = 'Trading'
            """,
            [universe_snapshot_date, membership_snapshot_date, as_of_date],
        ).fetchall()
        stock_codes = [str(row[0] or "") for row in current_rows if row[0]]
        if not stock_codes:
            return []
        placeholders = ",".join("?" for _ in stock_codes)
        history_rows = conn.execute(
            f"""
            select stock_code, close_value, amount
            from choice_stock_daily_observation
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
              and trim(coalesce(tradestatus, '')) = 'Trading'
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()
    except duckdb.Error:
        return []
    finally:
        conn.close()

    history_by_code: dict[str, dict[str, list[object]]] = {}
    for row in history_rows:
        code = str(row[0] or "")
        if not code:
            continue
        bucket = history_by_code.setdefault(code, {"close": [], "amount": []})
        bucket["close"].append(row[1])
        bucket["amount"].append(row[2])

    snapshots: list[UptrendMomentumSnapshot] = []
    for row in current_rows:
        code = str(row[0] or "")
        if not code:
            continue
        bucket = history_by_code.get(code, {"close": [], "amount": []})
        closes = bucket["close"]
        amounts = bucket["amount"]
        if len(closes) > 130:
            closes = closes[-130:]
            amounts = amounts[-130:]
        if len(closes) != len(amounts):
            continue
        snapshots.append(
            UptrendMomentumSnapshot(
                stock_code=code,
                stock_name=str(row[1] or code),
                sector_code=str(row[2] or ""),
                sector_name=str(row[3] or ""),
                close_value=row[4],
                pctchange=row[5],
                turn=row[6],
                amplitude=row[7],
                close_history=closes,
                amount_history=amounts,
            )
        )
    return snapshots


def _load_fresh_trend_watchlist_snapshots(
    *,
    duckdb_path: str,
    as_of_date: str,
) -> _FreshTrendWatchlistLoadResult:
    path = Path(duckdb_path)
    if not path.exists():
        return _FreshTrendWatchlistLoadResult(snapshots=[], tables_used=[])
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return _FreshTrendWatchlistLoadResult(snapshots=[], tables_used=[])
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {
            "choice_stock_universe",
            "choice_stock_sector_membership",
            "choice_stock_daily_observation",
        }
        if not required_tables.issubset(tables):
            return _FreshTrendWatchlistLoadResult(snapshots=[], tables_used=[])
        tables_used = [
            "choice_stock_daily_observation",
            "choice_stock_universe",
            "choice_stock_sector_membership",
        ]
        universe_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_universe",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        membership_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_sector_membership",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        if universe_snapshot_date is None or membership_snapshot_date is None:
            return _FreshTrendWatchlistLoadResult(snapshots=[], tables_used=[])
        current_rows = conn.execute(
            """
            select
              daily.stock_code,
              coalesce(nullif(trim(universe.stock_name), ''), daily.stock_code) as stock_name,
              coalesce(nullif(trim(membership.sw2021code), ''), '') as sector_code,
              coalesce(nullif(trim(membership.sw2021), ''), '') as sector_name,
              daily.close_value,
              daily.pctchange,
              daily.turn,
              daily.amplitude
            from choice_stock_daily_observation daily
            left join choice_stock_universe universe
              on universe.stock_code = daily.stock_code
             and universe.as_of_date = ?
            left join choice_stock_sector_membership membership
              on membership.stock_code = daily.stock_code
             and membership.as_of_date = ?
            where cast(daily.trade_date as date) = cast(? as date)
              and trim(coalesce(daily.tradestatus, '')) = 'Trading'
            """,
            [universe_snapshot_date, membership_snapshot_date, as_of_date],
        ).fetchall()
        stock_codes = [str(row[0] or "") for row in current_rows if row[0]]
        if not stock_codes:
            return _FreshTrendWatchlistLoadResult(snapshots=[], tables_used=[])
        placeholders = ",".join("?" for _ in stock_codes)
        history_rows = conn.execute(
            f"""
            select stock_code, close_value, amount
            from choice_stock_daily_observation
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
              and trim(coalesce(tradestatus, '')) = 'Trading'
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()
        concept_rows: list[tuple[object, object]] = []
        if "choice_stock_concept_membership" in tables:
            concept_snapshot_date = _latest_table_date_on_or_before(
                conn,
                table_name="choice_stock_concept_membership",
                column_name="as_of_date",
                as_of_date=as_of_date,
            )
            if concept_snapshot_date is not None:
                concept_rows = conn.execute(
                    f"""
                    select stock_code, concept_name
                    from choice_stock_concept_membership
                    where stock_code in ({placeholders})
                      and as_of_date = ?
                    order by stock_code asc, concept_name asc
                    """,
                    [*stock_codes, concept_snapshot_date],
                ).fetchall()
                tables_used.append("choice_stock_concept_membership")
        limit_rows: list[tuple[object, object]] = []
        if "choice_stock_limit_quality" in tables:
            limit_snapshot_date = _latest_table_date_on_or_before(
                conn,
                table_name="choice_stock_limit_quality",
                column_name="as_of_date",
                as_of_date=as_of_date,
            )
            if limit_snapshot_date is not None:
                limit_rows = conn.execute(
                    f"""
                    select stock_code, hlimitedays
                    from choice_stock_limit_quality
                    where stock_code in ({placeholders})
                      and as_of_date = ?
                    """,
                    [*stock_codes, limit_snapshot_date],
                ).fetchall()
                tables_used.append("choice_stock_limit_quality")
    except duckdb.Error:
        return _FreshTrendWatchlistLoadResult(snapshots=[], tables_used=[])
    finally:
        conn.close()

    history_by_code: dict[str, dict[str, list[object]]] = {}
    for row in history_rows:
        code = str(row[0] or "")
        if not code:
            continue
        bucket = history_by_code.setdefault(code, {"close": [], "amount": []})
        bucket["close"].append(row[1])
        bucket["amount"].append(row[2])

    concepts_by_code: dict[str, list[object]] = {}
    for code_raw, concept_name in concept_rows:
        code = str(code_raw or "")
        if not code:
            continue
        concepts_by_code.setdefault(code, []).append(concept_name)

    hlimitedays_by_code = {str(code or ""): hlimitedays for code, hlimitedays in limit_rows if code}

    snapshots: list[FreshTrendWatchlistSnapshot] = []
    for row in current_rows:
        code = str(row[0] or "")
        if not code:
            continue
        bucket = history_by_code.get(code, {"close": [], "amount": []})
        closes = bucket["close"]
        amounts = bucket["amount"]
        if len(closes) > 130:
            closes = closes[-130:]
            amounts = amounts[-130:]
        if len(closes) != len(amounts):
            continue
        snapshots.append(
            FreshTrendWatchlistSnapshot(
                stock_code=code,
                stock_name=str(row[1] or code),
                sector_code=str(row[2] or ""),
                sector_name=str(row[3] or ""),
                concepts=concepts_by_code.get(code, []),
                close_value=row[4],
                pctchange=row[5],
                turn=row[6],
                amplitude=row[7],
                hlimitedays=hlimitedays_by_code.get(code),
                close_history=closes,
                amount_history=amounts,
            )
        )
    return _FreshTrendWatchlistLoadResult(
        snapshots=snapshots,
        tables_used=_unique_preserving_order(tables_used),
    )


def _load_factor_screen_rows(
    *,
    duckdb_path: str,
    as_of_date: str,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> _FactorScreenLoadResult:
    """Load factor snapshot rows for the given date (or latest available)."""
    path = Path(duckdb_path)
    if not path.exists():
        return _FactorScreenLoadResult(
            rows=[],
            snapshot_as_of_date=None,
            tables_used=[],
            unavailable_reason="DuckDB file is missing; choice_stock_factor_snapshot cannot be read.",
        )
    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            return _FactorScreenLoadResult(
                rows=[],
                snapshot_as_of_date=None,
                tables_used=[],
                unavailable_reason="DuckDB file could not be opened; choice_stock_factor_snapshot cannot be read.",
            )
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "choice_stock_factor_snapshot" not in tables:
            return _FactorScreenLoadResult(
                rows=[],
                snapshot_as_of_date=None,
                tables_used=[],
                unavailable_reason="choice_stock_factor_snapshot table is missing.",
            )
        required_factor_columns = [
            "as_of_date",
            "stock_code",
            "pe",
            "pb",
            "ps",
            "roe",
            "gross_margin",
            "three_month_return",
            "twelve_month_return",
            "volatility",
            "dividend_yield",
            "industry",
        ]
        factor_columns = _table_columns(conn, "choice_stock_factor_snapshot")
        missing_factor_columns = [col for col in required_factor_columns if col not in factor_columns]
        if missing_factor_columns:
            return _FactorScreenLoadResult(
                rows=[],
                snapshot_as_of_date=None,
                tables_used=["choice_stock_factor_snapshot"],
                unavailable_reason=(
                    f"choice_stock_factor_snapshot is missing required columns: {', '.join(missing_factor_columns)}."
                ),
            )
        latest = conn.execute(
            """
            SELECT MAX(as_of_date) FROM choice_stock_factor_snapshot
            WHERE as_of_date <= ?
        """,
            [as_of_date],
        ).fetchone()
        if not latest or not latest[0]:
            return _FactorScreenLoadResult(
                rows=[],
                snapshot_as_of_date=None,
                tables_used=["choice_stock_factor_snapshot"],
                unavailable_reason=f"choice_stock_factor_snapshot has no rows on or before {as_of_date}.",
            )
        snap_date = latest[0]
        tables_used = ["choice_stock_factor_snapshot"]
        has_universe = _table_has_columns(conn, "choice_stock_universe", ["stock_code", "stock_name", "as_of_date"])
        has_sector = _table_has_columns(
            conn,
            "choice_stock_sector_membership",
            ["stock_code", "sw2021code", "sw2021", "as_of_date"],
        )
        universe_snapshot_date = (
            _latest_table_date_on_or_before(
                conn,
                table_name="choice_stock_universe",
                column_name="as_of_date",
                as_of_date=str(snap_date),
            )
            if has_universe
            else None
        )
        sector_snapshot_date = (
            _latest_table_date_on_or_before(
                conn,
                table_name="choice_stock_sector_membership",
                column_name="as_of_date",
                as_of_date=str(snap_date),
            )
            if has_sector
            else None
        )
        has_universe = has_universe and universe_snapshot_date is not None
        has_sector = has_sector and sector_snapshot_date is not None
        coverage_denominator = (
            _count_distinct_stock_codes(
                conn,
                table_name="choice_stock_universe",
                date_column="as_of_date",
                as_of_date=str(universe_snapshot_date),
            )
            if has_universe and universe_snapshot_date is not None
            else None
        )
        if has_universe:
            tables_used.append("choice_stock_universe")
        if has_sector:
            tables_used.append("choice_stock_sector_membership")

        stock_name_expr = "COALESCE(u.stock_name, f.stock_code)" if has_universe else "f.stock_code"
        universe_join = (
            """
            LEFT JOIN (
                SELECT stock_code, stock_name
                FROM choice_stock_universe
                WHERE as_of_date = ?
            ) u ON f.stock_code = u.stock_code
            """
            if has_universe
            else ""
        )
        sector_code_expr = "COALESCE(s.sw2021code, '')" if has_sector else "''"
        sector_name_expr = "COALESCE(s.sw2021, f.industry, '')" if has_sector else "COALESCE(f.industry, '')"
        sector_join = (
            """
            LEFT JOIN (
                SELECT stock_code, sw2021code, sw2021
                FROM choice_stock_sector_membership
                WHERE as_of_date = ?
            ) s ON f.stock_code = s.stock_code
            """
            if has_sector
            else ""
        )
        params: list[object] = []
        if has_universe:
            params.append(universe_snapshot_date)
        if has_sector:
            params.append(sector_snapshot_date)
        params.append(snap_date)

        rows = conn.execute(
            f"""
            SELECT
                f.stock_code,
                {stock_name_expr} AS stock_name,
                f.pe, f.pb, f.ps, f.roe, f.gross_margin,
                f.three_month_return, f.twelve_month_return,
                f.volatility, f.dividend_yield,
                f.industry,
                {sector_code_expr} AS sector_code,
                {sector_name_expr} AS sector_name
            FROM choice_stock_factor_snapshot f
            {universe_join}
            {sector_join}
            WHERE f.as_of_date = ?
        """,
            params,
        ).fetchall()

        cols = [
            "stock_code",
            "stock_name",
            "pe",
            "pb",
            "ps",
            "roe",
            "gross_margin",
            "three_month_return",
            "twelve_month_return",
            "volatility",
            "dividend_yield",
            "industry",
            "sector_code",
            "sector_name",
        ]
        mapped_rows = [dict(zip(cols, row, strict=False)) for row in rows]
        if not mapped_rows:
            return _FactorScreenLoadResult(
                rows=[],
                snapshot_as_of_date=str(snap_date),
                tables_used=tables_used,
                unavailable_reason=f"choice_stock_factor_snapshot has no usable rows for snapshot {snap_date}.",
            )
        return _FactorScreenLoadResult(
            rows=mapped_rows,
            snapshot_as_of_date=str(snap_date),
            tables_used=tables_used,
            coverage_denominator=coverage_denominator,
            coverage_denominator_as_of_date=str(universe_snapshot_date) if universe_snapshot_date is not None else None,
        )
    except duckdb.Error:
        return _FactorScreenLoadResult(
            rows=[],
            snapshot_as_of_date=None,
            tables_used=["choice_stock_factor_snapshot"],
            unavailable_reason="DuckDB query failed while reading choice_stock_factor_snapshot.",
        )
    finally:
        if owns_conn:
            conn.close()


def _table_has_columns(conn: duckdb.DuckDBPyConnection, table_name: str, columns: list[str]) -> bool:
    available = _table_columns(conn, table_name)
    return set(columns).issubset(available)


def _count_distinct_stock_codes(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    date_column: str,
    as_of_date: str,
) -> int:
    try:
        row = conn.execute(
            f"""
            select count(distinct stock_code)
            from {table_name}
            where cast({date_column} as date) = cast(? as date)
            """,
            [as_of_date],
        ).fetchone()
    except duckdb.Error:
        return 0
    return int(row[0]) if row and row[0] is not None else 0


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}
    except duckdb.Error:
        return set()


def _latest_table_date_on_or_before(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    column_name: str,
    as_of_date: str,
) -> str | None:
    try:
        row = conn.execute(
            f"""
            select max({column_name})
            from {table_name}
            where cast({column_name} as date) <= cast(? as date)
            """,
            [as_of_date],
        ).fetchone()
    except duckdb.Error:
        return None
    return str(row[0]) if row and row[0] else None


def _load_theme_breakout_snapshots(
    *,
    duckdb_path: str,
    as_of_date: str,
    sector_rank_payload: dict[str, object],
    conn: duckdb.DuckDBPyConnection | None = None,
    theme_overlay_result: ThemeOverlayReadResult | None = None,
) -> tuple[list[ThemeBreakoutSnapshot], list[str], list[str], list[str], _ThemeBreakoutEvidenceProvenance]:
    path = Path(duckdb_path)
    if not path.exists():
        return [], [], [], [], _ThemeBreakoutEvidenceProvenance()
    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            return [], [], [], [], _ThemeBreakoutEvidenceProvenance()
    required_tables = {
        "choice_stock_universe",
        "choice_stock_sector_membership",
        "choice_stock_daily_observation",
    }
    concept_rows: list[tuple[object, ...]] = []
    movement_rows: list[tuple[object, ...]] = []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if not required_tables.issubset(tables):
            return [], [], [], [], _ThemeBreakoutEvidenceProvenance()
        has_limit_quality = "choice_stock_limit_quality" in tables
        has_concept_membership = "choice_stock_concept_membership" in tables
        has_intraday_movement = "choice_stock_intraday_movement_event" in tables
        universe_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_universe",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        membership_snapshot_date = _latest_table_date_on_or_before(
            conn,
            table_name="choice_stock_sector_membership",
            column_name="as_of_date",
            as_of_date=as_of_date,
        )
        if universe_snapshot_date is None or membership_snapshot_date is None:
            return [], [], [], [], _ThemeBreakoutEvidenceProvenance()
        limit_snapshot_date = (
            _latest_table_date_on_or_before(
                conn,
                table_name="choice_stock_limit_quality",
                column_name="as_of_date",
                as_of_date=as_of_date,
            )
            if has_limit_quality
            else None
        )
        has_limit_quality = has_limit_quality and limit_snapshot_date is not None
        limit_select = (
            "coalesce(cast(limits.issurgedlimit as varchar), '') as issurgedlimit, "
            "limits.source_version, limits.vendor_version"
            if has_limit_quality
            else "'' as issurgedlimit, '' as limit_source_version, '' as limit_vendor_version"
        )
        limit_join = (
            """
            left join choice_stock_limit_quality limits
              on limits.stock_code = universe.stock_code
             and limits.as_of_date = ?
            """
            if has_limit_quality
            else ""
        )
        params: list[object] = [membership_snapshot_date, as_of_date]
        if has_limit_quality:
            params.append(limit_snapshot_date)
        params.append(universe_snapshot_date)
        rows = conn.execute(
            f"""
            select
              universe.stock_code,
              universe.stock_name,
              membership.sw2021code,
              membership.sw2021,
              daily.open_value,
              daily.high_value,
              daily.low_value,
              daily.close_value,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              {limit_select},
              universe.source_version,
              universe.vendor_version,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              daily.vendor_version
            from choice_stock_universe universe
            join choice_stock_sector_membership membership
              on membership.stock_code = universe.stock_code
             and membership.as_of_date = ?
            join choice_stock_daily_observation daily
              on daily.stock_code = universe.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            {limit_join}
            where universe.as_of_date = ?
            order by universe.stock_code asc
            """,
            params,
        ).fetchall()
        if has_concept_membership:
            concept_rows = conn.execute(
                """
                select
                  stock_code,
                  concept_code,
                  concept_name,
                  concept_source,
                  source_version,
                  vendor_version
                from choice_stock_concept_membership
                where as_of_date = ?
                order by stock_code asc, concept_code asc, concept_name asc
                """,
                [as_of_date],
            ).fetchall()
        if has_intraday_movement:
            movement_rows = conn.execute(
                """
                select
                  stock_code,
                  concept_code,
                  concept_name,
                  event_time,
                  event_title,
                  source_version,
                  vendor_version
                from choice_stock_intraday_movement_event
                where as_of_date = ?
                order by stock_code asc, concept_code asc, event_time asc
                """,
                [as_of_date],
            ).fetchall()
    except duckdb.Error:
        return [], sorted(required_tables | {"choice_stock_limit_quality"}), [], [], _ThemeBreakoutEvidenceProvenance()
    finally:
        if owns_conn:
            conn.close()

    sector_rank_by_key: dict[tuple[str, str], int] = {}
    for item in cast(list[dict[str, object]], sector_rank_payload["items"]):
        rank = _safe_int(item.get("rank"))
        if rank is None:
            continue
        sector_rank_by_key[(str(item["sector_code"]), str(item["sector_name"]))] = rank

    snapshots: list[ThemeBreakoutSnapshot] = []
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    universe_codes = {str(row[0] or "") for row in rows if str(row[0] or "")}
    concept_by_stock: dict[str, list[tuple[str, str, str]]] = {}
    concept_date_row_count = 0
    concept_matched_row_count = 0
    concept_fallback_row_count = 0
    point_in_time_choice_rows = [
        row
        for row in concept_rows
        if str(row[3] or "").strip().lower() == "choice" and bool(str(row[1] or "") or str(row[2] or ""))
    ]
    usable_choice_rows = [row for row in point_in_time_choice_rows if str(row[0] or "") in universe_codes]
    overlay_status = (
        "choice_exact_precedence"
        if usable_choice_rows
        else (theme_overlay_result.status if theme_overlay_result is not None else "not_configured")
    )
    overlay_reason = (
        "Exact request-date Choice concept membership takes precedence over current overlay."
        if usable_choice_rows
        else (
            theme_overlay_result.reason
            if theme_overlay_result is not None
            else "Current theme overlay reader is not configured."
        )
    )
    concept_input_rows = point_in_time_choice_rows if usable_choice_rows else []
    concept_source_kind = "real_concept" if usable_choice_rows else ""
    if not usable_choice_rows and theme_overlay_result is not None and theme_overlay_result.available:
        concept_source_kind = theme_overlay_result.concept_source_kind
        concept_input_rows = [
            (
                member.stock_code,
                member.theme_key,
                member.theme_name,
                theme_overlay_result.concept_source_kind,
                theme_overlay_result.source_version,
                theme_overlay_result.vendor_version,
            )
            for member in theme_overlay_result.members
        ]

    for row in concept_input_rows:
        stock_code = str(row[0] or "")
        concept_code = str(row[1] or "")
        concept_name = str(row[2] or "")
        if not stock_code or not (concept_code or concept_name):
            continue
        concept_date_row_count += 1
        if stock_code in universe_codes:
            concept_matched_row_count += 1
        else:
            continue
        row_source_kind = (
            "tushare_current_overlay" if str(row[3] or "").lower() == "tushare_current_overlay" else "real_concept"
        )
        if row_source_kind != "real_concept":
            concept_fallback_row_count += 1
        concept_by_stock.setdefault(stock_code, []).append((concept_code, concept_name, row_source_kind))
        source_versions.extend(str(value) for value in (row[4],) if value)
        vendor_versions.extend(str(value) for value in (row[5],) if value)

    movement_by_key: dict[tuple[str, str, str], dict[str, object]] = {}
    seen_movement_events: set[tuple[str, str, str, str, str]] = set()
    movement_date_row_count = 0
    movement_matched_row_count = 0
    for row in movement_rows:
        stock_code = str(row[0] or "")
        concept_code = str(row[1] or "")
        concept_name = str(row[2] or "")
        if not stock_code:
            continue
        event_time = str(row[3] or "")
        event_title = str(row[4] or "")
        identity = (stock_code, concept_code, concept_name, event_time, event_title)
        if identity in seen_movement_events:
            continue
        seen_movement_events.add(identity)
        movement_date_row_count += 1
        if stock_code in universe_codes:
            movement_matched_row_count += 1
        key = (stock_code, concept_code, concept_name)
        current = movement_by_key.setdefault(
            key,
            {
                "count": 0,
                "latest_event_time": "",
                "latest_event_title": "",
            },
        )
        current["count"] = int(current["count"]) + 1
        if event_time >= str(current["latest_event_time"]):
            current["latest_event_time"] = event_time
            current["latest_event_title"] = event_title
        source_versions.extend(str(value) for value in (row[5],) if value)
        vendor_versions.extend(str(value) for value in (row[6],) if value)

    for row in rows:
        stock_code = str(row[0] or "")
        sector_code = str(row[2] or "")
        sector_name = str(row[3] or "")
        concepts = concept_by_stock.get(stock_code) or [("", "", "proxy")]
        if (stock_code, "", "") in movement_by_key and not any(
            not concept_code and not concept_name for concept_code, concept_name, _source_kind in concepts
        ):
            concepts = [*concepts, ("", "", "proxy")]
        for concept_code, concept_name, snapshot_source_kind in concepts:
            movement = _movement_for_concept(
                movement_by_key=movement_by_key,
                stock_code=stock_code,
                concept_code=concept_code,
                concept_name=concept_name,
            )
            snapshots.append(
                ThemeBreakoutSnapshot(
                    stock_code=stock_code,
                    stock_name=str(row[1] or ""),
                    sector_code=sector_code,
                    sector_name=sector_name,
                    sector_rank=sector_rank_by_key.get((sector_code, sector_name)),
                    open_value=row[4],
                    high_value=row[5],
                    low_value=row[6],
                    close_value=row[7],
                    pctchange=row[8],
                    turn=row[9],
                    amplitude=row[10],
                    closed_up_limit=bool(_truthy(row[11])),
                    concept_code=concept_code,
                    concept_name=concept_name,
                    movement_event_count=int(movement["count"]),
                    latest_event_title=str(movement["latest_event_title"]),
                    latest_event_time=str(movement["latest_event_time"]),
                    concept_source_kind=snapshot_source_kind,
                )
            )
        source_versions.extend(str(value) for value in (row[12], row[14], row[16], row[18]) if value)
        vendor_versions.extend(str(value) for value in (row[13], row[15], row[17], row[19]) if value)

    tables_used = [
        "choice_stock_universe",
        "choice_stock_sector_membership",
        "choice_stock_daily_observation",
    ]
    if has_limit_quality:
        tables_used.append("choice_stock_limit_quality")
    if has_concept_membership:
        tables_used.append("choice_stock_concept_membership")
    if has_intraday_movement:
        tables_used.append("choice_stock_intraday_movement_event")
    return (
        snapshots,
        tables_used,
        source_versions,
        vendor_versions,
        _ThemeBreakoutEvidenceProvenance(
            concept_date_row_count=concept_date_row_count,
            concept_matched_row_count=concept_matched_row_count,
            concept_fallback_row_count=concept_fallback_row_count,
            movement_date_row_count=movement_date_row_count,
            movement_matched_row_count=movement_matched_row_count,
            concept_source_kind=concept_source_kind,
            overlay_status=overlay_status,
            overlay_reason=overlay_reason,
            overlay_run_id=(theme_overlay_result.run_id if theme_overlay_result is not None else ""),
            overlay_source_version=(theme_overlay_result.source_version if theme_overlay_result is not None else ""),
            overlay_vendor_version=(theme_overlay_result.vendor_version if theme_overlay_result is not None else ""),
            overlay_source_kind=(theme_overlay_result.source_kind if theme_overlay_result is not None else ""),
            overlay_member_count=(len(theme_overlay_result.members) if theme_overlay_result is not None else 0),
        ),
    )


def _build_theme_breakout_evidence_state(
    *,
    stock_readiness: ChoiceStockReadiness,
    tables_used: list[str],
    provenance: _ThemeBreakoutEvidenceProvenance,
) -> dict[str, dict[str, object]]:
    concept_membership = _theme_breakout_evidence_entry(
        input_family="concept_membership",
        catalog_status=choice_stock_optional_input_status(stock_readiness, "concept_membership"),
        table_name="choice_stock_concept_membership",
        tables_used=tables_used,
        date_row_count=provenance.concept_date_row_count,
        matched_row_count=provenance.concept_matched_row_count,
        fallback_row_count=provenance.concept_fallback_row_count,
    )
    concept_membership.update(
        {
            "concept_source_kind": provenance.concept_source_kind or None,
            "overlay_status": provenance.overlay_status,
            "overlay_reason": provenance.overlay_reason,
        }
    )
    if provenance.concept_source_kind == "tushare_current_overlay":
        concept_membership.update(
            {
                "status": "current_overlay",
                "state": "current_overlay",
                "source_kind": provenance.overlay_source_kind,
                "source_version": provenance.overlay_source_version,
                "vendor_version": provenance.overlay_vendor_version,
                "run_id": provenance.overlay_run_id,
                "member_count": provenance.overlay_member_count,
                "point_in_time": False,
                "historical_use_allowed": False,
                "message": (
                    "Current Tushare THS concept overlay is available for the latest observation date; "
                    "it is non-point-in-time and remains partial evidence."
                ),
            }
        )
    return {
        "concept_membership": concept_membership,
        "intraday_movement": _theme_breakout_evidence_entry(
            input_family="intraday_movement",
            catalog_status=choice_stock_optional_input_status(stock_readiness, "intraday_movement"),
            table_name="choice_stock_intraday_movement_event",
            tables_used=tables_used,
            date_row_count=provenance.movement_date_row_count,
            matched_row_count=provenance.movement_matched_row_count,
            fallback_row_count=0,
        ),
    }


def _theme_breakout_evidence_entry(
    *,
    input_family: str,
    catalog_status: str,
    table_name: str,
    tables_used: list[str],
    date_row_count: int,
    matched_row_count: int,
    fallback_row_count: int = 0,
) -> dict[str, object]:
    if catalog_status == "catalog_unconfirmed" and fallback_row_count <= 0:
        state = "catalog_unconfirmed"
    elif table_name not in tables_used:
        state = "table_missing"
    elif matched_row_count > 0:
        state = "matched_rows"
    else:
        state = "landed_no_rows"
    return {
        "input_family": input_family,
        "status": state,
        "state": state,
        "table": table_name,
        "table_name": table_name,
        "row_count": date_row_count,
        "date_row_count": date_row_count,
        "matched_row_count": matched_row_count,
        "fallback_row_count": fallback_row_count,
        "message": _theme_breakout_evidence_message(
            input_family=input_family,
            state=state,
            table_name=table_name,
            date_row_count=date_row_count,
            matched_row_count=matched_row_count,
        ),
    }


def _theme_breakout_evidence_message(
    *,
    input_family: str,
    state: str,
    table_name: str,
    date_row_count: int,
    matched_row_count: int,
) -> str:
    if state == "catalog_unconfirmed":
        return f"{input_family} is optional and not confirmed in the Choice stock catalog."
    if state == "table_missing":
        return f"{input_family} is confirmed, but {table_name} is not landed in DuckDB."
    if state == "matched_rows":
        return f"{input_family} has {matched_row_count} date-matched rows from {table_name}."
    return f"{input_family} table {table_name} is landed with {date_row_count} date rows but no matched usable rows."


def _movement_for_concept(
    *,
    movement_by_key: dict[tuple[str, str, str], dict[str, object]],
    stock_code: str,
    concept_code: str,
    concept_name: str,
) -> dict[str, object]:
    empty = {
        "count": 0,
        "latest_event_time": "",
        "latest_event_title": "",
    }
    if not movement_by_key:
        return empty
    candidates = [
        value
        for (code, row_concept_code, row_concept_name), value in movement_by_key.items()
        if code == stock_code and row_concept_code == concept_code and row_concept_name == concept_name
    ]
    if not candidates:
        return empty
    latest = max(candidates, key=lambda row: str(row["latest_event_time"]))
    return {
        "count": sum(int(row["count"]) for row in candidates),
        "latest_event_time": latest["latest_event_time"],
        "latest_event_title": latest["latest_event_title"],
    }


def _load_risk_exit_snapshots(
    *,
    duckdb_path: str,
    as_of_date: str,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> tuple[list[RiskExitSnapshot], list[str], list[str], list[str]]:
    path = Path(duckdb_path)
    if not path.exists():
        return [], [], [], []
    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            return [], [], [], []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {"livermore_position_snapshot", "choice_stock_daily_observation"}
        if not required_tables.issubset(tables):
            return [], [], [], []
        position_rows = conn.execute(
            """
            select
              stock_code,
              stock_name,
              entry_cost,
              bars_since_entry,
              source_version,
              vendor_version
            from livermore_position_snapshot
            where as_of_date = ?
              and upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
            order by stock_code asc
            """,
            [as_of_date],
        ).fetchall()
        stock_codes = [str(row[0]) for row in position_rows if row[0]]
        if not stock_codes:
            return [], list(required_tables), [], []
        placeholders = ",".join("?" for _ in stock_codes)
        history_rows = conn.execute(
            f"""
            select stock_code, close_value, volume, source_version, vendor_version
            from choice_stock_daily_observation
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()
    except duckdb.Error:
        return [], list(required_tables), [], []
    finally:
        if owns_conn:
            conn.close()

    close_history_by_code: dict[str, list[float]] = {}
    volume_history_by_code: dict[str, list[float]] = {}
    history_sources: list[str] = []
    history_vendors: list[str] = []
    for row in history_rows:
        stock_code = str(row[0] or "")
        close_value = _safe_float(row[1])
        volume_value = _safe_float(row[2])
        if not stock_code or close_value is None or volume_value is None:
            continue
        close_history_by_code.setdefault(stock_code, []).append(close_value)
        volume_history_by_code.setdefault(stock_code, []).append(volume_value)
        if row[3]:
            history_sources.append(str(row[3]))
        if row[4]:
            history_vendors.append(str(row[4]))

    snapshots = [
        RiskExitSnapshot(
            stock_code=str(row[0] or ""),
            stock_name=str(row[1] or ""),
            entry_cost=row[2],
            bars_since_entry=row[3],
            close_history=close_history_by_code.get(str(row[0] or ""), []),
            volume_history=volume_history_by_code.get(str(row[0] or ""), []),
        )
        for row in position_rows
        if row[0]
    ]
    position_sources = [str(row[4]) for row in position_rows if row[4]]
    position_vendors = [str(row[5]) for row in position_rows if row[5]]
    return (
        snapshots,
        ["livermore_position_snapshot", "choice_stock_daily_observation"],
        [*position_sources, *history_sources],
        [*position_vendors, *history_vendors],
    )


def _risk_exit_input_block_reason(
    *,
    duckdb_path: str,
    as_of_date: str,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> str:
    path = Path(duckdb_path)
    if not path.exists():
        return "DuckDB database is not available, so Livermore position and close-history inputs are not materialized."
    owns_conn = conn is None
    if owns_conn:
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            return "DuckDB database is unavailable while checking Livermore position and close-history inputs."
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "livermore_position_snapshot" not in tables:
            return "livermore_position_snapshot table is not materialized for Livermore A-share holdings."
        if "choice_stock_daily_observation" not in tables:
            return "choice_stock_daily_observation close history is not materialized for Livermore risk_exit."
        total_rows, active_rows = conn.execute(
            """
            select
              count(*)::integer,
              sum(case when upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE' then 1 else 0 end)::integer
            from livermore_position_snapshot
            where as_of_date = ?
            """,
            [as_of_date],
        ).fetchone()
        if int(active_rows or 0) <= 0:
            latest_row = conn.execute(
                """
                select max(as_of_date)
                from livermore_position_snapshot
                where upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
                """
            ).fetchone()
            latest_active_date = latest_row[0] if latest_row else None
            if int(total_rows or 0) > 0:
                return f"livermore_position_snapshot has rows but no ACTIVE A-share rows for as_of_date {as_of_date}."
            if latest_active_date:
                return (
                    "livermore_position_snapshot has no ACTIVE A-share rows for as_of_date "
                    f"{as_of_date}; latest ACTIVE as_of_date is {latest_active_date}."
                )
            return f"livermore_position_snapshot has no ACTIVE A-share rows for as_of_date {as_of_date}."
        close_rows = conn.execute(
            """
            select count(*)::integer
            from choice_stock_daily_observation daily
            join livermore_position_snapshot position
              on position.stock_code = daily.stock_code
            where position.as_of_date = ?
              and upper(coalesce(position.position_status, 'ACTIVE')) = 'ACTIVE'
              and cast(daily.trade_date as date) <= cast(? as date)
              and daily.close_value is not null
            """,
            [as_of_date, as_of_date],
        ).fetchone()[0]
        if int(close_rows or 0) <= 0:
            return (
                "livermore_position_snapshot has ACTIVE A-share rows, but choice_stock_daily_observation "
                f"has no close history through {as_of_date} for those stock_codes."
            )
        return ""
    except duckdb.Error:
        return "DuckDB query failed while checking Livermore position and close-history inputs."
    finally:
        if owns_conn:
            conn.close()


def _mean_reversion_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if market_state in {"HOT", "OVERHEAT"}:
        return (
            "Mean reversion watchlist is paused when the market gate is HOT or OVERHEAT "
            "because the defended-trend candidate bundle already covers overheated tape."
        )
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but mean reversion daily inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    return (
        "Mean reversion inputs are landed, but no Trading-status A-share rows produced "
        "watchlist snapshots for this as_of_date."
    )


def _uptrend_momentum_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if market_state not in {"WARM", "HOT"}:
        return "Uptrend momentum watchlist is paused unless the market gate is WARM or HOT."
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but uptrend momentum daily inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    return (
        "Uptrend momentum inputs are landed, but no Trading-status A-share rows produced "
        "watchlist snapshots for this as_of_date."
    )


def _fresh_trend_watchlist_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if market_state not in {"WARM", "HOT", "OVERHEAT"}:
        return "Fresh trend watchlist is observation-only and runs only when the market gate is WARM, HOT, or OVERHEAT."
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status", "sector_membership"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but fresh trend daily inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    return (
        "Fresh trend inputs are landed, but no growth-board Trading rows passed "
        "the new-trend and old-economy exclusion filters for this as_of_date."
    )


def _build_supported_outputs(
    state: str,
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> tuple[list[str], list[dict[str, str]]]:
    sector_reason = _sector_unavailable_reason(stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    stock_reason = _stock_unavailable_reason(
        market_state=state,
        stock_readiness=stock_readiness,
        stock_outputs=stock_outputs,
    )
    supported: list[str] = []
    unsupported: list[dict[str, str]] = []
    if state == "NO_DATA":
        unsupported.append(
            {
                "key": "market_gate",
                "reason": "Broad-index history is unavailable for CA.CSI300.",
            }
        )
    else:
        supported.append("market_gate")
    if stock_outputs.sector_rank_payload is not None:
        supported.append("sector_rank")
    else:
        unsupported.append({"key": "sector_rank", "reason": sector_reason})
    if stock_outputs.stock_candidates_payload is not None:
        supported.append("stock_candidates")
    else:
        unsupported.append({"key": "stock_candidates", "reason": stock_reason})
    if stock_outputs.uptrend_momentum_payload is not None:
        supported.append("uptrend_momentum_candidates")
    else:
        unsupported.append(
            {
                "key": "uptrend_momentum_candidates",
                "reason": _uptrend_momentum_unavailable_reason(
                    market_state=state,
                    stock_readiness=stock_readiness,
                    stock_outputs=stock_outputs,
                ),
            }
        )
    if stock_outputs.fresh_trend_watchlist_payload is not None:
        supported.append("fresh_trend_watchlist")
    else:
        unsupported.append(
            {
                "key": "fresh_trend_watchlist",
                "reason": _fresh_trend_watchlist_unavailable_reason(
                    market_state=state,
                    stock_readiness=stock_readiness,
                    stock_outputs=stock_outputs,
                ),
            }
        )
    if stock_outputs.mean_reversion_payload is not None:
        supported.append("mean_reversion_candidates")
    else:
        unsupported.append(
            {
                "key": "mean_reversion_candidates",
                "reason": _mean_reversion_unavailable_reason(
                    market_state=state,
                    stock_readiness=stock_readiness,
                    stock_outputs=stock_outputs,
                ),
            }
        )
    if stock_outputs.factor_screen_payload is not None:
        supported.append("factor_screen_candidates")
    else:
        unsupported.append(
            {
                "key": "factor_screen_candidates",
                "reason": stock_outputs.factor_screen_block_reason
                or "choice_stock_factor_snapshot has no usable rows for the resolved as_of_date.",
            }
        )
    if stock_outputs.theme_breakout_payload is not None:
        supported.append("theme_breakout")
    else:
        unsupported.append(
            {
                "key": "theme_breakout",
                "reason": _theme_breakout_unavailable_reason(
                    market_state=state,
                    stock_readiness=stock_readiness,
                    stock_outputs=stock_outputs,
                ),
            }
        )
    if _payload_item_count(stock_outputs.hybrid_fusion_payload) > 0:
        supported.append("hybrid_fusion")
    else:
        unsupported.append(
            {
                "key": "hybrid_fusion",
                "reason": stock_outputs.hybrid_fusion_block_reason,
            }
        )
    if stock_outputs.risk_exit_payload is not None:
        supported.append("risk_exit")
    else:
        unsupported.append(
            {"key": "risk_exit", "reason": _risk_unavailable_reason(stock_outputs.risk_exit_block_reason)}
        )
    return supported, unsupported


def _build_module_states(
    *,
    page_as_of_date: str | None,
    market_dates: list[date],
    unsupported_outputs: list[dict[str, str]],
    stock_outputs: _ChoiceStockOutputs,
) -> list[dict[str, object]]:
    unsupported_by_key = {row["key"]: row["reason"] for row in unsupported_outputs}
    states: list[dict[str, object]] = []
    for key in LIVERMORE_OUTPUT_KEYS:
        payload = _module_payload(key=key, stock_outputs=stock_outputs)
        source_date = _module_source_date(
            key=key,
            payload=payload,
            stock_outputs=stock_outputs,
            page_as_of_date=page_as_of_date,
        )
        threshold_days = _module_threshold_days(key)
        lag_days = _module_lag_days(page_as_of_date=page_as_of_date, source_date=source_date, market_dates=market_dates)
        coverage_count, coverage_denominator, coverage_ratio = _module_coverage(
            key=key,
            payload=payload,
            stock_outputs=stock_outputs,
        )
        unsupported_reason = unsupported_by_key.get(key)
        reasons: list[str] = []
        state = "ready"
        render_mode = "primary"
        evidence_scope = "primary"
        excludes_from_primary = False

        if unsupported_reason:
            state = "blocked" if key == "risk_exit" else "unsupported"
            render_mode = "evidence_only"
            evidence_scope = "detail"
            excludes_from_primary = True
            reasons.append(unsupported_reason)
        elif key == "factor_screen_candidates":
            reasons.extend(
                _factor_screen_degradation_reasons(
                    payload=payload,
                    lag_days=lag_days,
                    threshold_days=threshold_days,
                    coverage_count=coverage_count,
                    coverage_denominator=coverage_denominator,
                    coverage_ratio=coverage_ratio,
                )
            )
        elif key == "hybrid_fusion":
            reasons.extend(
                _hybrid_fusion_degradation_reasons(
                    payload=payload,
                    lag_days=lag_days,
                    threshold_days=threshold_days,
                    coverage_count=coverage_count,
                    coverage_denominator=coverage_denominator,
                    coverage_ratio=coverage_ratio,
                )
            )

        if reasons and not unsupported_reason:
            coverage_state = _coverage_state(coverage_denominator=coverage_denominator, coverage_ratio=coverage_ratio)
            state = coverage_state or "degraded"
            render_mode = "evidence_only"
            evidence_scope = "detail"
            excludes_from_primary = True

        states.append(
            {
                "key": key,
                "state": state,
                "render_mode": render_mode,
                "source_date": source_date,
                "lag_days": lag_days,
                "threshold_days": threshold_days,
                "coverage_count": coverage_count,
                "coverage_denominator": coverage_denominator,
                "coverage_ratio": coverage_ratio,
                "coverage_threshold": (
                    STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD
                    if key in {"factor_screen_candidates", "hybrid_fusion"}
                    else None
                ),
                "reasons": reasons,
                "evidence_scope": evidence_scope,
                "excludes_from_primary": excludes_from_primary,
            }
        )
    return states


def _module_payload(*, key: str, stock_outputs: _ChoiceStockOutputs) -> dict[str, object] | None:
    if key == "sector_rank":
        return stock_outputs.sector_rank_payload
    if key == "stock_candidates":
        return stock_outputs.stock_candidates_payload
    if key == "uptrend_momentum_candidates":
        return stock_outputs.uptrend_momentum_payload
    if key == "fresh_trend_watchlist":
        return stock_outputs.fresh_trend_watchlist_payload
    if key == "mean_reversion_candidates":
        return stock_outputs.mean_reversion_payload
    if key == "factor_screen_candidates":
        return stock_outputs.factor_screen_payload
    if key == "theme_breakout":
        return stock_outputs.theme_breakout_payload
    if key == "hybrid_fusion":
        return stock_outputs.hybrid_fusion_payload
    if key == "risk_exit":
        return stock_outputs.risk_exit_payload
    return None


def _module_source_date(
    *,
    key: str,
    payload: dict[str, object] | None,
    stock_outputs: _ChoiceStockOutputs,
    page_as_of_date: str | None,
) -> str | None:
    if key == "market_gate":
        return page_as_of_date
    if key == "factor_screen_candidates":
        return _payload_text(payload, "factor_snapshot_as_of_date") or _payload_text(payload, "as_of_date")
    if key == "hybrid_fusion" and _hybrid_fusion_is_factor_only(payload):
        return _module_source_date(
            key="factor_screen_candidates",
            payload=stock_outputs.factor_screen_payload,
            stock_outputs=stock_outputs,
            page_as_of_date=page_as_of_date,
        )
    return _payload_text(payload, "as_of_date")


def _payload_text(payload: dict[str, object] | None, key: str) -> str | None:
    value = payload.get(key) if isinstance(payload, dict) else None
    text = str(value).strip() if value is not None else ""
    return text or None


def _module_threshold_days(key: str) -> int | None:
    if key in {"factor_screen_candidates", "hybrid_fusion", "risk_exit"}:
        return STOCK_MODULE_FRESHNESS_THRESHOLD_DAYS
    return None


def _module_lag_days(*, page_as_of_date: str | None, source_date: str | None, market_dates: list[date]) -> int | None:
    if not page_as_of_date or not source_date:
        return None
    try:
        page_date = date.fromisoformat(page_as_of_date)
        source = date.fromisoformat(source_date)
    except ValueError:
        return None
    if page_date <= source:
        return 0
    trading_dates = {market_date for market_date in market_dates if source < market_date <= page_date}
    if trading_dates:
        return len(trading_dates)
    return max(0, (page_date - source).days)


def _coverage_ratio(count: int | None, denominator: int | None) -> float | None:
    if count is None or denominator is None or denominator <= 0:
        return None
    return round(count / denominator, 6)


def _module_coverage(
    *,
    key: str,
    payload: dict[str, object] | None,
    stock_outputs: _ChoiceStockOutputs,
) -> tuple[int | None, int | None, float | None]:
    source_payload = payload
    if key == "hybrid_fusion" and _hybrid_fusion_is_factor_only(payload):
        source_payload = stock_outputs.factor_screen_payload
    if key not in {"factor_screen_candidates", "hybrid_fusion"} or not isinstance(source_payload, dict):
        return None, None, None
    coverage_count = _safe_int(source_payload.get("coverage_count"))
    if coverage_count is None:
        coverage_count = _safe_int(source_payload.get("input_stock_count"))
    coverage_denominator = _safe_int(source_payload.get("coverage_denominator"))
    coverage_ratio_raw = _safe_float(source_payload.get("coverage_ratio"))
    coverage_ratio = (
        coverage_ratio_raw if coverage_ratio_raw is not None else _coverage_ratio(coverage_count, coverage_denominator)
    )
    return coverage_count, coverage_denominator, coverage_ratio


def _coverage_state(*, coverage_denominator: int | None, coverage_ratio: float | None) -> str | None:
    if coverage_denominator is None or coverage_denominator <= 0 or coverage_ratio is None:
        return "blocked"
    if coverage_ratio < STOCK_MODULE_PARTIAL_COVERAGE_THRESHOLD:
        return "blocked"
    if coverage_ratio < STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD:
        return "partial"
    return None


def _coverage_degradation_reason(
    *,
    label: str,
    coverage_count: int | None,
    coverage_denominator: int | None,
    coverage_ratio: float | None,
) -> str | None:
    if coverage_denominator is None or coverage_denominator <= 0 or coverage_ratio is None:
        count_text = "unknown" if coverage_count is None else str(coverage_count)
        return (
            f"{label} active A-share universe denominator is unavailable; "
            f"coverage count is {count_text}, so primary eligibility cannot be certified."
        )
    if coverage_ratio < STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD:
        percent = coverage_ratio * 100
        threshold = STOCK_MODULE_PRIMARY_COVERAGE_THRESHOLD * 100
        return (
            f"{label} covers {coverage_count}/{coverage_denominator} active A-share stocks "
            f"({percent:.1f}%); primary threshold is {threshold:.0f}%."
        )
    return None


def _factor_screen_degradation_reasons(
    *,
    payload: dict[str, object] | None,
    lag_days: int | None,
    threshold_days: int | None,
    coverage_count: int | None,
    coverage_denominator: int | None,
    coverage_ratio: float | None,
) -> list[str]:
    if not isinstance(payload, dict):
        return []
    reasons: list[str] = []
    if threshold_days is not None and lag_days is not None and lag_days > threshold_days:
        reasons.append(
            f"Factor screen source date lags the page as_of_date by {lag_days} days; threshold is {threshold_days} days."
        )
    coverage_reason = _coverage_degradation_reason(
        label="Factor screen",
        coverage_count=coverage_count,
        coverage_denominator=coverage_denominator,
        coverage_ratio=coverage_ratio,
    )
    if coverage_reason:
        reasons.append(coverage_reason)
    coverage_note = _payload_text(payload, "coverage_note")
    if coverage_note:
        reasons.append(coverage_note)
    return reasons


def _hybrid_fusion_degradation_reasons(
    *,
    payload: dict[str, object] | None,
    lag_days: int | None,
    threshold_days: int | None,
    coverage_count: int | None,
    coverage_denominator: int | None,
    coverage_ratio: float | None,
) -> list[str]:
    if not isinstance(payload, dict) or _payload_item_count(payload) <= 0:
        return []
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    reasons: list[str] = []
    if threshold_days is not None and lag_days is not None and lag_days > threshold_days:
        reasons.append(
            f"Hybrid fusion source date lags the page as_of_date by {lag_days} days; threshold is {threshold_days} days."
        )
    coverage_reason = _coverage_degradation_reason(
        label="Hybrid fusion",
        coverage_count=coverage_count,
        coverage_denominator=coverage_denominator,
        coverage_ratio=coverage_ratio,
    )
    if coverage_reason:
        reasons.append(coverage_reason)
    if _hybrid_fusion_is_factor_only(payload):
        reasons.append(
            "Hybrid fusion candidates are factor-only and lack independent trend, sector, or theme confirmation."
        )
    if any(str(item.get("confidence") or "").strip().lower() in {"low", "very_low"} for item in items):
        reasons.append("Hybrid fusion confidence is low for at least one candidate.")
    if items and all(
        _safe_float(cast(dict[str, object], item.get("evidence") or {}).get("sector_score")) in (None, 0.0)
        for item in items
    ):
        reasons.append("Hybrid fusion has no sector confirmation score.")
    if items and all((_safe_float(item.get("price_confirm_score")) or 0.0) <= 0.0 for item in items):
        reasons.append("Hybrid fusion has no positive price-confirm evidence.")
    if items and all(
        ((_safe_float(item.get("attention_score")) or 0.0) <= 0.0)
        and ((_safe_float(item.get("burst_score")) or 0.0) <= 0.0)
        for item in items
    ):
        reasons.append("Hybrid fusion has no attention or burst evidence.")
    return reasons


def _hybrid_fusion_is_factor_only(payload: dict[str, object] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return False
    source_kinds: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            continue
        raw_kinds = evidence.get("source_kinds")
        if isinstance(raw_kinds, list):
            source_kinds.update(str(kind) for kind in raw_kinds if kind)
    return source_kinds == {"factor_screen"}


def _build_cycle_rotation_framework(
    *,
    market_gate: dict[str, object],
    stock_outputs: _ChoiceStockOutputs,
    cycle_input_evidence: _CycleInputEvidence,
) -> dict[str, object]:
    gate_state = str(market_gate.get("state", "NO_DATA"))
    gate_available = gate_state not in {"NO_DATA"}
    sector_count = _safe_int((stock_outputs.sector_rank_payload or {}).get("sector_count"))
    factor_count = _safe_int((stock_outputs.factor_screen_payload or {}).get("candidate_count"))
    candidate_count = _safe_int((stock_outputs.stock_candidates_payload or {}).get("candidate_count"))
    risk_count = _safe_int((stock_outputs.risk_exit_payload or {}).get("signal_count"))
    macro_available = ["market_gate"] if gate_available else []
    macro_missing: list[str] = []
    if cycle_input_evidence.pmi_ready:
        macro_available.append("PMI")
    else:
        macro_missing.append("PMI")
    if cycle_input_evidence.credit_impulse_ready:
        macro_available.append("credit_impulse")
    else:
        macro_missing.append("credit_impulse")
    if cycle_input_evidence.price_spread_ready:
        macro_available.append("price_spread")
    else:
        macro_missing.append("price_spread")
    market_flow_available = ["stock_candidates"] if stock_outputs.stock_candidates_payload is not None else []
    market_flow_missing = ["fund_flow", "northbound_flow"]
    if cycle_input_evidence.turnover_persistence_ready:
        market_flow_available.append("turnover_persistence")
    else:
        market_flow_missing.append("turnover_persistence")
    valuation_available = ["factor_screen_candidates"] if stock_outputs.factor_screen_payload is not None else []
    valuation_missing = ["earnings_revision"]
    if cycle_input_evidence.valuation_percentile_history_ready:
        valuation_available.append("valuation_percentile_history")
    else:
        valuation_missing.append("valuation_percentile_history")

    return {
        "strategy_name": "A-share cycle rotation research framework",
        "display_name": "A股景气周期选股与行业轮动",
        "observation_only": True,
        "implementation_stage": "verification_pending",
        "score_formula": ("CycleScore = 0.30 Macro + 0.35 Industry + 0.20 MarketFlow + 0.15 ValuationSupport"),
        "macro_formula": "MacroScore = 0.40 PMI + 0.35 CreditImpulse + 0.25 PriceSpread",
        "lifecourt_formula": (
            "LifeCourtScore = 0.18*VCOV + 0.14*CONS + 0.14*BURST + 0.20*PCONF - 0.16*CROWD + 0.10*HYGIENE + 0.08*REGIME"
        ),
        "fusion_formula": "FusionScore = 0.65*CycleScore + 0.35*LifeCourtScore",
        "macro_layer": {
            "macro_score": cycle_input_evidence.macro_score,
            "ready": cycle_input_evidence.macro_score_ready,
            "evidence": cycle_input_evidence.macro_score_evidence,
            "available_inputs": macro_available,
            "missing_inputs": macro_missing,
            "source_versions": list(cycle_input_evidence.source_versions),
            "vendor_versions": list(cycle_input_evidence.vendor_versions),
            "lineage": (
                cycle_input_evidence.macro_snapshot.lineage if cycle_input_evidence.macro_snapshot is not None else {}
            ),
        },
        "rebalance_cadence": "Monthly core review with weekly satellite monitoring.",
        "lifecourt_overlay": {
            "display_name": "生命法庭覆盖层（量化重建）",
            "observation_only": True,
            "implementation_stage": "proxy_reconstruction",
            "rebalance_cadence": "Weekly overlay review on top of monthly cycle core.",
            "boundary": (
                "LifeCourt inputs are proxy-reconstructed from theme/trend/factor evidence; "
                "original influencer rule text is not fully available."
            ),
            "available_inputs": _lifecourt_available_inputs(stock_outputs),
            "missing_inputs": _lifecourt_missing_inputs(stock_outputs),
            "life_long_gates": [
                "LifeCourtScore in top 15%",
                "PCONF in top 30%",
                "CROWD below 80th percentile",
                "HYGIENE > 0",
            ],
        },
        "fusion_policy": {
            "cycle_weight": 0.65,
            "life_weight": 0.35,
            "conflict_policy": "cycle_filter_life_overlay",
            "matrix": [
                {"cycle": "strong", "life": "strong", "action": "core_plus_trading"},
                {"cycle": "strong", "life": "neutral", "action": "core_reduce_trading"},
                {"cycle": "neutral", "life": "strong", "action": "satellite_trial"},
                {"cycle": "weak", "life": "strong", "action": "high_liquidity_trial_only"},
                {"cycle": "weak", "life": "weak", "action": "clear_or_defensive"},
            ],
        },
        "layers": [
            {
                "key": "macro_direction",
                "title": "Macro direction",
                "weight": 0.30,
                "status": (
                    "provisional"
                    if cycle_input_evidence.macro_score_ready
                    else "partial"
                    if cycle_input_evidence.price_spread_ready
                    else "missing_inputs"
                ),
                "evidence": (
                    f"Livermore market gate is {gate_state}; "
                    + (
                        cycle_input_evidence.macro_score_evidence
                        if cycle_input_evidence.macro_score_evidence
                        else (
                            cycle_input_evidence.price_spread_evidence
                            if cycle_input_evidence.price_spread_ready
                            else "PMI, credit impulse and price spread are not landed for this framework."
                        )
                    )
                ),
                "available_inputs": macro_available,
                "missing_inputs": macro_missing,
            },
            {
                "key": "industry_cycle",
                "title": "Industry cycle",
                "weight": 0.35,
                "status": "provisional" if stock_outputs.sector_rank_payload is not None else "missing_inputs",
                "evidence": (
                    f"sector_rank is available for {sector_count} sectors; industry profit and revenue cycle "
                    "inputs are not landed."
                    if stock_outputs.sector_rank_payload is not None
                    else "sector_rank is unavailable, so the industry-cycle layer is blocked."
                ),
                "available_inputs": ["sector_rank"] if stock_outputs.sector_rank_payload is not None else [],
                "missing_inputs": ["industry_profit_cycle", "industry_revenue_cycle"],
            },
            {
                "key": "market_flow",
                "title": "Market flow",
                "weight": 0.20,
                "status": (
                    "provisional"
                    if stock_outputs.stock_candidates_payload is not None
                    or cycle_input_evidence.turnover_persistence_ready
                    else "missing_inputs"
                ),
                "evidence": (
                    (
                        f"Stock candidate review has {candidate_count} rows; "
                        if stock_outputs.stock_candidates_payload is not None
                        else "Stock candidate review is unavailable; "
                    )
                    + (
                        cycle_input_evidence.turnover_persistence_evidence
                        if cycle_input_evidence.turnover_persistence_ready
                        else "fund-flow confirmation is not landed."
                    )
                ),
                "available_inputs": market_flow_available,
                "missing_inputs": market_flow_missing,
            },
            {
                "key": "valuation_support",
                "title": "Valuation support",
                "weight": 0.15,
                "status": (
                    "provisional"
                    if stock_outputs.factor_screen_payload is not None
                    or cycle_input_evidence.valuation_percentile_history_ready
                    else "missing_inputs"
                ),
                "evidence": (
                    (
                        f"factor_screen_candidates has {factor_count} rows; "
                        if stock_outputs.factor_screen_payload is not None
                        else "factor_screen_candidates is unavailable; "
                    )
                    + (
                        cycle_input_evidence.valuation_percentile_history_evidence
                        if cycle_input_evidence.valuation_percentile_history_ready
                        else "valuation support is not confirmed."
                    )
                ),
                "available_inputs": valuation_available,
                "missing_inputs": valuation_missing,
            },
            {
                "key": "execution_constraints",
                "title": "Execution constraints",
                "weight": None,
                "status": "verification_pending",
                "evidence": (
                    f"Risk-exit evidence has {risk_count} signals; sizing, cost and liquidity controls still "
                    "need governed replay evidence."
                    if stock_outputs.risk_exit_payload is not None
                    else "Risk-exit evidence is unavailable; sizing, cost and liquidity controls remain pending."
                ),
                "available_inputs": ["risk_exit"] if stock_outputs.risk_exit_payload is not None else [],
                "missing_inputs": ["transaction_cost", "disclosure_lag", "liquidity_floor"],
            },
        ],
        "constraints": [
            "monthly core review; weekly satellite monitoring",
            "industry cap 25%",
            "single stock cap 5%",
            "exclude ST and suspended stocks",
            "exclude bottom 30% liquidity names until liquidity evidence is landed",
            "require 250 trading-day history before replay statistics are trusted",
        ],
        "boundary": (
            "Research-only framework assembled from available read-only evidence; no return, sizing or "
            "execution claim is produced until missing inputs are governed. LifeCourt layer uses "
            "proxy reconstruction until social/text pipelines are landed."
        ),
    }


def _lifecourt_available_inputs(stock_outputs: _ChoiceStockOutputs) -> list[str]:
    available: list[str] = []
    if stock_outputs.stock_candidates_payload is not None:
        available.append("stock_candidates")
    if stock_outputs.theme_breakout_payload is not None:
        available.append("theme_breakout")
    if stock_outputs.factor_screen_payload is not None:
        available.append("factor_screen_candidates")
    if stock_outputs.hybrid_fusion_payload is not None:
        available.append("hybrid_fusion")
    return available


def _lifecourt_missing_inputs(stock_outputs: _ChoiceStockOutputs) -> list[str]:
    missing = [
        "social_text_raw",
        "ocr_asr_pipeline",
        "bot_spam_detection",
        "margin_balance",
        "unlock_event_panel",
    ]
    if stock_outputs.sector_rank_payload is None:
        missing.append("sector_rank_for_regime")
    return missing


def _gate_supplement_breadth_limit(
    *,
    supplement: MarketGateSupplement | None,
    latest_trade_date: date | None,
) -> tuple[bool, bool]:
    if supplement is None or latest_trade_date is None or supplement.trade_date != latest_trade_date:
        return False, False
    return (
        supplement.breadth_5d is not None,
        supplement.limit_up_quality_ok is not None,
    )


def _build_rule_readiness(
    *,
    market_gate: dict[str, object],
    history_count: int,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
    supplement: MarketGateSupplement | None = None,
    latest_trade_date: date | None = None,
) -> list[dict[str, object]]:
    breadth_landed, limit_up_landed = _gate_supplement_breadth_limit(
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    gate_state = str(market_gate["state"])
    if gate_state == "NO_DATA":
        gate_status = "missing"
        gate_summary = "Broad-index history is unavailable, so the market gate cannot be evaluated."
        gate_missing_inputs = ["broad_index_history", "breadth", "limit_up_quality"]
    elif gate_state == "STALE":
        gate_status = "stale"
        gate_summary = "Broad-index history resolved, but the latest landed point is stale."
        gate_missing_inputs = ["breadth", "limit_up_quality"]
    elif gate_state == "PENDING_DATA":
        gate_status = "partial"
        gate_summary = f"Broad-index history is present but only {history_count} observations are landed."
        gate_missing_inputs = ["breadth", "limit_up_quality"]
    else:
        gate_missing_inputs = []
        if not breadth_landed:
            gate_missing_inputs.append("breadth")
        if not limit_up_landed:
            gate_missing_inputs.append("limit_up_quality")
        if gate_missing_inputs:
            gate_status = "partial"
            gate_summary = "Trend market gate is available; supplement breadth and/or limit-up inputs remain missing."
        else:
            gate_status = "ready"
            gate_summary = "All broad-index and supplement gate inputs are landed for the resolved trade date."
    sector_missing_inputs = _sector_missing_inputs(stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    stock_missing_inputs = _stock_missing_inputs(
        market_state=gate_state,
        stock_readiness=stock_readiness,
        stock_outputs=stock_outputs,
    )
    sector_status = _sector_status(stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    stock_status = _stock_status(market_state=gate_state, stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    sector_summary = (
        "Sector ranking is available from landed Choice sector inputs."
        if stock_outputs.sector_rank_payload is not None
        else _sector_unavailable_reason(stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    )
    stock_summary = (
        "Stock pivot candidate screening is available for landed Choice stock inputs."
        if stock_outputs.stock_candidates_payload is not None
        else _stock_unavailable_reason(
            market_state=gate_state,
            stock_readiness=stock_readiness,
            stock_outputs=stock_outputs,
        )
    )
    risk_status = "ready" if stock_outputs.risk_exit_payload is not None else "blocked"
    risk_summary = (
        "Risk and exit output is available from landed position snapshots and close history."
        if stock_outputs.risk_exit_payload is not None
        else _risk_unavailable_reason(stock_outputs.risk_exit_block_reason)
    )
    risk_missing_inputs = [] if stock_outputs.risk_exit_payload is not None else list(RISK_EXIT_REQUIRED_INPUTS)
    return [
        {
            "key": "market_gate",
            "title": "Market gate",
            "status": gate_status,
            "summary": gate_summary,
            "required_inputs": [
                "broad_index_history",
                "breadth",
                "limit_up_quality",
            ],
            "missing_inputs": gate_missing_inputs,
        },
        {
            "key": "sector_rank",
            "title": "Sector ranking",
            "status": sector_status,
            "summary": sector_summary,
            "required_inputs": ["sector_membership", "sector_strength"],
            "missing_inputs": sector_missing_inputs,
        },
        {
            "key": "stock_pivot",
            "title": "Stock pivot filters",
            "status": stock_status,
            "summary": stock_summary,
            "required_inputs": [
                "stock_universe",
                "stock_ohlcv",
                "stock_status",
                "limit_up_quality",
                "sector_rank",
                "market_gate",
                STOCK_CANDIDATE_POLICY_INACTIVE_INPUT_FAMILY,
            ],
            "missing_inputs": stock_missing_inputs,
        },
        {
            "key": "risk_exit",
            "title": "Risk and exit rules",
            "status": risk_status,
            "summary": risk_summary,
            "required_inputs": list(RISK_EXIT_REQUIRED_INPUTS),
            "missing_inputs": risk_missing_inputs,
        },
    ]


def _build_data_gaps(
    *,
    market_gate: dict[str, object],
    history_count: int,
    resolved_as_of_date: str | None,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
    cycle_input_evidence: _CycleInputEvidence,
    supplement: MarketGateSupplement | None = None,
    latest_trade_date: date | None = None,
) -> list[dict[str, str]]:
    breadth_landed, limit_up_landed = _gate_supplement_breadth_limit(
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    date_label = resolved_as_of_date or (latest_trade_date.isoformat() if latest_trade_date else "resolved date")
    gaps = []
    gaps.append(
        {
            "input_family": "price_spread",
            "status": "ready" if cycle_input_evidence.price_spread_ready else "missing",
            "evidence": cycle_input_evidence.price_spread_evidence
            or "CSI300 PE and China 10Y yield inputs are not both landed for price_spread.",
        }
    )
    gaps.append(
        {
            "input_family": "PMI",
            "status": "ready" if cycle_input_evidence.pmi_ready else "missing",
            "evidence": cycle_input_evidence.pmi_evidence
            or f"Manufacturing PMI ({PMI_SERIES_ID}) is not landed in fact_choice_macro_daily.",
        }
    )
    gaps.append(
        {
            "input_family": "credit_impulse",
            "status": "ready" if cycle_input_evidence.credit_impulse_ready else "missing",
            "evidence": cycle_input_evidence.credit_impulse_evidence
            or (
                f"Social financing YoY delta ({SOCIAL_FINANCING_YOY_SERIES_ID} or {M2_YOY_SERIES_ID}) "
                "requires at least two monthly observations."
            ),
        }
    )
    gaps.append(
        {
            "input_family": "macro_score",
            "status": "ready" if cycle_input_evidence.macro_score_ready else "missing",
            "evidence": cycle_input_evidence.macro_score_evidence
            or "MacroScore cannot be computed until PMI, credit impulse and/or price spread inputs land.",
        }
    )
    gaps.append(
        {
            "input_family": "turnover_persistence",
            "status": "ready" if cycle_input_evidence.turnover_persistence_ready else "missing",
            "evidence": cycle_input_evidence.turnover_persistence_evidence
            or "choice_stock_daily_observation turn history is not landed for turnover persistence.",
        }
    )
    gaps.append(
        {
            "input_family": "valuation_percentile_history",
            "status": "ready" if cycle_input_evidence.valuation_percentile_history_ready else "missing",
            "evidence": cycle_input_evidence.valuation_percentile_history_evidence
            or "choice_stock_factor_snapshot PE/PB history is not landed for valuation support.",
        }
    )
    if not breadth_landed:
        gaps.append(
            {
                "input_family": "breadth",
                "status": "missing",
                "evidence": "5-day breadth input family is not landed in DuckDB for this slice.",
            }
        )
    elif supplement is not None and supplement.breadth_5d is not None:
        gaps.append(
            {
                "input_family": "breadth",
                "status": "ready",
                "evidence": (
                    f"5-day breadth {supplement.breadth_5d:.4f} landed in "
                    f"fact_livermore_gate_supplement_daily for {date_label}."
                ),
            }
        )

    if not limit_up_landed:
        gaps.append(
            {
                "input_family": "limit_up_quality",
                "status": "missing",
                "evidence": _choice_stock_dependency_summary(
                    stock_readiness=stock_readiness,
                    families=["limit_up_quality"],
                    ready_summary="Choice limit-up quality catalog is confirmed, but DuckDB materialization is not landed.",
                ),
            }
        )
    elif supplement is not None and supplement.limit_up_quality_ok is not None:
        gaps.append(
            {
                "input_family": "limit_up_quality",
                "status": "ready",
                "evidence": (
                    f"Market gate limit-up quality flag ({supplement.limit_up_quality_ok}) landed in "
                    f"fact_livermore_gate_supplement_daily for {date_label}."
                ),
            }
        )
    if stock_outputs.risk_exit_payload is None:
        gaps.append(
            {
                "input_family": "position_risk",
                "status": "missing",
                "evidence": _risk_unavailable_reason(stock_outputs.risk_exit_block_reason),
            }
        )
    if stock_outputs.sector_rank_payload is None:
        gaps.append(
            {
                "input_family": "sector_strength",
                "status": _coverage_gap_status(stock_outputs.sector_coverage),
                "evidence": _sector_unavailable_reason(stock_readiness=stock_readiness, stock_outputs=stock_outputs),
            }
        )
    if stock_outputs.stock_candidates_payload is None and not _is_stock_candidate_policy_inactive_reason(
        stock_outputs.stock_candidate_block_reason
    ):
        gaps.append(
            {
                "input_family": _stock_unavailable_input_family(stock_outputs),
                "status": _coverage_gap_status(stock_outputs.stock_coverage),
                "evidence": _stock_unavailable_reason(
                    market_state=str(market_gate["state"]),
                    stock_readiness=stock_readiness,
                    stock_outputs=stock_outputs,
                ),
            }
        )
    if stock_outputs.theme_breakout_payload is not None:
        theme_is_proxy = bool(stock_outputs.theme_breakout_payload.get("is_proxy", True))
        theme_evidence_ready = _theme_breakout_evidence_ready(stock_outputs.theme_breakout_payload)
        gaps.append(
            {
                "input_family": "theme_taxonomy",
                "status": "ready" if (not theme_is_proxy and theme_evidence_ready) else "partial",
                "evidence": _theme_breakout_gap_evidence(stock_outputs.theme_breakout_payload),
            }
        )
    gate_state = str(market_gate["state"])
    if gate_state == "NO_DATA":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "missing",
                "evidence": "CA.CSI300 history is unavailable in fact_choice_macro_daily/choice_market_snapshot.",
            },
        )
    elif gate_state == "PENDING_DATA":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "partial",
                "evidence": f"CA.CSI300 history has {history_count} observations; 60 are required.",
            },
        )
    elif gate_state == "STALE":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "stale",
                "evidence": f"Latest CA.CSI300 input on {resolved_as_of_date} is marked stale.",
            },
        )
    return gaps


def _cycle_input_freshness_date(business_date: str, *, cadence: str) -> str:
    """Use month-end for provider rows keyed to the first day of their statistical month."""
    if cadence != "monthly":
        return business_date
    try:
        parsed = date.fromisoformat(business_date)
    except ValueError:
        return business_date
    if parsed.day != 1:
        return business_date
    return parsed.replace(day=monthrange(parsed.year, parsed.month)[1]).isoformat()


def _assess_input_freshness(
    *,
    cycle_input_evidence: _CycleInputEvidence,
    as_of_date: date | None,
) -> list[dict[str, object]]:
    """Assess key strategy inputs against the strategy-resolved trade_date (not wall clock)."""
    if as_of_date is None:
        return []
    entries: list[dict[str, object]] = []
    for input_family, input_label, cadence, business_date in cycle_input_evidence.input_business_dates:
        assessment = assess_freshness(business_date, as_of_date, cadence=cadence)
        entries.append(
            {
                "input_family": input_family,
                "input": input_label,
                "cadence": cadence,
                "business_date": business_date,
                "age_days": assessment.age_days,
                "tier": assessment.tier,
            }
        )
    return entries


def _input_freshness_severity(entry: dict[str, object]) -> tuple[int, int]:
    tier_rank = _INPUT_FRESHNESS_TIER_RANK.get(str(entry.get("tier") or ""), 0)
    age_days = entry.get("age_days")
    return tier_rank, age_days if isinstance(age_days, int) else -(10**9)


def _merge_input_freshness_into_data_gaps(
    *,
    data_gaps: list[dict[str, object]],
    input_freshness: list[dict[str, object]],
) -> None:
    """Extend existing data_gaps entries with freshness evidence; flag look-ahead-dated inputs."""
    worst_by_family: dict[str, dict[str, object]] = {}
    for entry in input_freshness:
        family = str(entry.get("input_family") or "")
        current = worst_by_family.get(family)
        if current is None or _input_freshness_severity(entry) > _input_freshness_severity(current):
            worst_by_family[family] = entry
    for gap in data_gaps:
        entry = worst_by_family.get(str(gap.get("input_family") or ""))
        if entry is None:
            continue
        gap["input"] = str(entry.get("input") or "")
        gap["business_date"] = str(entry.get("business_date") or "")
        gap["age_days"] = entry.get("age_days")
        gap["tier"] = str(entry.get("tier") or "")
    for entry in input_freshness:
        age_days = entry.get("age_days")
        if isinstance(age_days, int) and age_days < 0:
            data_gaps.append(
                {
                    "input_family": str(entry.get("input_family") or ""),
                    "input": str(entry.get("input") or ""),
                    "status": INPUT_FRESHNESS_LOOK_AHEAD_STATUS,
                    "evidence": (
                        f"{entry.get('input')} business_date {entry.get('business_date')} is later than the "
                        f"resolved trade_date (age_days={age_days}); flagged as a look-ahead risk."
                    ),
                    "business_date": str(entry.get("business_date") or ""),
                    "age_days": age_days,
                    "tier": str(entry.get("tier") or ""),
                }
            )


def _input_freshness_degradation_notes(
    input_freshness: list[dict[str, object]],
) -> list[dict[str, str | None]]:
    notes: list[dict[str, str | None]] = []
    for entry in input_freshness:
        tier = str(entry.get("tier") or "")
        if tier not in INPUT_FRESHNESS_DEGRADED_TIERS:
            continue
        family = str(entry.get("input_family") or "")
        category = _INPUT_FRESHNESS_NOTE_CATEGORY_BY_FAMILY.get(family, "关键输入")
        notes.append(
            {
                "severity": "warning",
                "code": INPUT_FRESHNESS_DEGRADED_DIAGNOSTIC_CODE,
                "message": (
                    f"{category} {entry.get('input')} 数据滞后 {entry.get('age_days')} 天（{tier}），信号质量降级"
                ),
                "input_family": family,
            }
        )
    return notes


def _degrade_quality_flag_for_input_freshness(
    quality_flag: str,
    input_freshness: list[dict[str, object]],
) -> str:
    """Any stale/expired key input downgrades an otherwise-ok result to warning; never upgrades."""
    if quality_flag != "ok":
        return quality_flag
    has_lagging_input = any(str(entry.get("tier") or "") in INPUT_FRESHNESS_DEGRADED_TIERS for entry in input_freshness)
    return "warning" if has_lagging_input else quality_flag


def _build_diagnostics(
    *,
    requested_as_of_date: str | None,
    resolved_as_of_date: str | None,
    market_gate: dict[str, object],
    history_count: int,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
    supplement: MarketGateSupplement | None = None,
    latest_trade_date: date | None = None,
) -> list[dict[str, str | None]]:
    diagnostics: list[dict[str, str | None]] = []
    breadth_landed, limit_up_landed = _gate_supplement_breadth_limit(
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    state = str(market_gate["state"])
    if requested_as_of_date is not None and resolved_as_of_date != requested_as_of_date:
        diagnostics.append(
            {
                "severity": "info",
                "code": "LIVERMORE_REQUESTED_DATE_RESOLVED_TO_AVAILABLE",
                "message": (
                    f"Requested {requested_as_of_date}; resolved to latest available broad-index input "
                    f"{resolved_as_of_date}."
                ),
                "input_family": "broad_index_history",
            }
        )
    if state == "NO_DATA":
        diagnostics.append(
            {
                "severity": "error",
                "code": "LIVERMORE_BROAD_INDEX_NO_DATA",
                "message": "CA.CSI300 history is unavailable in landed market-data tables.",
                "input_family": "broad_index_history",
            }
        )
    elif state == "PENDING_DATA":
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_BROAD_INDEX_INSUFFICIENT_HISTORY",
                "message": f"Need at least 60 broad-index observations; found {history_count}.",
                "input_family": "broad_index_history",
            }
        )
    elif state == "STALE":
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_BROAD_INDEX_STALE",
                "message": "Latest CA.CSI300 input is marked stale and cannot be treated as current.",
                "input_family": "broad_index_history",
            }
        )
    if not breadth_landed:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_BREADTH_MISSING",
                "message": "Breadth inputs are unavailable; the market gate is capped at the trend-only slice.",
                "input_family": "breadth",
            }
        )
    if not limit_up_landed:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_LIMIT_UP_QUALITY_MISSING",
                "message": _choice_stock_dependency_summary(
                    stock_readiness=stock_readiness,
                    families=["limit_up_quality"],
                    ready_summary=(
                        "Choice limit-up quality catalog is confirmed, but landed inputs are unavailable; "
                        "the market gate is capped at the trend-only slice."
                    ),
                ),
                "input_family": "limit_up_quality",
            }
        )
    if stock_outputs.risk_exit_payload is None:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_RISK_INPUTS_MISSING",
                "message": _risk_unavailable_reason(stock_outputs.risk_exit_block_reason),
                "input_family": "position_risk",
            }
        )
    if stock_outputs.sector_rank_payload is None:
        diagnostics.append(
            {
                "severity": "warning",
                "code": (
                    "LIVERMORE_SECTOR_RANK_INSUFFICIENT_DATA"
                    if stock_readiness.ready
                    and stock_outputs.sector_coverage is not None
                    and stock_outputs.sector_coverage.full_coverage
                    else "LIVERMORE_SECTOR_INPUTS_MISSING"
                ),
                "message": _sector_unavailable_reason(stock_readiness=stock_readiness, stock_outputs=stock_outputs),
                "input_family": "sector_strength",
            }
        )
    else:
        sector_formula_status = str(stock_outputs.sector_rank_payload.get("formula_status") or "").lower()
        if sector_formula_status != "signed_off":
            diagnostics.append(
                {
                    "severity": "warning",
                    "code": "LIVERMORE_SECTOR_RANK_PROVISIONAL_FORMULA",
                    "message": "Sector rank currently uses the provisional percentile formula over pctchange, turn, and amplitude.",
                    "input_family": "sector_strength",
                }
            )
    if stock_outputs.stock_candidates_payload is None:
        stock_reason = _stock_unavailable_reason(
            market_state=state,
            stock_readiness=stock_readiness,
            stock_outputs=stock_outputs,
        )
        if stock_reason:
            policy_paused = _is_stock_candidate_policy_inactive_reason(stock_outputs.stock_candidate_block_reason)
            diagnostics.append(
                {
                    "severity": "info" if policy_paused else "warning",
                    "code": (
                        "LIVERMORE_STOCK_INPUTS_MISSING"
                        if not stock_readiness.ready
                        or stock_outputs.stock_coverage is None
                        or not stock_outputs.stock_coverage.full_coverage
                        else (
                            "LIVERMORE_STOCK_PIVOT_PAUSED_BY_POLICY"
                            if policy_paused
                            else "LIVERMORE_STOCK_PIVOT_BLOCKED"
                        )
                    ),
                    "message": stock_reason,
                    "input_family": _stock_unavailable_input_family(stock_outputs),
                }
            )
    elif (
        _safe_int(stock_outputs.stock_candidates_payload.get("candidate_count")) == 0
        and (_safe_int(stock_outputs.stock_candidates_payload.get("insufficient_history_count")) or 0) > 0
    ):
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_STOCK_CANDIDATES_INSUFFICIENT_HISTORY",
                "message": "Stock inputs are landed, but some names still lack enough history for the 55-day breakout and MA120 filters.",
                "input_family": "stock_universe",
            }
        )
    if stock_outputs.theme_breakout_payload is not None:
        theme_is_proxy = bool(stock_outputs.theme_breakout_payload.get("is_proxy", True))
        theme_evidence_ready = _theme_breakout_evidence_ready(stock_outputs.theme_breakout_payload)
        if _theme_breakout_uses_current_overlay(stock_outputs.theme_breakout_payload):
            code = "LIVERMORE_THEME_BREAKOUT_CURRENT_OVERLAY"
            message = (
                "Theme breakout radar uses the governed current Tushare THS overlay; "
                "it is non-point-in-time, unavailable for historical replay, and remains partial evidence."
            )
        elif theme_is_proxy:
            code = "LIVERMORE_THEME_BREAKOUT_PROXY_FORMULA"
            message = (
                "Theme breakout radar is proxy-based over landed daily rows and level-1 sectors; "
                "it is not an intraday or authoritative concept taxonomy feed."
            )
        elif not theme_evidence_ready:
            code = "LIVERMORE_THEME_BREAKOUT_PARTIAL_REAL_EVIDENCE"
            message = (
                "Theme breakout radar uses landed concept rows, but real concept/movement evidence is still partial."
            )
        else:
            code = "LIVERMORE_THEME_BREAKOUT_REAL_CONCEPT_FORMULA"
            message = "Theme breakout radar uses landed concept membership and intraday movement rows; output remains observation-only."
        diagnostics.append(
            {
                "severity": "warning",
                "code": code,
                "message": f"{message} {_theme_breakout_evidence_summary(stock_outputs.theme_breakout_payload)}",
                "input_family": "theme_taxonomy",
            }
        )
    return diagnostics


def _sector_unavailable_reason(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["sector_membership", "sector_strength"],
            ready_summary="",
        )
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but sector ranking inputs are not materialized yet."
    if not stock_outputs.sector_coverage.full_coverage:
        return stock_outputs.sector_coverage.message
    return "Choice sector inputs are landed, but fewer than three rankable sectors are available."


def _stock_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.stock_candidate_block_reason:
        return stock_outputs.stock_candidate_block_reason
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status", "limit_up_quality"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but stock candidate inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    if stock_outputs.sector_rank_payload is None:
        return "Sector rank is unavailable, so stock candidates remain blocked."
    if market_state in {"NO_DATA", "PENDING_DATA", "STALE"}:
        return "Market gate is unavailable or stale, so stock candidates cannot be evaluated."
    return ""


def _stock_candidate_policy_inactive_reason(*, policy_name: str, market_state: str) -> str:
    active_states = "/".join(sorted(stock_candidate_policy_active_market_states(policy_name)))
    return (
        f"{STOCK_CANDIDATE_POLICY_INACTIVE_REASON_PREFIX}{policy_name} is inactive in {market_state}; "
        f"active market states are {active_states}."
    )


def _is_stock_candidate_policy_inactive_reason(reason: str) -> bool:
    return reason.startswith(STOCK_CANDIDATE_POLICY_INACTIVE_REASON_PREFIX)


def _theme_breakout_evidence_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    evidence_state = payload.get("evidence_state")
    if not isinstance(evidence_state, dict):
        return []
    entries: list[dict[str, object]] = []
    for input_family in ("concept_membership", "intraday_movement"):
        entry = evidence_state.get(input_family)
        if isinstance(entry, dict):
            entries.append(cast(dict[str, object], entry))
    return entries


def _theme_breakout_evidence_ready(payload: dict[str, object]) -> bool:
    entries = _theme_breakout_evidence_entries(payload)
    return bool(entries) and all(str(entry.get("status") or entry.get("state")) == "matched_rows" for entry in entries)


def _theme_breakout_evidence_summary(payload: dict[str, object]) -> str:
    parts: list[str] = []
    for entry in _theme_breakout_evidence_entries(payload):
        input_family = str(entry.get("input_family") or "theme_input")
        status = str(entry.get("status") or entry.get("state") or "unknown")
        row_count = _safe_int(entry.get("row_count") or entry.get("date_row_count")) or 0
        matched_count = _safe_int(entry.get("matched_row_count")) or 0
        parts.append(f"{input_family}={status} rows {row_count}/matched {matched_count}")
    return "Evidence state: " + "; ".join(parts) + "." if parts else "Evidence state unavailable."


def _theme_breakout_gap_evidence(payload: dict[str, object]) -> str:
    if _theme_breakout_uses_current_overlay(payload):
        return (
            "Theme breakout radar uses a governed current overlay that is non-point-in-time and "
            "not allowed for historical replay. "
            f"{_theme_breakout_evidence_summary(payload)}"
        )
    if _theme_breakout_evidence_entries(payload):
        return _theme_breakout_evidence_summary(payload)
    if bool(payload.get("is_proxy", True)):
        return (
            "Theme breakout radar is using proxy stock-name and Shenwan level-1 sector evidence; "
            "real concept and intraday movement input state is unavailable."
        )
    return "Theme breakout radar is using landed concept membership and intraday movement evidence."


def _theme_breakout_uses_current_overlay(payload: dict[str, object]) -> bool:
    raw_themes = payload.get("items")
    if isinstance(raw_themes, list) and any(
        isinstance(theme, dict) and theme.get("source_kind") == "tushare_current_overlay" for theme in raw_themes
    ):
        return True
    evidence_state = payload.get("evidence_state")
    if not isinstance(evidence_state, dict):
        return False
    concept_evidence = evidence_state.get("concept_membership")
    return isinstance(concept_evidence, dict) and (
        concept_evidence.get("status") == "current_overlay"
        or concept_evidence.get("concept_source_kind") == "tushare_current_overlay"
    )


def _theme_breakout_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "sector_membership", "sector_strength", "stock_ohlcv", "stock_status"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but theme breakout inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    if stock_outputs.sector_rank_payload is None:
        return "Sector rank is unavailable, so the theme breakout proxy is blocked."
    if market_state in {"NO_DATA", "PENDING_DATA", "STALE"}:
        return "Market gate is unavailable or stale, so theme breakout observations cannot be evaluated."
    if market_state == "OVERHEAT":
        return "Theme breakout execution is paused in OVERHEAT; historical replay showed this bucket is draggy."
    return "Theme breakout proxy produced no payload for the resolved inputs."


def _has_hybrid_fusion_candidate_source(
    *,
    stock_candidates_payload: dict[str, object] | None,
    factor_screen_payload: dict[str, object] | None,
    theme_breakout_payload: dict[str, object] | None,
) -> bool:
    return any(
        (
            _payload_item_count(stock_candidates_payload) > 0,
            _payload_item_count(factor_screen_payload) > 0,
            _theme_breakout_stock_item_count(theme_breakout_payload) > 0,
        )
    )


def _hybrid_fusion_unavailable_reason_from_payloads(
    *,
    market_state: str,
    stock_candidates_payload: dict[str, object] | None,
    factor_screen_payload: dict[str, object] | None,
    theme_breakout_payload: dict[str, object] | None,
) -> str:
    missing_sources: list[str] = []
    if _payload_item_count(stock_candidates_payload) <= 0:
        missing_sources.append("stock_candidates")
    if _payload_item_count(factor_screen_payload) <= 0:
        missing_sources.append("factor_screen_candidates")
    if _theme_breakout_stock_item_count(theme_breakout_payload) <= 0:
        missing_sources.append("theme_breakout")
    if len(missing_sources) == 3:
        return (
            "Hybrid fusion requires at least one landed candidate source: "
            "stock_candidates, factor_screen_candidates, or theme_breakout. "
            f"Missing candidate source rows: {', '.join(missing_sources)}."
        )
    if market_state not in {"WARM", "HOT"}:
        return f"Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is {market_state}."
    return ""


def _payload_item_count(payload: dict[str, object] | None) -> int:
    raw = payload.get("items") if isinstance(payload, dict) else None
    return len(raw) if isinstance(raw, list) else 0


def _theme_breakout_stock_item_count(payload: dict[str, object] | None) -> int:
    raw_themes = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_themes, list):
        return 0
    count = 0
    for raw_theme in raw_themes:
        if not isinstance(raw_theme, dict):
            continue
        raw_items = raw_theme.get("items")
        if isinstance(raw_items, list):
            count += sum(1 for raw_item in raw_items if isinstance(raw_item, dict))
    return count


def _stock_unavailable_input_family(stock_outputs: _ChoiceStockOutputs) -> str:
    if stock_outputs.stock_candidate_block_reason:
        if _is_stock_candidate_policy_inactive_reason(stock_outputs.stock_candidate_block_reason):
            return STOCK_CANDIDATE_POLICY_INACTIVE_INPUT_FAMILY
        return "limit_up_quality"
    return "stock_universe"


def _risk_unavailable_reason(specific_reason: str = "") -> str:
    reason = (
        f"The defended-bundle {MVP_RULE_LABEL} MVP remains blocked. Existing formal ledger "
        "position_snapshot/position_snapshot_agg are not accepted for Livermore A-share risk_exit "
        "because their governed schema is bond/ledger-shaped and lacks proven stock_code, "
        "Livermore entry_cost, and bars_since_entry semantics. Current accepted stock holding "
        "fact source remains livermore_position_snapshot plus choice_stock_daily_observation close_history."
    )
    if specific_reason:
        return f"{reason} Current blocker: {specific_reason}"
    return reason


def _coverage_gap_status(coverage: ChoiceStockMaterializationCoverage | None) -> str:
    if coverage is None:
        return "missing"
    if coverage.status == "partial":
        return "partial"
    return "missing"


def _sector_status(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.sector_rank_payload is not None:
        return "ready"
    if not stock_readiness.ready:
        return "missing"
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.status == "not_materialized":
        return "missing"
    if not stock_outputs.sector_coverage.full_coverage:
        return "partial"
    return "blocked"


def _stock_status(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.stock_candidates_payload is not None:
        return "ready"
    if not stock_readiness.ready:
        return "blocked"
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "blocked"
    if not stock_outputs.stock_coverage.full_coverage:
        return "partial"
    if stock_outputs.sector_rank_payload is None or market_state in {"NO_DATA", "PENDING_DATA", "STALE"}:
        return "blocked"
    return "blocked"


def _sector_missing_inputs(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> list[str]:
    if stock_outputs.sector_rank_payload is not None:
        return []
    if not stock_readiness.ready:
        return _choice_stock_missing_inputs(
            stock_readiness=stock_readiness,
            families=["sector_membership", "sector_strength"],
        )
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.full_coverage:
        return []
    return _missing_families_from_request_items(stock_outputs.sector_coverage.missing_request_items)


def _stock_missing_inputs(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> list[str]:
    if stock_outputs.stock_candidates_payload is not None:
        return []
    missing_inputs: list[str] = []
    if not stock_readiness.ready:
        missing_inputs.extend(
            _choice_stock_missing_inputs(
                stock_readiness=stock_readiness,
                families=["stock_universe", "stock_ohlcv", "stock_status", "limit_up_quality"],
            )
        )
    elif stock_outputs.stock_coverage is not None and not stock_outputs.stock_coverage.full_coverage:
        missing_inputs.extend(_missing_families_from_request_items(stock_outputs.stock_coverage.missing_request_items))
    if (
        stock_outputs.stock_candidate_block_reason
        and not _is_stock_candidate_policy_inactive_reason(stock_outputs.stock_candidate_block_reason)
        and "limit_ratio" not in missing_inputs
    ):
        missing_inputs.append("limit_ratio")
    if stock_outputs.sector_rank_payload is None and "sector_rank" not in missing_inputs:
        missing_inputs.append("sector_rank")
    if market_state in {"NO_DATA", "PENDING_DATA", "STALE"} and "market_gate" not in missing_inputs:
        missing_inputs.append("market_gate")
    return _unique_preserving_order(missing_inputs)


def _missing_families_from_request_items(items: list[str]) -> list[str]:
    families = [str(item).split(":", 1)[0] for item in items if item]
    return _unique_preserving_order(families)


def _limit_ratio(
    *,
    highlimit: object,
    lowlimit: object,
    prior_close: float | None,
    stock_code: str,
    stock_name: str,
    as_of_date: str,
) -> float | None:
    if prior_close is None or prior_close <= 0:
        return None
    high_value = _safe_float(highlimit)
    if high_value is not None and high_value > 0:
        ratio = abs((high_value - prior_close) / prior_close)
        if ratio > 0:
            return ratio
    low_value = _safe_float(lowlimit)
    if low_value is not None and low_value > 0:
        ratio = abs((prior_close - low_value) / prior_close)
        if ratio > 0:
            return ratio
    return _rule_derived_limit_ratio(
        stock_code=stock_code,
        stock_name=stock_name,
        as_of_date=as_of_date,
    )


def _rule_derived_limit_ratio(*, stock_code: str, stock_name: str, as_of_date: str) -> float | None:
    code = stock_code.strip().upper()
    if not code:
        return None
    if code.endswith(".BJ") or code.startswith(("8", "4", "920")):
        return 0.30
    if code.endswith(".SH") and code.startswith(("688", "689")):
        return 0.20
    if code.endswith(".SZ") and code.startswith(("300", "301")):
        return 0.20
    if _is_risk_warning_stock_name(stock_name) and _date_before(
        as_of_date, MAINBOARD_RISK_WARNING_LIMIT_RATIO_10_START
    ):
        return 0.05
    if code.endswith((".SH", ".SZ")):
        return 0.10
    return None


def _is_risk_warning_stock_name(stock_name: str) -> bool:
    normalized = stock_name.strip().upper()
    return normalized.startswith("*ST") or normalized.startswith("ST")


def _date_before(value: str, threshold: date) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed < threshold


def _safe_float(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number


def _safe_int(value: object) -> int | None:
    number = _safe_float(value)
    return None if number is None else int(number)


def _safe_int_or_none(value: object) -> int | None:
    return _safe_int(value)


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y", "是"}


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _quality_flag_for_market_gate(state: str) -> str:
    if state == "STALE":
        return "stale"
    if state in {"NO_DATA", "PENDING_DATA"}:
        return "warning"
    return "ok"


def _vendor_status_for_state(state: str) -> str:
    if state == "STALE":
        return "vendor_stale"
    if state == "NO_DATA":
        return "vendor_unavailable"
    return "ok"


def _aggregate_lineage(values: list[str], *, empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)


def livermore_data_version(duckdb_path: str) -> str:
    """Stable cross-process version fingerprint for persisted Livermore data."""
    path = Path(duckdb_path)
    try:
        stat = path.stat()
    except OSError:
        return "missing"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _livermore_business_input_signature(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except OSError:
        return "missing"
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def livermore_business_inputs_version() -> str:
    input_paths = (
        DEFAULT_STRATEGY_YAML,
        _OFFICIAL_AVAILABILITY_MANIFEST_PATH,
        _OFFICIAL_RELEASES_MANIFEST_PATH,
    )
    return "|".join(
        f"{path.name}={_livermore_business_input_signature(path)}"
        for path in input_paths
    )
