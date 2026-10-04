"""Route-support helpers for `/ui/market-data` livermore endpoints.

This module owns the non-endpoint assembly logic that previously lived in
`backend.app.api.routes.market_data_livermore`: cache-key builders, the
stock-analysis-workbench cache wrapper, the position-snapshot CSV path guard,
the macro-context loader, and the workbench-summary payload builders. The
route module re-imports every helper into its own namespace so existing
monkeypatch/import contracts keep working. The background market-home warmup
service also imports `_cached_stock_analysis_workbench` from here directly
(not from the route module), so a route cache-key/signature change and a
warmup change both resolve to this single implementation.

Intentionally not moved here (their internals must resolve through the route
module globals for existing tests): `_livermore_strategy_cache_key` and
`_livermore_signal_confluence_cache_key`.

This module must not import the route module (no circular imports). Shared
response-cache and performance helpers live below the API layer so this service
can import them directly without depending on route package initialization.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any, cast

from backend.app.observability.perf_logging import timed_api_call
from backend.app.observability.response_cache import market_home_response_cache
from backend.app.repositories.duckdb_read_context import resolve_effective_read_path
from backend.app.repositories.system_read_publication_repo import current_system_read_context
from backend.app.services.livermore_signal_confluence_service import (
    LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION,
    LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
)
from backend.app.services.macro_bond_linkage_service import get_macro_context_v1
from backend.app.services.market_data_livermore_service import (
    EXECUTION_STOCK_CANDIDATE_POLICY,
    capture_livermore_external_inputs,
    livermore_data_version,
    theme_overlay_fingerprint,
    theme_overlay_reader_from_settings,
)
from backend.app.services.pretrade_qualification import (
    STRATEGY_CALCULATION_MODE,
    canonical_pretrade_confluence_projection_sha256,
    normalize_pretrade_qualification,
    qualify_sealed_pretrade_read,
    unavailable_pretrade_qualification,
)
from backend.app.services.stock_analysis_workbench_service import (
    DEFAULT_INCLUDE_KEYS,
    WORKBENCH_CACHE_VERSION,
    WORKBENCH_RULE_VERSION,
)

# `livermore_business_inputs_version` and `stock_analysis_workbench_envelope`
# are intentionally NOT imported at module level: this module is not
# hot-reloaded by the test suite's `load_module` helper (unlike the route
# module, which is), so a frozen binding would silently keep calling a stale
# function after a test swaps in a fresh service-module instance. The two
# call sites below re-resolve them from `sys.modules` on every call instead.

# Kept mutable (module-global aliases, not direct references) so tests can
# monkeypatch the theme-overlay hooks for the workbench cache-build path the
# same way the route module's own aliases are patched for its other paths.
_theme_overlay_reader_from_settings = theme_overlay_reader_from_settings
_theme_overlay_fingerprint = theme_overlay_fingerprint

# Freshness comes from DuckDB, Choice catalog, repository business-input, and
# theme-overlay fingerprints. Keep unchanged snapshots for one day.
STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS = 24 * 60 * 60.0


def _resolve_livermore_position_csv_path(*, data_input_root: Path, csv_path: str) -> Path:
    base_root = Path(data_input_root).resolve()
    allowed_root = (base_root / "livermore").resolve()
    raw_path = Path(csv_path).expanduser()
    candidate = raw_path.resolve() if raw_path.is_absolute() else (base_root / raw_path).resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("Livermore position snapshot CSV must be under data_input/livermore.") from exc
    return candidate


def _invalidate_livermore_response_cache() -> None:
    market_home_response_cache.invalidate()


def _choice_stock_catalog_fingerprint(catalog_file: object) -> str:
    try:
        stat = Path(str(catalog_file)).stat()
    except OSError:
        return "missing"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _stock_analysis_workbench_cache_key(
    *,
    duckdb_path: str,
    catalog_file: object,
    as_of_date: str | None,
    include: str | None,
    sector_window_days: int,
    top_k: int,
    theme_overlay_fingerprint: str = "theme-overlay-reader:not-configured",
    pretrade_authority_fingerprint: str = "pretrade:none",
) -> str:
    # Re-resolve through the current `sys.modules` entry on every call: unlike
    # the route module (which tests reload per-call via `load_module`), this
    # module is not reloaded, so a frozen module-level binding would keep
    # pointing at a stale service-module instance after a hot-reload swap
    # (e.g. business-input-signature tests).
    from backend.app.services.market_data_livermore_service import (
        livermore_business_inputs_version,
        livermore_data_version,
    )

    include_keys = set(DEFAULT_INCLUDE_KEYS)
    include_keys.update(item.strip() for item in str(include or "").split(",") if item.strip())
    include_token = ",".join(sorted(include_keys))
    return (
        f"livermore/workbench::as_of={as_of_date or ''}::include={include_token}"
        f"::sector_window_days={sector_window_days}::top_k={top_k}"
        f"::catalog={catalog_file}::catalog_version={_choice_stock_catalog_fingerprint(catalog_file)}"
        f"::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
        f"::theme_overlay={theme_overlay_fingerprint}"
        f"::business_inputs={livermore_business_inputs_version()}"
        f"::rule_version={WORKBENCH_RULE_VERSION}"
        f"::cache_version={WORKBENCH_CACHE_VERSION}"
        f"::{pretrade_authority_fingerprint}"
    )


def _selected_pretrade_external_read(
    *,
    catalog_file: object,
    as_of_date: str | None,
) -> tuple[dict[str, object], Mapping[str, object] | None, str | None, str]:
    context = current_system_read_context()
    sealed = normalize_pretrade_qualification(
        context.pretrade_availability if context is not None else None
    )
    target_date = as_of_date or str(sealed.get("target_date") or "") or None
    if context is None:
        qualification = unavailable_pretrade_qualification(
            "system_read_generation_missing"
        )
    elif sealed.get("status") == "unavailable":
        qualification = sealed
    elif target_date is None:
        qualification = unavailable_pretrade_qualification(
            "pretrade_qualification_target_date_missing"
        )
    else:
        qualification = qualify_sealed_pretrade_read(
            evidence=sealed,
            target_date=target_date,
            stock_candidate_policy=EXECUTION_STOCK_CANDIDATE_POLICY,
        )
    captured_external_inputs: Mapping[str, object] | None = None
    if qualification.get("status") in {"ready", "ready_empty"}:
        captured = capture_livermore_external_inputs(str(catalog_file))
        snapshot = qualification.get("input_snapshot")
        expected_profiles = (
            snapshot.get("external_sources")
            if isinstance(snapshot, Mapping)
            else None
        )
        if captured.get("identity_profiles") != expected_profiles:
            qualification = unavailable_pretrade_qualification(
                "pretrade_external_source_identity_mismatch"
            )
        else:
            captured_external_inputs = captured
    authority_fingerprint = (
        "pretrade="
        f"{getattr(context, 'generation', 'none')}:"
        f"{qualification.get('status')}:"
        f"{qualification.get('evidence_sha256') or qualification.get('reason')}"
    )
    return (
        qualification,
        captured_external_inputs,
        target_date,
        authority_fingerprint,
    )


def _livermore_strategy_cache_key(
    *,
    duckdb_path: str,
    catalog_file: object,
    as_of_date: str | None,
    theme_overlay_fingerprint: str = "theme-overlay-reader:not-configured",
) -> str:
    from backend.app.services.market_data_livermore_service import (
        livermore_business_inputs_version,
        livermore_data_version,
    )

    return (
        f"livermore/strategy::as_of={as_of_date or ''}::catalog={catalog_file}::{duckdb_path}"
        f"::data_version={livermore_data_version(duckdb_path)}"
        f"::theme_overlay={theme_overlay_fingerprint}"
        f"::business_inputs={livermore_business_inputs_version()}"
    )


def _livermore_signal_confluence_cache_key(
    *,
    duckdb_path: str,
    catalog_file: object,
    as_of_date: str | None,
    theme_overlay_fingerprint: str = "theme-overlay-reader:not-configured",
    pretrade_authority_fingerprint: str = "pretrade:none",
) -> str:
    from backend.app.services.market_data_livermore_service import (
        livermore_business_inputs_version,
        livermore_data_version,
    )

    return (
        f"livermore/signal-confluence::as_of={as_of_date or ''}::catalog={catalog_file}::{duckdb_path}"
        f"::data_version={livermore_data_version(duckdb_path)}"
        f"::theme_overlay={theme_overlay_fingerprint}"
        f"::business_inputs={livermore_business_inputs_version()}"
        f"::rule_version={LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION}"
        f"::cache_version={LIVERMORE_SIGNAL_CONFLUENCE_CACHE_VERSION}"
        f"::{pretrade_authority_fingerprint}"
    )


def _cached_stock_analysis_workbench(
    *,
    settings: object,
    as_of_date: str | None,
    include: str | None,
    sector_window_days: int,
    top_k: int,
) -> tuple[dict[str, object], str, float, float, float]:
    # Also re-resolved per call (see `_stock_analysis_workbench_cache_key`):
    # this module is not hot-reloaded by the test suite's `load_module` helper,
    # so a frozen module-level binding would silently keep calling a stale
    # `stock_analysis_workbench_envelope` after a test swaps in a fresh
    # `stock_analysis_workbench_service` module instance.
    from backend.app.services.stock_analysis_workbench_service import (
        stock_analysis_workbench_envelope,
    )

    duckdb_path = str(settings.duckdb_path)  # type: ignore[attr-defined]
    catalog_file = settings.choice_stock_catalog_file  # type: ignore[attr-defined]
    overlay_started = time.perf_counter()
    theme_overlay_reader = _theme_overlay_reader_from_settings(settings)
    overlay_fingerprint = _theme_overlay_fingerprint(theme_overlay_reader)
    overlay_ms = (time.perf_counter() - overlay_started) * 1000
    compute_ms = 0.0
    (
        pretrade_qualification,
        captured_external_inputs,
        _pretrade_target_date,
        authority_fingerprint,
    ) = _selected_pretrade_external_read(
        catalog_file=catalog_file,
        as_of_date=as_of_date,
    )

    def build() -> dict[str, object]:
        nonlocal compute_ms
        compute_started = time.perf_counter()
        try:
            return timed_api_call(
                "/ui/market-data/stock-analysis/workbench",
                lambda: stock_analysis_workbench_envelope(
                    duckdb_path=duckdb_path,
                    as_of_date=as_of_date,
                    choice_stock_catalog_file=catalog_file,
                    include=include,
                    sector_window_days=sector_window_days,
                    top_k=top_k,
                    theme_overlay_reader=theme_overlay_reader,
                    _pretrade_qualification=pretrade_qualification,
                    _captured_external_inputs=captured_external_inputs,
                ),
            )
        finally:
            compute_ms = (time.perf_counter() - compute_started) * 1000

    cache_started = time.perf_counter()
    payload, cache_status = market_home_response_cache.get_or_build_with_status(
        _stock_analysis_workbench_cache_key(
            duckdb_path=duckdb_path,
            catalog_file=catalog_file,
            as_of_date=as_of_date,
            include=include,
            sector_window_days=sector_window_days,
            top_k=top_k,
            theme_overlay_fingerprint=overlay_fingerprint,
            pretrade_authority_fingerprint=authority_fingerprint,
        ),
        build,
        ttl_seconds=STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS,
    )
    cache_ms = (time.perf_counter() - cache_started) * 1000
    return payload, cache_status, compute_ms, overlay_ms, cache_ms


def _livermore_stock_detail_cache_key(
    *, duckdb_path: str, stock_code: str, as_of_date: str | None, lookback: int
) -> str:
    return (
        f"livermore/stock-detail::stock={stock_code}::as_of={as_of_date or ''}"
        f"::lookback={lookback}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _stock_kline_analysis_cache_key(*, duckdb_path: str, stock_code: str, as_of_date: str | None, lookback: int) -> str:
    return (
        f"stock-analysis/kline::stock={stock_code}::as_of={as_of_date or ''}::lookback={lookback}"
        f"::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _stock_heavyweight_trends_cache_key(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    window_days: int,
    sector_limit: int,
    stocks_per_sector: int,
) -> str:
    return (
        f"stock-analysis/heavyweight-trends::as_of={as_of_date or ''}::window_days={window_days}"
        f"::sector_limit={sector_limit}::stocks_per_sector={stocks_per_sector}"
        f"::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_candidate_history_cache_key(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    evaluation_as_of_date: str | None,
    limit: int,
) -> str:
    return (
        f"livermore/candidate-history::stock={stock_code or ''}"
        f"::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::evaluation={evaluation_as_of_date or ''}::limit={limit}::{duckdb_path}"
        f"::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_strategy_score_cache_key(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
) -> str:
    return (
        f"livermore/strategy-score::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::market_state={current_market_state or ''}::min_sample={min_sample}"
        f"::primary_horizon={primary_horizon}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_strategy_optimization_cache_key(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
) -> str:
    return (
        f"livermore/strategy-optimization::from={snapshot_from or ''}::to={snapshot_to or ''}"
        f"::market_state={current_market_state or ''}::min_sample={min_sample}"
        f"::primary_horizon={primary_horizon}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_cycle_proxy_backtest_cache_key(
    *, duckdb_path: str, snapshot_from: str | None, snapshot_to: str | None
) -> str:
    return f"livermore/cycle-proxy-backtest::from={snapshot_from or ''}::to={snapshot_to or ''}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"


def _livermore_portfolio_backtest_cache_key(
    *, duckdb_path: str, snapshot_from: str | None, snapshot_to: str | None
) -> str:
    return (
        f"livermore/candidate-history-portfolio-backtest::from={snapshot_from or ''}"
        f"::to={snapshot_to or ''}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_sector_rank_series_cache_key(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    window_days: int,
    sector_code: str | None,
    top_k: int,
) -> str:
    return (
        f"livermore/sector-rank-series::as_of={as_of_date or ''}::window_days={window_days}"
        f"::sector={sector_code or ''}::top_k={top_k}::{duckdb_path}::data_version={livermore_data_version(duckdb_path)}"
    )


def _livermore_macro_context_v1_for_date(as_of_date: str) -> dict[str, object] | None:
    as_of_text = _optional_text(as_of_date)
    if not as_of_text:
        return None
    return get_macro_context_v1(
        date.fromisoformat(as_of_text[:10]),
        as_of_date=as_of_text[:10],
    )


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _count_array(value: object) -> int | None:
    if isinstance(value, list):
        return len(value)
    return None


def _count_mapping(value: object) -> int | None:
    if isinstance(value, dict):
        return len(value)
    return None


def _count_array_or_mapping(value: object) -> int | None:
    if isinstance(value, (list, dict)):
        return len(value)
    return None


def _present(value: object) -> bool:
    return value not in (None, "", [], {})


def _optional_count(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        parsed = int(value)
    elif isinstance(value, (int, float, str)):
        try:
            parsed = int(value)
        except ValueError:
            return None
    else:
        return None
    return max(parsed, 0)


def _item_count(value: object) -> int | None:
    mapping = _mapping(value)
    if "items" in mapping:
        return _count_array(mapping.get("items"))
    return _count_array_or_mapping(value)


def _active_data_gap_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(1 for item in value if not (isinstance(item, dict) and str(item.get("status") or "").lower() == "ready"))


def _active_diagnostic_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(
        1 for item in value if not (isinstance(item, dict) and str(item.get("severity") or "").lower() == "info")
    )


def _actionable_unsupported_output_count(value: object) -> int | None:
    if not isinstance(value, list):
        return None
    return sum(
        1 for item in value if not (isinstance(item, dict) and _is_known_livermore_policy_pause(item.get("reason")))
    )


def _is_known_livermore_policy_pause(reason: object) -> bool:
    lower = str(reason or "").strip().lower()
    return (
        ("stock candidate policy" in lower and "inactive in overheat" in lower)
        or "mean reversion watchlist is paused" in lower
        or ("theme breakout execution is paused" in lower and "overheat" in lower)
        or ("hybrid fusion is observation-only" in lower and "warm/hot" in lower)
        or ("uptrend momentum watchlist is paused" in lower and "warm or hot" in lower)
    )


def _sum_optional_counts(*values: int | None) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _livermore_workbench_strategy_summary(result: dict[str, object]) -> dict[str, object]:
    data_gap_count = _active_data_gap_count(result.get("data_gaps"))
    diagnostic_count = _active_diagnostic_count(result.get("diagnostics"))
    unsupported_output_count = _actionable_unsupported_output_count(result.get("unsupported_outputs"))
    return {
        "kind": "strategy",
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "requested_as_of_date": (
            result.get("requested_as_of_date") if _present(result.get("requested_as_of_date")) else None
        ),
        "strategy_name": result.get("strategy_name") if _present(result.get("strategy_name")) else None,
        "basis": result.get("basis") if _present(result.get("basis")) else None,
        "market_gate_present": _present(result.get("market_gate")),
        "rule_readiness_count": _count_array(result.get("rule_readiness")),
        "module_state_count": _count_array(result.get("module_states")),
        "factor_screen_candidate_count": _item_count(result.get("factor_screen_candidates")),
        "hybrid_fusion_candidate_count": _item_count(result.get("hybrid_fusion_candidates")),
        "sector_rank_count": _item_count(result.get("sector_rank")),
        "data_gap_count": data_gap_count,
        "diagnostic_count": diagnostic_count,
        "supported_output_count": _count_array(result.get("supported_outputs")),
        "unsupported_output_count": unsupported_output_count,
        "actionable_boundary_count": _sum_optional_counts(data_gap_count, diagnostic_count, unsupported_output_count),
        "total_data_gap_count": _count_array(result.get("data_gaps")),
        "total_diagnostic_count": _count_array(result.get("diagnostics")),
        "total_unsupported_output_count": _count_array(result.get("unsupported_outputs")),
        "risk_exit_present": _present(result.get("risk_exit")),
    }


def _livermore_workbench_signal_summary(result: dict[str, object]) -> dict[str, object]:
    replay = _mapping(result.get("replay_evidence"))
    return {
        "kind": "signal_confluence",
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "macro_context_present": _present(result.get("macro_context")),
        "adversarial_context_present": _present(result.get("adversarial_context")),
        "strategy_context_present": _present(result.get("strategy_context")),
        "closed_loop_state_present": _present(result.get("closed_loop_state")),
        "entry_observation_count": _count_array(result.get("entry_observations")),
        "exit_observation_count": _count_array(result.get("exit_observations")),
        "replay_evidence_present": _present(result.get("replay_evidence")),
        "replay_evidence_row_count": _optional_count(replay.get("row_count")) if replay else None,
        "replay_evidence_sample_count": _count_array(replay.get("sample_items")) if replay else None,
        "diagnostic_count": _count_array(result.get("diagnostics")),
        "position_size_hint_present": _present(result.get("position_size_hint")),
    }


def _livermore_workbench_candidate_history_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "candidate_history",
        "item_count": _count_array(result.get("items")),
        "summary_present": _present(result.get("summary")),
        "backtest_window_summary_present": _present(result.get("backtest_window_summary")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
        "stock_code_present": _present(result.get("stock_code")),
        "limit": _optional_count(result.get("limit")),
    }


def _livermore_workbench_strategy_score_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "strategy_score",
        "row_count": _count_array(result.get("rows")),
        "current_market_state_row_count": _count_array(result.get("current_market_state_rows")),
        "scope_count": _count_array_or_mapping(result.get("stock_candidate_state_scopes")),
        "review_thresholds_present": _present(result.get("review_thresholds")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
        "primary_horizon": result.get("primary_horizon") if _present(result.get("primary_horizon")) else None,
        "min_sample": _optional_count(result.get("min_sample")),
        "backtest_window_summary_present": _present(result.get("backtest_window_summary")),
    }


def _livermore_workbench_strategy_optimization_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "strategy_optimization",
        "strategy_summary_count": _count_array(result.get("strategy_summaries")),
        "slice_count": _count_array(result.get("slices")),
        "optimization_review_item_count": _count_array(result.get("recommendations")),
        "pending_summary_present": _present(result.get("pending_summary")),
        "sample_maturity_present": _present(result.get("sample_maturity")),
        "review_thresholds_present": _present(result.get("review_thresholds")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_cycle_proxy_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "cycle_proxy_backtest",
        "status": result.get("status") if _present(result.get("status")) else None,
        "full_strategy_status": (
            result.get("full_strategy_status") if _present(result.get("full_strategy_status")) else None
        ),
        "proxy_signal_kind": result.get("proxy_signal_kind") if _present(result.get("proxy_signal_kind")) else None,
        "proxy_rule_present": _present(result.get("proxy_rule")),
        "summary_present": _present(result.get("summary")),
        "nav_series_count": _count_array(result.get("nav_series")),
        "warning_count": _count_array(result.get("warnings")),
        "missing_input_count": _count_array(result.get("missing_full_strategy_inputs")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_portfolio_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "candidate_history_portfolio_backtest",
        "status": result.get("status") if _present(result.get("status")) else None,
        "full_strategy_status": (
            result.get("full_strategy_status") if _present(result.get("full_strategy_status")) else None
        ),
        "signal_kind": result.get("signal_kind") if _present(result.get("signal_kind")) else None,
        "rebalance_rule_present": _present(result.get("rebalance_rule")),
        "weighting_rule_present": _present(result.get("weighting_rule")),
        "summary_present": _present(result.get("summary")),
        "nav_series_count": _count_array(result.get("nav_series")),
        "rebalance_log_count": _count_array(result.get("rebalance_log")),
        "warning_count": _count_array(result.get("warnings")),
        "missing_input_count": _count_array(result.get("missing_full_strategy_inputs")),
        "snapshot_from": result.get("snapshot_from") if _present(result.get("snapshot_from")) else None,
        "snapshot_to": result.get("snapshot_to") if _present(result.get("snapshot_to")) else None,
    }


def _livermore_workbench_sector_series_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "sector_rank_series",
        "state": result.get("state") if _present(result.get("state")) else None,
        "as_of_date": result.get("as_of_date") if _present(result.get("as_of_date")) else None,
        "series_count": _count_array(result.get("series")),
        "top_k": _optional_count(result.get("top_k")),
        "window_days": _optional_count(result.get("window_days")),
        "formula_version": result.get("formula_version") if _present(result.get("formula_version")) else None,
        "unsupported_note_count": _count_array(result.get("unsupported_notes")),
    }


def _livermore_workbench_summary(result: dict[str, object], *, summary_kind: str) -> dict[str, object]:
    if summary_kind == "strategy":
        return _livermore_workbench_strategy_summary(result)
    if summary_kind == "signal_confluence":
        return _livermore_workbench_signal_summary(result)
    if summary_kind == "candidate_history":
        return _livermore_workbench_candidate_history_summary(result)
    if summary_kind == "strategy_score":
        return _livermore_workbench_strategy_score_summary(result)
    if summary_kind == "strategy_optimization":
        return _livermore_workbench_strategy_optimization_summary(result)
    if summary_kind == "cycle_proxy_backtest":
        return _livermore_workbench_cycle_proxy_summary(result)
    if summary_kind == "candidate_history_portfolio_backtest":
        return _livermore_workbench_portfolio_summary(result)
    if summary_kind == "sector_rank_series":
        return _livermore_workbench_sector_series_summary(result)
    return {
        "kind": summary_kind,
        "field_count": _count_mapping(result),
    }


def _with_livermore_workbench_summary(
    envelope: dict[str, object],
    *,
    summary_kind: str,
) -> dict[str, object]:
    result_value = envelope.get("result")
    if not isinstance(result_value, dict):
        return envelope
    result_value["workbench_summary"] = _livermore_workbench_summary(result_value, summary_kind=summary_kind)
    return envelope


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _qualified_livermore_signal_confluence(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    catalog_file: object,
    theme_overlay_reader: Any,
    pretrade_qualification: Mapping[str, object] | None = None,
    captured_external_inputs: Mapping[str, object] | None = None,
    target_date: str | None = None,
    envelope_builder: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]:
    if pretrade_qualification is None:
        (
            qualification,
            resolved_external_inputs,
            resolved_target_date,
            _authority_fingerprint,
        ) = _selected_pretrade_external_read(
            catalog_file=catalog_file,
            as_of_date=as_of_date,
        )
        captured_external_inputs = captured_external_inputs or resolved_external_inputs
        target_date = target_date or resolved_target_date
    else:
        qualification = dict(pretrade_qualification)
    if target_date is None:
        target_date = as_of_date or str(qualification.get("target_date") or "") or None
    rule_identity = qualification.get("rule_identity")
    calculation_mode = (
        rule_identity.get("strategy_calculation_mode")
        if isinstance(rule_identity, Mapping)
        else None
    )
    use_attested_replay = (
        qualification.get("status") in {"ready", "ready_empty"}
        and calculation_mode == STRATEGY_CALCULATION_MODE
    )
    if envelope_builder is None:
        from backend.app.services.livermore_signal_confluence_service import (
            livermore_signal_confluence_envelope,
        )

        envelope_builder = livermore_signal_confluence_envelope
    envelope = envelope_builder(
        duckdb_path=duckdb_path,
        as_of_date=target_date,
        choice_stock_catalog_file=catalog_file,
        theme_overlay_reader=theme_overlay_reader,
        _strategy_calculation_mode=(
            STRATEGY_CALCULATION_MODE if use_attested_replay else None
        ),
        _captured_external_inputs=(
            captured_external_inputs if use_attested_replay else None
        ),
    )
    result = dict(cast(Mapping[str, object], envelope.get("result") or {}))
    resolved_date = str(result.get("as_of_date") or "") or None
    qualified_outputs = qualification.get("outputs")
    projection_matches = (
        use_attested_replay
        and resolved_date == target_date
        and isinstance(qualified_outputs, Mapping)
        and qualified_outputs.get("signal_confluence_sha256")
        == canonical_pretrade_confluence_projection_sha256(envelope)
    )
    if qualification.get("status") == "ready" and projection_matches:
        qualified_envelope = {
            **envelope,
            "result": {
                **result,
                "pretrade_qualification": {
                    "status": qualification.get("status"),
                    "reason": qualification.get("reason"),
                    "evidence_sha256": qualification.get("evidence_sha256"),
                },
            },
        }
    else:
        reason = (
            "pretrade_qualification_ready_empty"
            if qualification.get("status") == "ready_empty" and projection_matches
            else (
                "pretrade_signal_confluence_projection_mismatch"
                if use_attested_replay
                else str(
                    qualification.get("reason")
                    or "completed_pretrade_provenance_missing"
                )
            )
        )
        raw_strategy_context = result.get("strategy_context") or {}
        if not isinstance(raw_strategy_context, Mapping):
            raise TypeError("strategy_context must be a mapping")
        strategy_context = dict(raw_strategy_context)
        qualified_envelope = {
            **envelope,
            "result": {
                **result,
                "strategy_context": {
                    **strategy_context,
                    "allows_new_entry_observations": False,
                    "new_entry_observation_allowed": False,
                    "position_size_hint": None,
                },
                "closed_loop_state": {
                    "status": "blocked_by_pretrade_qualification",
                    "reason": reason,
                },
                "position_size_hint": None,
                "entry_observations": [],
                "exit_observations": [],
                "pretrade_qualification": {
                    "status": (
                        "ready_empty"
                        if qualification.get("status") == "ready_empty"
                        else "unavailable"
                    ),
                    "reason": reason,
                    "evidence_sha256": qualification.get("evidence_sha256"),
                },
            },
        }
    return _with_livermore_workbench_summary(
        qualified_envelope,
        summary_kind="signal_confluence",
    )


def _cached_livermore_signal_confluence(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    catalog_file: object,
    theme_overlay_reader: Any,
    theme_overlay_fingerprint: str,
    selected_pretrade_read: tuple[
        dict[str, object], Mapping[str, object] | None, str | None, str
    ],
    force_refresh: bool = False,
    qualified_builder: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]:
    qualification, captured_external_inputs, target_date, authority_fingerprint = (
        selected_pretrade_read
    )
    effective_duckdb_path = str(resolve_effective_read_path(duckdb_path))
    key = _livermore_signal_confluence_cache_key(
        duckdb_path=effective_duckdb_path,
        catalog_file=catalog_file,
        as_of_date=as_of_date,
        theme_overlay_fingerprint=theme_overlay_fingerprint,
        pretrade_authority_fingerprint=authority_fingerprint,
    )
    if qualified_builder is None:
        qualified_builder = _qualified_livermore_signal_confluence

    def build() -> dict[str, object]:
        return qualified_builder(
            duckdb_path=effective_duckdb_path,
            as_of_date=as_of_date,
            catalog_file=catalog_file,
            theme_overlay_reader=theme_overlay_reader,
            pretrade_qualification=qualification,
            captured_external_inputs=captured_external_inputs,
            target_date=target_date,
        )

    if force_refresh:
        generation = market_home_response_cache.generation()
        payload = build()
        market_home_response_cache.set(key, payload, generation=generation)
        return payload
    return market_home_response_cache.get_or_build(key, build)
