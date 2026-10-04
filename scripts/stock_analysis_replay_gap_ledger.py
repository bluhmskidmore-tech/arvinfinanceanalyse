#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import json
import sys
from collections import Counter, defaultdict
from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.cycle_macro_score import (  # noqa: E402
    M2_YOY_SERIES_ID,
    PMI_SERIES_ID,
    SOCIAL_FINANCING_YOY_SERIES_ID,
)
from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402
from backend.app.services.livermore_candidate_history_service import (  # noqa: E402
    _annotate_forward_maturity,
    _load_backtest_window_rows,
)
from backend.app.services.livermore_candidate_history_window_stats import (  # noqa: E402
    _EXECUTION_METRIC_BASIS,
    _classify_replay_date,
)

TABLE_HIST = "livermore_candidate_history"
TABLE_EXECUTION = "livermore_candidate_execution_history"
TABLE_MATCHED_BASELINE = "livermore_matched_baseline_history"
TABLE_OBS = "choice_stock_daily_observation"
CURRENT_RULE_SIGNAL_KIND = "stock_candidate"
UNKNOWN_VALUE = "unknown"
MARKDOWN_TITLE = "# Stock Analysis Replay Gap Ledger Summary"
MAX_AUDIT_WINDOW_MONTHS = 24
REQUIRED_COVERAGE_ITEMS: tuple[str, ...] = (
    "stock_universe:a_share_universe_sector_001004",
    "sector_membership:sw2021_industry_membership",
    "sector_strength:daily_return_turnover_amplitude",
    "stock_ohlcv:daily_ohlcv_amount",
    "stock_status:daily_trade_status",
    "limit_up_quality:daily_limit_flags",
    "limit_up_quality:point_in_time_limit_streaks",
)
STRICT_COMPLETED_STATUS = "completed"
FALLBACK_COVERED_STATUS = "completed_tushare_fallback"
FALLBACK_ELIGIBLE_STATUSES = {
    STRICT_COMPLETED_STATUS,
    "completed_tushare_gap_repair",
    FALLBACK_COVERED_STATUS,
}
STATUS_PRIORITY = {
    STRICT_COMPLETED_STATUS: 0,
    "completed_tushare_gap_repair": 1,
    FALLBACK_COVERED_STATUS: 2,
}


def load_choice_stock_materialization_coverage(**kwargs: Any) -> Any:
    from backend.app.tasks.choice_stock_materialize import (
        load_choice_stock_materialization_coverage as _load_coverage,
    )

    return _load_coverage(**kwargs)


def _default_current_rule_contract() -> dict[str, Any]:
    from backend.app.core_finance.livermore_stock_candidates import (
        EXP3B_STOCK_CANDIDATE_POLICY,
        FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
    )
    from backend.app.core_finance.matched_baseline import (
        FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
    )
    from backend.app.tasks.livermore_candidate_history_materialize import (
        EXECUTION_FORMULA_VERSION,
        FORMULA_VERSION as CANDIDATE_HISTORY_FORMULA_VERSION,
        RULE_VERSION as CANDIDATE_HISTORY_RULE_VERSION,
    )

    return {
        "signal_kind": CURRENT_RULE_SIGNAL_KIND,
        "metric_basis": _EXECUTION_METRIC_BASIS,
        "candidate_history_rule_version": CANDIDATE_HISTORY_RULE_VERSION,
        "candidate_history_formula_version": CANDIDATE_HISTORY_FORMULA_VERSION,
        "stock_candidate_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "selection_policy": EXP3B_STOCK_CANDIDATE_POLICY,
        "execution_formula_version": EXECUTION_FORMULA_VERSION,
        "matched_baseline_formula_version": MATCHED_BASELINE_FORMULA_VERSION,
        "stock_candidate_formula_resolution": "signal_evidence.selection_formula_version -> row.formula_version",
        "macro_series": {
            "pmi_series_id": PMI_SERIES_ID,
            "credit_proxy_series_id": SOCIAL_FINANCING_YOY_SERIES_ID,
            "degraded_display_proxy_series_id": M2_YOY_SERIES_ID,
        },
    }


def build_stock_analysis_replay_gap_ledger(
    *,
    duckdb_path: str | Path,
    evaluation_date: str,
    audit_window_months: int = 24,
    current_rule_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_path = _resolve_duckdb_path(duckdb_path)
    resolved_evaluation_date = _normalize_date(evaluation_date)
    if not 1 <= audit_window_months <= MAX_AUDIT_WINDOW_MONTHS:
        raise ValueError(
            f"audit_window_months must be between 1 and {MAX_AUDIT_WINDOW_MONTHS}."
        )
    requested_start = _subtract_months(resolved_evaluation_date, audit_window_months)
    contract = dict(current_rule_contract or _default_current_rule_contract())

    with _connect_read_only(resolved_path) as conn:
        tables = _table_names(conn)
        table_columns = {table: _table_columns(conn, table) for table in tables}
        trade_date_bundle = _load_trade_dates(
            conn,
            tables=tables,
            requested_start=requested_start,
            evaluation_date=resolved_evaluation_date,
        )
        trade_dates = trade_date_bundle["trade_dates"]
        candidate_rows = _load_candidate_rows(
            conn,
            tables=tables,
            requested_start=requested_start,
            evaluation_date=resolved_evaluation_date,
        )
        pit_candidate_rows = _load_pit_candidate_rows(
            conn,
            tables=tables,
            requested_start=requested_start,
            evaluation_date=resolved_evaluation_date,
        )
        execution_rows = _load_execution_rows(
            conn,
            tables=tables,
            requested_start=requested_start,
            evaluation_date=resolved_evaluation_date,
        )
        baseline_rows = _load_matched_baseline_rows(
            conn,
            tables=tables,
            requested_start=requested_start,
            evaluation_date=resolved_evaluation_date,
        )
        coverage_views = _build_coverage_views(
            conn,
            tables=tables,
            trade_dates=trade_dates,
            requested_start=requested_start,
            evaluation_date=resolved_evaluation_date,
            duckdb_path=resolved_path,
            calendar_verifiable=bool(trade_date_bundle["calendar_verifiable"]),
        )
        rows_by_date = _group_rows_by_key(pit_candidate_rows, "snapshot_as_of_date")
        date_detail = _build_date_detail(
            conn=conn,
            duckdb_path=resolved_path,
            trade_dates=trade_dates,
            rows_by_date=rows_by_date,
            evaluation_date=resolved_evaluation_date,
            coverage_views=coverage_views,
            history_table_present=TABLE_HIST in tables,
        )
    distributions = _build_distributions(candidate_rows, execution_rows, baseline_rows)
    stale_versions = _build_stale_version_counts(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=baseline_rows,
        contract=contract,
    )
    duplicate_audit = _build_duplicate_audit(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=baseline_rows,
        contract=contract,
        coverage_views=coverage_views,
    )
    current_rule_capacity = _build_current_rule_capacity(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=baseline_rows,
        date_detail=date_detail,
        evaluation_date=resolved_evaluation_date,
            contract=contract,
            coverage_views=coverage_views,
            duplicate_audit=duplicate_audit,
            calendar_verifiable=bool(trade_date_bundle["calendar_verifiable"]),
        )

    requested_range = {
        "start_date": requested_start,
        "end_date": resolved_evaluation_date,
        "audit_window_months": audit_window_months,
    }
    observed_range = {
        "start_date": trade_dates[0] if trade_dates else None,
        "end_date": trade_dates[-1] if trade_dates else None,
        "trade_date_count": len(trade_dates),
        "calendar_authority": trade_date_bundle["calendar_authority"],
        "calendar_residual_risk": trade_date_bundle["calendar_residual_risk"],
    }
    unsupported_rows = [
        detail for detail in date_detail["dates"] if detail["date_state"] == "unsupported"
    ]
    unsupported_signal_dates = [detail for detail in unsupported_rows if detail["row_count"] > 0]
    unsupported_no_signal_dates = [detail for detail in unsupported_rows if detail["row_count"] == 0]

    return {
        "page_id": "GAP-STOCK-ANALYSIS-PAGE",
        "page_route": "/stock-analysis",
        "mode": "observational_only",
        "formal_use_allowed": False,
        "duckdb_path": str(resolved_path),
        "evaluation_date": resolved_evaluation_date,
        "requested_range": requested_range,
        "observed_range": observed_range,
        "current_rule_contract": contract,
        "table_presence": {
            "tables": sorted(tables),
            "columns": {name: sorted(columns) for name, columns in sorted(table_columns.items())},
        },
        "duplicate_audit": duplicate_audit,
        "coverage_views": coverage_views,
        "date_state_summary": {
            "scope": "observational_as_produced_all_signal_kinds_and_versions",
            "formal_use_allowed": False,
            "counts": date_detail["counts"],
            "reason_code_counts": date_detail["reason_code_counts"],
            "dates": date_detail["dates"],
            "completed_no_strategy_signal_dates": [
                detail for detail in date_detail["dates"] if detail["date_state"] == "completed_no_strategy_signals"
            ],
            "pending_tail_dates": [
                detail for detail in date_detail["dates"] if detail["date_state"] == "pending_tail"
            ],
            "blocking_pending_dates": [
                detail for detail in date_detail["dates"] if detail["date_state"] == "blocking_pending"
            ],
            "proxy_only_dates": [
                detail for detail in date_detail["dates"] if detail["date_state"] == "proxy_only"
            ],
            "unsupported_signal_dates": unsupported_signal_dates,
            "unsupported_no_signal_dates": unsupported_no_signal_dates,
        },
        "distributions": distributions,
        "stale_versions": stale_versions,
        "pit_capacity": current_rule_capacity["pit_capacity"],
        "current_rule_certifiable_capacity": current_rule_capacity["current_rule_certifiable_capacity"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    capacity = report["current_rule_certifiable_capacity"]
    blocker_text = ", ".join(capacity["blockers"]) or "none"
    lines: list[str] = [
        MARKDOWN_TITLE,
        "",
        "> This is a summary view. Use JSON output for the complete per-date evidence ledger.",
        "",
    ]
    lines.extend(
        [
            f"- DuckDB: `{report['duckdb_path']}`",
            f"- Evaluation date: `{report['evaluation_date']}`",
            f"- Requested range: `{report['requested_range']['start_date']}` -> `{report['requested_range']['end_date']}`",
            f"- Observed range: `{report['observed_range']['start_date']}` -> `{report['observed_range']['end_date']}` ({report['observed_range']['trade_date_count']} dates)",
            "",
            "## Date States",
            "",
        ]
    )
    for key, value in report["date_state_summary"]["counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Reason Codes", ""])
    reason_counts = report["date_state_summary"]["reason_code_counts"]
    if reason_counts:
        for item in reason_counts:
            lines.append(f"- {item['value']}: {item['count']}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Coverage Views",
            "",
        ]
    )
    for view_name, view in report["coverage_views"].items():
        lines.extend(
            [
                f"- {view_name}: earliest_full_coverage_date={view['earliest_full_coverage_date']}, longest_continuous_eligible_streak={view['longest_continuous_eligible_streak']}, fallback_covered_date_count={view['fallback_covered_date_count']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Duplicate Audit",
            "",
            f"- Candidate as-produced duplicate keys: {report['duplicate_audit']['candidate_history']['as_produced']['duplicate_key_count']}",
            f"- Candidate current-window duplicate keys: {report['duplicate_audit']['candidate_history']['current_rule_strict_window']['duplicate_key_count']}",
            f"- Execution as-produced duplicate keys: {report['duplicate_audit']['execution_history']['as_produced']['duplicate_key_count']}",
            f"- Execution current-window duplicate keys: {report['duplicate_audit']['execution_history']['current_rule_strict_window']['duplicate_key_count']}",
            f"- Matched baseline as-produced duplicate keys: {report['duplicate_audit']['matched_baseline_history']['as_produced']['duplicate_key_count']}",
            f"- Matched baseline current-window duplicate keys: {report['duplicate_audit']['matched_baseline_history']['current_rule_strict_window']['duplicate_key_count']}",
            "",
            "## Current Rule Capacity",
            "",
            f"- Completed-date capacity: {capacity['completed_date_capacity']}/20",
            f"- Matched-entry capacity: {capacity['matched_entry_count']}/100",
            f"- Potential completed no-signal dates: {capacity['potential_completed_no_strategy_signal_date_count']}",
            f"- Potential current-rule signal dates: {capacity['potential_current_rule_signal_date_count']}",
            f"- Matched baseline PIT verifiability: {capacity['pit_verifiability']['matched_baseline']}",
            f"- Estimated materialization: {capacity['estimated_materialization']['status']}",
            f"- Blockers: {blocker_text}",
            "",
            "## PIT Capacity",
            "",
            f"- Stock-candidate dual-horizon rows: {report['pit_capacity']['stock_candidate_dual_horizon_row_count']}",
            f"- Stock-candidate current-formula dual-horizon rows: {report['pit_capacity']['stock_candidate_current_formula_dual_horizon_row_count']}",
            f"- Matched current-formula dual-horizon rows: {report['pit_capacity']['matched_baseline_current_formula_dual_horizon_row_count']}",
            "",
            "## Stale Versions",
            "",
        ]
    )
    for key, value in report["stale_versions"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _build_date_detail(
    *,
    conn: duckdb.DuckDBPyConnection,
    duckdb_path: Path,
    trade_dates: list[str],
    rows_by_date: dict[str, list[dict[str, Any]]],
    evaluation_date: str,
    coverage_views: dict[str, Any],
    history_table_present: bool,
) -> dict[str, Any]:
    tail_window = set(trade_dates[-20:])
    counts = {
        "completed_with_signals": 0,
        "completed_no_strategy_signals": 0,
        "pending_tail": 0,
        "blocking_pending": 0,
        "unsupported": 0,
        "proxy_only": 0,
    }
    reason_counter: Counter[str] = Counter()
    details: list[dict[str, Any]] = []
    for trade_date in trade_dates:
        rows = rows_by_date.get(trade_date, [])
        coverage = load_choice_stock_materialization_coverage(
            duckdb_path=str(duckdb_path),
            as_of_date=trade_date,
            conn=conn,
        )
        classification = _classify_replay_date(
            trade_date=trade_date,
            coverage=coverage,
            rows=rows,
            history_table_present=history_table_present,
        )
        public_reason = classification.get("public_reason")
        date_state = _date_state_from_classification(
            classification=classification,
            row_count=len(rows),
            trade_date=trade_date,
            tail_window=tail_window,
        )
        counts[date_state] += 1
        reason_code = None
        message = None
        if isinstance(public_reason, dict):
            reason_code = _optional_text(public_reason.get("reason_code"))
            message = _optional_text(public_reason.get("message"))
        if reason_code:
            reason_counter[reason_code] += 1
        strict_view = set(coverage_views["strict_completed_only"]["eligible_dates"])
        fallback_view = set(coverage_views["completed_plus_fallback"]["eligible_dates"])
        fallback_covered = set(coverage_views["completed_plus_fallback"]["fallback_covered_dates"])
        details.append(
            {
                "trade_date": trade_date,
                "date_state": date_state,
                "raw_status": str(classification.get("status") or ""),
                "reason_code": reason_code,
                "message": message,
                "row_count": len(rows),
                "stock_candidate_row_count": sum(
                    1 for row in rows if _optional_text(row.get("signal_kind")) == CURRENT_RULE_SIGNAL_KIND
                ),
                "signal_kind_counts": _distribution_list(
                    Counter(_optional_text(row.get("signal_kind")) or UNKNOWN_VALUE for row in rows)
                ),
                "coverage_views": {
                    "strict_completed_only": trade_date in strict_view,
                    "completed_plus_fallback": trade_date in fallback_view,
                    "fallback_covered": trade_date in fallback_covered,
                },
            }
        )

    return {
        "counts": counts,
        "reason_code_counts": _distribution_list(reason_counter),
        "dates": details,
    }


def _build_distributions(
    candidate_rows: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    stock_candidate_rows = [
        row for row in candidate_rows if _optional_text(row.get("signal_kind")) == CURRENT_RULE_SIGNAL_KIND
    ]
    return {
        "candidate_history": {
            "row_count": len(candidate_rows),
            "signal_kind_counts": _distribution_list(
                Counter(_optional_text(row.get("signal_kind")) or UNKNOWN_VALUE for row in candidate_rows)
            ),
            "formula_version_counts": _distribution_list(
                Counter(_optional_text(row.get("formula_version")) or UNKNOWN_VALUE for row in candidate_rows)
            ),
            "rule_version_counts": _distribution_list(
                Counter(_optional_text(row.get("rule_version")) or UNKNOWN_VALUE for row in candidate_rows)
            ),
            "run_id_counts": _distribution_list(
                Counter(_optional_text(row.get("run_id")) or UNKNOWN_VALUE for row in candidate_rows)
            ),
            "stock_candidate_selection_formula_counts": _distribution_list(
                Counter(_selection_formula_version(row) or UNKNOWN_VALUE for row in stock_candidate_rows)
            ),
        },
        "execution_history": {
            "row_count": len(execution_rows),
            "formula_version_counts": _distribution_list(
                Counter(_optional_text(row.get("formula_version")) or UNKNOWN_VALUE for row in execution_rows)
            ),
            "run_id_counts": _distribution_list(
                Counter(_optional_text(row.get("run_id")) or UNKNOWN_VALUE for row in execution_rows)
            ),
            "signal_kind_counts": _distribution_list(
                Counter(_optional_text(row.get("signal_kind")) or UNKNOWN_VALUE for row in execution_rows)
            ),
        },
        "matched_baseline_history": {
            "row_count": len(baseline_rows),
            "formula_version_counts": _distribution_list(
                Counter(_optional_text(row.get("formula_version")) or UNKNOWN_VALUE for row in baseline_rows)
            ),
            "run_id_counts": _distribution_list(
                Counter(_optional_text(row.get("run_id")) or UNKNOWN_VALUE for row in baseline_rows)
            ),
            "signal_kind_counts": _distribution_list(
                Counter(_optional_text(row.get("signal_kind")) or UNKNOWN_VALUE for row in baseline_rows)
            ),
        },
    }


def _build_stale_version_counts(
    *,
    candidate_rows: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, int]:
    stock_candidate_rows = [
        row for row in candidate_rows if _optional_text(row.get("signal_kind")) == CURRENT_RULE_SIGNAL_KIND
    ]
    return {
        "candidate_history_rule_stale_row_count": sum(
            1
            for row in candidate_rows
            if _optional_text(row.get("rule_version")) != contract["candidate_history_rule_version"]
        ),
        "candidate_history_formula_stale_row_count": sum(
            1
            for row in candidate_rows
            if _optional_text(row.get("formula_version")) != contract["candidate_history_formula_version"]
        ),
        "stock_candidate_selection_formula_stale_row_count": sum(
            1
            for row in stock_candidate_rows
            if _selection_formula_version(row) != contract["stock_candidate_formula_version"]
        ),
        "execution_formula_stale_row_count": sum(
            1
            for row in execution_rows
            if _optional_text(row.get("formula_version")) != contract["execution_formula_version"]
        ),
        "matched_baseline_formula_stale_row_count": sum(
            1
            for row in baseline_rows
            if _optional_text(row.get("formula_version")) != contract["matched_baseline_formula_version"]
        ),
    }


def _build_current_rule_capacity(
    *,
    candidate_rows: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    date_detail: dict[str, Any],
    evaluation_date: str,
    contract: dict[str, Any],
    coverage_views: dict[str, Any],
    duplicate_audit: dict[str, Any],
    calendar_verifiable: bool,
) -> dict[str, Any]:
    # date_detail is intentionally observational only; current-rule potential is
    # derived exclusively from the frozen candidate tuple and PIT-safe execution.
    _ = date_detail
    evaluation = date.fromisoformat(evaluation_date)
    strict_eligible_dates = set(coverage_views["strict_completed_only"]["eligible_dates"])
    strict_mixed_lineage_dates = set(coverage_views["strict_completed_only"].get("mixed_lineage_dates", []))
    lineage_verifiable = bool(coverage_views["strict_completed_only"].get("coverage_lineage_verifiable"))
    duplicate_blockers = [
        name
        for name, payload in duplicate_audit.items()
        if bool(payload.get("current_rule_strict_window", {}).get("has_duplicates"))
    ]
    current_candidate_rows = [
        row
        for row in candidate_rows
        if _is_exact_current_candidate_row(row, contract=contract)
    ]
    current_execution_rows = [
        row
        for row in execution_rows
        if _optional_text(row.get("signal_kind")) == CURRENT_RULE_SIGNAL_KIND
        and _optional_text(row.get("formula_version")) == contract["execution_formula_version"]
        and _is_execution_dual_horizon_pit_safe(row, evaluation)
    ]
    all_execution_dual_rows = [
        row
        for row in execution_rows
        if _optional_text(row.get("signal_kind")) == CURRENT_RULE_SIGNAL_KIND
        and _is_execution_dual_horizon_pit_safe(row, evaluation)
    ]
    current_baseline_rows = [
        row
        for row in baseline_rows
        if _optional_text(row.get("signal_kind")) == CURRENT_RULE_SIGNAL_KIND
        and _optional_text(row.get("formula_version")) == contract["matched_baseline_formula_version"]
        and _is_matched_baseline_dual_horizon_ready(row)
    ]

    current_candidate_keys = {_candidate_key(row) for row in current_candidate_rows}
    current_execution_map = {_execution_key(row): row for row in current_execution_rows}
    potential_duplicate_blockers = {
        name
        for name in duplicate_blockers
        if name in {"candidate_history", "execution_history"}
    }
    potential_allowed = (
        calendar_verifiable
        and lineage_verifiable
        and not potential_duplicate_blockers
    )
    potential_entry_keys = {
        key
        for key in current_candidate_keys
        if key in current_execution_map
        and key[0] in strict_eligible_dates
        and key[0] not in strict_mixed_lineage_dates
        and potential_allowed
    }
    potential_signal_dates = sorted({key[0] for key in potential_entry_keys})
    potential_no_signal_dates: set[str] = set()
    blockers: list[str] = ["current_rule_certified_cohort_not_materialized"]
    if not calendar_verifiable:
        blockers.append("calendar_authority_unavailable")
    if not lineage_verifiable:
        blockers.append("coverage_lineage_unverifiable")
    if strict_mixed_lineage_dates:
        blockers.append("mixed_run_or_lineage_dates_present")
    if not current_candidate_rows:
        blockers.append("current_rule_candidate_tuple_unavailable")
    blockers.append("matched_baseline_pit_proof_unavailable")
    blockers.append("zero_signal_receipt_not_persisted")
    blockers.extend(f"duplicate_keys:{name}" for name in duplicate_blockers)
    if len(potential_no_signal_dates) + len(potential_signal_dates) < 20:
        blockers.append("insufficient_potential_completed_dates")
    if len(potential_entry_keys) < 100:
        blockers.append("insufficient_potential_matched_entries")

    return {
        "pit_capacity": {
            "stock_candidate_dual_horizon_row_count": len(all_execution_dual_rows),
            "stock_candidate_dual_horizon_date_count": len(
                {str(row.get("signal_date") or "")[:10] for row in all_execution_dual_rows}
            ),
            "stock_candidate_current_formula_dual_horizon_row_count": len(current_execution_rows),
            "stock_candidate_current_formula_dual_horizon_date_count": len(
                {str(row.get("signal_date") or "")[:10] for row in current_execution_rows}
            ),
            "matched_baseline_current_formula_dual_horizon_row_count": len(current_baseline_rows),
            "matched_baseline_current_formula_dual_horizon_date_count": len(
                {str(row.get("signal_date") or "")[:10] for row in current_baseline_rows}
            ),
            "matched_baseline_pit_verifiability": "unavailable_missing_exit_dates",
        },
        "current_rule_certifiable_capacity": {
            "potential_completed_no_strategy_signal_date_count": len(potential_no_signal_dates),
            "certifiable_completed_no_strategy_signal_date_count": 0,
            "current_rule_candidate_row_count": len(current_candidate_rows),
            "current_rule_candidate_date_count": len(
                {str(row.get("snapshot_as_of_date") or "")[:10] for row in current_candidate_rows}
            ),
            "current_rule_execution_row_count": len(current_execution_rows),
            "current_rule_execution_date_count": len(
                {str(row.get("signal_date") or "")[:10] for row in current_execution_rows}
            ),
            "current_rule_matched_baseline_row_count": len(current_baseline_rows),
            "current_rule_matched_baseline_date_count": len(
                {str(row.get("signal_date") or "")[:10] for row in current_baseline_rows}
            ),
            "pit_verifiability": {
                "execution_history": "verified_with_entry_and_exit_dates",
                "matched_baseline": "unavailable_missing_exit_dates",
                "no_signal_dates": "unavailable_missing_run_receipt_and_date_certificate",
            },
            "potential_date_state_basis": "exact_current_candidate_tuple_plus_pit_safe_execution_and_strict_coverage",
            "potential_matched_entry_basis": "exact_current_candidate_with_pit_safe_dual_horizon_execution",
            "potential_matched_entry_count": len(potential_entry_keys),
            "potential_current_rule_signal_date_count": len(potential_signal_dates),
            "potential_current_rule_signal_dates": potential_signal_dates,
            "matched_entry_count": 0,
            "current_rule_certifiable_signal_date_count": 0,
            "current_rule_certifiable_signal_dates": [],
            "completed_date_capacity": 0,
            "potential_completed_date_capacity_including_no_signal": len(potential_no_signal_dates) + len(potential_signal_dates),
            "estimated_materialization": {
                "status": "unavailable",
                "replay_fact_row_count": None,
                "date_certificate_row_count": None,
                "reason": "current_rule_replay_plan_and_authoritative_calendar_required",
            },
            "strict_coverage_only": True,
            "blockers": blockers,
            "threshold_progress": {
                "completed_dates_target": 20,
                "completed_dates_actual": 0,
                "completed_dates_potential": len(potential_no_signal_dates) + len(potential_signal_dates),
                "matched_entries_target": 100,
                "matched_entries_actual": 0,
                "matched_entries_potential": len(potential_entry_keys),
            },
        },
    }


def _load_trade_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    requested_start: str,
    evaluation_date: str,
) -> dict[str, Any]:
    if TABLE_OBS in tables:
        rows = conn.execute(
            f"""
            select distinct trade_date
            from {TABLE_OBS}
            where cast(trade_date as date) >= cast(? as date)
              and cast(trade_date as date) <= cast(? as date)
            order by trade_date
            """,
            [requested_start, evaluation_date],
        ).fetchall()
        dates = [str(row[0])[:10] for row in rows if _optional_text(row[0])]
        if dates:
            return {
                "trade_dates": dates,
                "calendar_authority": TABLE_OBS,
                "calendar_verifiable": False,
                "calendar_residual_risk": "choice_stock_daily_observation proves landed observed dates only; fully missing trade dates remain uncertified, so continuity/potential stay fail-closed",
            }
    if TABLE_HIST in tables:
        rows = conn.execute(
            f"""
            select distinct snapshot_as_of_date
            from {TABLE_HIST}
            where cast(snapshot_as_of_date as date) >= cast(? as date)
              and cast(snapshot_as_of_date as date) <= cast(? as date)
            order by snapshot_as_of_date
            """,
            [requested_start, evaluation_date],
        ).fetchall()
        return {
            "trade_dates": [str(row[0])[:10] for row in rows if _optional_text(row[0])],
            "calendar_authority": "candidate_history_fallback",
            "calendar_verifiable": False,
            "calendar_residual_risk": "candidate-history fallback is not an official trading calendar and cannot prove absent trade dates were fully checked; continuity/potential are fail-closed",
        }
    return {
        "trade_dates": [],
        "calendar_authority": "unavailable",
        "calendar_verifiable": False,
        "calendar_residual_risk": "no observed trade-date authority is available",
    }


def _load_candidate_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    requested_start: str,
    evaluation_date: str,
) -> list[dict[str, Any]]:
    if TABLE_HIST not in tables:
        return []
    columns = _table_columns(conn, TABLE_HIST)
    selection_policy_expr = (
        "selection_policy"
        if "selection_policy" in columns
        else "cast(null as varchar) as selection_policy"
    )
    rows = conn.execute(
        f"""
        select
          snapshot_as_of_date,
          stock_code,
          signal_kind,
          theme_source_kind,
          data_status,
          formula_version,
          rule_version,
          run_id,
          signal_evidence_json,
          {selection_policy_expr}
        from {TABLE_HIST}
        where cast(snapshot_as_of_date as date) >= cast(? as date)
          and cast(snapshot_as_of_date as date) <= cast(? as date)
        """,
        [requested_start, evaluation_date],
    ).fetchall()
    return [
        {
            "snapshot_as_of_date": _optional_text(row[0]),
            "stock_code": _optional_text(row[1]),
            "signal_kind": _optional_text(row[2]),
            "theme_source_kind": _optional_text(row[3]),
            "data_status": _optional_text(row[4]),
            "formula_version": _optional_text(row[5]),
            "rule_version": _optional_text(row[6]),
            "run_id": _optional_text(row[7]),
            "signal_evidence_json": _parse_json_object(row[8]),
            "selection_policy": _optional_text(row[9]),
        }
        for row in rows
    ]


def _load_pit_candidate_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    requested_start: str,
    evaluation_date: str,
) -> list[dict[str, Any]]:
    if TABLE_HIST not in tables:
        return []
    rows = _load_backtest_window_rows(
        conn,
        stock_code=None,
        snapshot_from=requested_start,
        snapshot_to=evaluation_date,
        evaluation_as_of_date=evaluation_date,
    )
    _annotate_forward_maturity(
        conn,
        items=rows,
        tables=tables,
        evaluation_as_of_date=evaluation_date,
        rewrite_legacy_status=True,
    )
    return rows


def _load_execution_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    requested_start: str,
    evaluation_date: str,
) -> list[dict[str, Any]]:
    if TABLE_EXECUTION not in tables:
        return []
    rows = conn.execute(
        f"""
        select
          signal_date,
          stock_code,
          signal_kind,
          entry_executable,
          entry_date,
          exit_date_5d,
          exit_date_20d,
          return_5d_net_adj,
          return_20d_net_adj,
          formula_version,
          run_id
        from {TABLE_EXECUTION}
        where cast(signal_date as date) >= cast(? as date)
          and cast(signal_date as date) <= cast(? as date)
        """,
        [requested_start, evaluation_date],
    ).fetchall()
    return [
        {
            "signal_date": _optional_text(row[0]),
            "stock_code": _optional_text(row[1]),
            "signal_kind": _optional_text(row[2]),
            "entry_executable": bool(row[3]),
            "entry_date": _optional_text(row[4]),
            "exit_date_5d": _optional_text(row[5]),
            "exit_date_20d": _optional_text(row[6]),
            "return_5d_net_adj": _optional_float(row[7]),
            "return_20d_net_adj": _optional_float(row[8]),
            "formula_version": _optional_text(row[9]),
            "run_id": _optional_text(row[10]),
        }
        for row in rows
    ]


def _load_matched_baseline_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    requested_start: str,
    evaluation_date: str,
) -> list[dict[str, Any]]:
    if TABLE_MATCHED_BASELINE not in tables:
        return []
    rows = conn.execute(
        f"""
        select
          signal_date,
          candidate_stock_code,
          signal_kind,
          control_stock_code,
          control_group,
          seed,
          control_entry_executable,
          control_return_5d_net_adj,
          control_return_20d_net_adj,
          formula_version,
          run_id
        from {TABLE_MATCHED_BASELINE}
        where cast(signal_date as date) >= cast(? as date)
          and cast(signal_date as date) <= cast(? as date)
        """,
        [requested_start, evaluation_date],
    ).fetchall()
    return [
        {
            "signal_date": _optional_text(row[0]),
            "candidate_stock_code": _optional_text(row[1]),
            "signal_kind": _optional_text(row[2]),
            "control_stock_code": _optional_text(row[3]),
            "control_group": _optional_text(row[4]),
            "seed": _optional_text(row[5]),
            "control_entry_executable": bool(row[6]),
            "control_return_5d_net_adj": _optional_float(row[7]),
            "control_return_20d_net_adj": _optional_float(row[8]),
            "formula_version": _optional_text(row[9]),
            "run_id": _optional_text(row[10]),
        }
        for row in rows
    ]


def _group_rows_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key_value = _optional_text(row.get(key))
        if key_value:
            grouped[key_value].append(row)
    return dict(grouped)


def _date_state_from_classification(
    *,
    classification: dict[str, Any],
    row_count: int,
    trade_date: str,
    tail_window: set[str],
) -> str:
    status = str(classification.get("status") or "")
    if status == "completed":
        return "completed_with_signals" if row_count > 0 else "completed_no_strategy_signals"
    if status == "proxy_only":
        return "proxy_only"
    if status == "unsupported":
        return "unsupported"
    if status == "pending":
        reason = classification.get("public_reason") if isinstance(classification.get("public_reason"), dict) else {}
        if (
            str(reason.get("reason_code") or "") == "forward_returns_pending"
            and trade_date in tail_window
        ):
            return "pending_tail"
        return "blocking_pending"
    return "unsupported"


def _resolved_stock_candidate_formula_version(row: dict[str, Any]) -> str | None:
    selection_formula = _selection_formula_version(row)
    return selection_formula or _optional_text(row.get("formula_version"))


def _selection_formula_version(row: dict[str, Any]) -> str | None:
    evidence = row.get("signal_evidence_json")
    if not isinstance(evidence, dict):
        return None
    return _optional_text(evidence.get("selection_formula_version"))


def _selection_policy(row: dict[str, Any]) -> str | None:
    evidence = row.get("signal_evidence_json")
    if not isinstance(evidence, dict):
        return None
    return _optional_text(evidence.get("selection_policy"))


def _is_exact_current_candidate_row(
    row: dict[str, Any],
    *,
    contract: dict[str, Any],
    eligible_dates: set[str] | None = None,
) -> bool:
    evidence_policy = _selection_policy(row)
    outer_policy = _optional_text(row.get("selection_policy"))
    expected_policy = _optional_text(contract.get("selection_policy"))
    if expected_policy is None or evidence_policy != expected_policy:
        return False
    if outer_policy is not None and outer_policy != evidence_policy:
        return False
    if eligible_dates is not None:
        snapshot_date = _optional_text(row.get("snapshot_as_of_date"))
        if snapshot_date not in eligible_dates:
            return False
    return (
        _optional_text(row.get("signal_kind")) == contract["signal_kind"]
        and _optional_text(row.get("rule_version"))
        == contract["candidate_history_rule_version"]
        and _optional_text(row.get("formula_version"))
        == contract["candidate_history_formula_version"]
        and _selection_formula_version(row)
        == contract["stock_candidate_formula_version"]
    )


def _candidate_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("snapshot_as_of_date") or ""),
        str(row.get("stock_code") or ""),
        str(row.get("signal_kind") or ""),
    )


def _execution_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("signal_date") or ""),
        str(row.get("stock_code") or ""),
        str(row.get("signal_kind") or ""),
    )


def _baseline_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("signal_date") or ""),
        str(row.get("candidate_stock_code") or ""),
        str(row.get("signal_kind") or ""),
    )


def _baseline_audit_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("signal_date") or ""),
        str(row.get("candidate_stock_code") or ""),
        str(row.get("signal_kind") or ""),
        str(row.get("control_stock_code") or ""),
        str(row.get("control_group") or ""),
        str(row.get("seed") or ""),
    )


def _is_execution_dual_horizon_pit_safe(row: dict[str, Any], evaluation: date) -> bool:
    if not bool(row.get("entry_executable")):
        return False
    if row.get("return_5d_net_adj") is None or row.get("return_20d_net_adj") is None:
        return False
    entry_date = _parse_optional_date(row.get("entry_date"))
    exit_date_5d = _parse_optional_date(row.get("exit_date_5d"))
    exit_date_20d = _parse_optional_date(row.get("exit_date_20d"))
    if not entry_date or not exit_date_5d or not exit_date_20d:
        return False
    return entry_date <= evaluation and exit_date_5d <= evaluation and exit_date_20d <= evaluation


def _is_matched_baseline_dual_horizon_ready(row: dict[str, Any]) -> bool:
    return bool(row.get("control_entry_executable")) and row.get("control_return_5d_net_adj") is not None and row.get("control_return_20d_net_adj") is not None


def _distribution_list(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _connect_read_only(path: Path) -> AbstractContextManager[duckdb.DuckDBPyConnection]:
    return read_only_connection(str(path))


def _resolve_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    return path




def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _table_columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}


def _build_coverage_views(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    trade_dates: list[str],
    requested_start: str,
    evaluation_date: str,
    duckdb_path: Path,
    calendar_verifiable: bool,
) -> dict[str, Any]:
    if "choice_stock_request_audit" not in tables or not trade_dates:
        return _build_coverage_views_from_loader(
            conn=conn,
            duckdb_path=duckdb_path,
            trade_dates=trade_dates,
        )
    audit_columns = _table_columns(conn, "choice_stock_request_audit")
    has_run_id = "run_id" in audit_columns
    has_source_version = "source_version" in audit_columns
    has_rule_version = "rule_version" in audit_columns
    audit_rows = conn.execute(
        f"""
        select
          as_of_date,
          input_family,
          field_key,
          status,
          row_count,
          {'run_id' if has_run_id else 'null'} as run_id,
          {'source_version' if has_source_version else 'null'} as source_version,
          {'rule_version' if has_rule_version else 'null'} as rule_version
        from choice_stock_request_audit
        where cast(as_of_date as date) >= cast(? as date)
          and cast(as_of_date as date) <= cast(? as date)
        """,
        [requested_start, evaluation_date],
    ).fetchall()
    status_by_date_item: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in audit_rows:
        as_of_date = _optional_text(row[0])
        input_family = _optional_text(row[1])
        field_key = _optional_text(row[2])
        status = _optional_text(row[3]) or ""
        row_count = int(row[4] or 0)
        run_id = _optional_text(row[5]) or UNKNOWN_VALUE
        source_version = _optional_text(row[6]) or UNKNOWN_VALUE
        rule_version = _optional_text(row[7]) or UNKNOWN_VALUE
        if not as_of_date or not input_family or not field_key or row_count <= 0:
            continue
        item_key = f"{input_family}:{field_key}"
        if item_key not in REQUIRED_COVERAGE_ITEMS:
            continue
        current = status_by_date_item[as_of_date].get(item_key)
        candidate = {
            "status": status,
            "row_count": row_count,
            "run_id": run_id,
            "source_version": source_version,
            "rule_version": rule_version,
        }
        if current is None or _status_rank(status) < _status_rank(str(current["status"])) or (
            _status_rank(status) == _status_rank(str(current["status"])) and row_count > int(current["row_count"])
        ) or (
            _status_rank(status) == _status_rank(str(current["status"]))
            and row_count == int(current["row_count"])
            and (run_id, source_version, rule_version, status) < (
                str(current.get("run_id") or ""),
                str(current.get("source_version") or ""),
                str(current.get("rule_version") or ""),
                str(current.get("status") or ""),
            )
        ):
            status_by_date_item[as_of_date][item_key] = candidate

    strict_eligible_dates: list[str] = []
    fallback_eligible_dates: list[str] = []
    fallback_covered_dates: list[str] = []
    strict_date_lineage: list[dict[str, Any]] = []
    fallback_date_lineage: list[dict[str, Any]] = []
    for trade_date in trade_dates:
        item_statuses = status_by_date_item.get(trade_date, {})
        strict_ready = all(
            item_statuses.get(item, {}).get("status") == STRICT_COMPLETED_STATUS for item in REQUIRED_COVERAGE_ITEMS
        )
        fallback_ready = all(
            item_statuses.get(item, {}).get("status") in FALLBACK_ELIGIBLE_STATUSES for item in REQUIRED_COVERAGE_ITEMS
        )
        if strict_ready:
            strict_eligible_dates.append(trade_date)
        if fallback_ready:
            fallback_eligible_dates.append(trade_date)
            if any(
                item_statuses.get(item, {}).get("status") == FALLBACK_COVERED_STATUS
                for item in REQUIRED_COVERAGE_ITEMS
            ):
                fallback_covered_dates.append(trade_date)
        strict_date_lineage.append(
            _coverage_lineage_for_date(
                trade_date=trade_date,
                item_statuses=item_statuses,
                eligible=strict_ready,
                fallback_covered=False,
            )
        )
        fallback_date_lineage.append(
            _coverage_lineage_for_date(
                trade_date=trade_date,
                item_statuses=item_statuses,
                eligible=fallback_ready,
                fallback_covered=trade_date in fallback_covered_dates,
            )
        )

    return {
        "strict_completed_only": _coverage_view_payload(
            trade_dates=trade_dates,
            eligible_dates=strict_eligible_dates,
            fallback_covered_dates=[],
            semantics="eligible statuses = {'completed'}",
            date_lineage=strict_date_lineage,
            coverage_lineage_verifiable=has_run_id and has_source_version and has_rule_version,
            continuity_certifiable=calendar_verifiable,
        ),
        "completed_plus_fallback": _coverage_view_payload(
            trade_dates=trade_dates,
            eligible_dates=fallback_eligible_dates,
            fallback_covered_dates=fallback_covered_dates,
            semantics="eligible statuses = {'completed','completed_tushare_gap_repair','completed_tushare_fallback'}; fallback-covered dates are not certified by default",
            date_lineage=fallback_date_lineage,
            coverage_lineage_verifiable=has_run_id and has_source_version and has_rule_version,
            continuity_certifiable=calendar_verifiable,
        ),
    }


def _coverage_view_payload(
    *,
    trade_dates: list[str],
    eligible_dates: list[str],
    fallback_covered_dates: list[str],
    semantics: str,
    date_lineage: list[dict[str, Any]],
    coverage_lineage_verifiable: bool,
    continuity_certifiable: bool,
) -> dict[str, Any]:
    eligible_set = set(eligible_dates)
    streak = 0
    longest = 0
    for trade_date in trade_dates:
        if trade_date in eligible_set:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    mixed_lineage_dates = [item["trade_date"] for item in date_lineage if item["mixed_lineage"]]
    incomplete_lineage_dates = [item["trade_date"] for item in date_lineage if item["incomplete_lineage"]]
    return {
        "eligible_status_semantics": semantics,
        "coverage_lineage_verifiable": coverage_lineage_verifiable and not incomplete_lineage_dates,
        "continuity_certifiable": continuity_certifiable,
        "eligible_dates": eligible_dates,
        "fallback_covered_dates": fallback_covered_dates,
        "eligible_date_count": len(eligible_dates),
        "fallback_covered_date_count": len(fallback_covered_dates),
        "mixed_lineage_dates": mixed_lineage_dates,
        "mixed_lineage_date_count": len(mixed_lineage_dates),
        "incomplete_lineage_dates": incomplete_lineage_dates,
        "incomplete_lineage_date_count": len(incomplete_lineage_dates),
        "earliest_full_coverage_date": eligible_dates[0] if eligible_dates else None,
        "longest_continuous_eligible_streak": longest,
        "continuity_basis": "observed_trade_date_sequence",
        "date_lineage": date_lineage,
    }


def _build_coverage_views_from_loader(
    *,
    conn: duckdb.DuckDBPyConnection,
    duckdb_path: Path,
    trade_dates: list[str],
) -> dict[str, Any]:
    strict_eligible_dates: list[str] = []
    for trade_date in trade_dates:
        coverage = load_choice_stock_materialization_coverage(
            duckdb_path=str(duckdb_path),
            as_of_date=trade_date,
            conn=conn,
        )
        if bool(getattr(coverage, "full_coverage", False)):
            strict_eligible_dates.append(trade_date)

    strict = _coverage_view_payload(
        trade_dates=trade_dates,
        eligible_dates=strict_eligible_dates,
        fallback_covered_dates=[],
        semantics="derived from load_choice_stock_materialization_coverage(full_coverage=true); request audit table absent",
        date_lineage=[],
        coverage_lineage_verifiable=False,
        continuity_certifiable=False,
    )
    return {
        "strict_completed_only": strict,
        "completed_plus_fallback": strict,
    }


def _status_rank(status: str) -> int:
    return STATUS_PRIORITY.get(status, 999)


def _build_duplicate_audit(
    *,
    candidate_rows: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    contract: dict[str, Any],
    coverage_views: dict[str, Any],
) -> dict[str, Any]:
    strict_eligible_dates = set(coverage_views["strict_completed_only"]["eligible_dates"])
    candidate_counter = Counter(_candidate_key(row) for row in candidate_rows)
    execution_counter = Counter(_execution_key(row) for row in execution_rows)
    baseline_counter = Counter(_baseline_audit_key(row) for row in baseline_rows)
    current_candidate_rows = [
        row
        for row in candidate_rows
        if _is_exact_current_candidate_row(
            row,
            contract=contract,
            eligible_dates=strict_eligible_dates,
        )
    ]
    current_candidate_keys = {_candidate_key(row) for row in current_candidate_rows}
    current_execution_rows = [
        row
        for row in execution_rows
        if _optional_text(row.get("signal_kind")) == CURRENT_RULE_SIGNAL_KIND
        and _optional_text(row.get("formula_version")) == contract["execution_formula_version"]
        and _optional_text(row.get("signal_date")) in strict_eligible_dates
        and _execution_key(row) in current_candidate_keys
    ]
    current_baseline_rows = [
        row
        for row in baseline_rows
        if _optional_text(row.get("signal_kind")) == CURRENT_RULE_SIGNAL_KIND
        and _optional_text(row.get("formula_version")) == contract["matched_baseline_formula_version"]
        and _optional_text(row.get("signal_date")) in strict_eligible_dates
    ]
    return {
        "candidate_history": {
            "as_produced": _duplicate_payload(candidate_counter),
            "current_rule_strict_window": _duplicate_payload(
                Counter(_candidate_key(row) for row in current_candidate_rows)
            ),
        },
        "execution_history": {
            "as_produced": _duplicate_payload(execution_counter),
            "current_rule_strict_window": _duplicate_payload(
                Counter(_execution_key(row) for row in current_execution_rows)
            ),
        },
        "matched_baseline_history": {
            "as_produced": _duplicate_payload(baseline_counter),
            "current_rule_strict_window": _duplicate_payload(
                Counter(_baseline_audit_key(row) for row in current_baseline_rows)
            ),
        },
    }


def _duplicate_payload(counter: Counter[tuple[str, ...]]) -> dict[str, Any]:
    duplicates = [(key, count) for key, count in counter.items() if count > 1]
    duplicates.sort(key=lambda item: (-item[1], item[0]))
    return {
        "duplicate_key_count": len(duplicates),
        "has_duplicates": bool(duplicates),
        "sample_duplicate_keys": [
            {"key": list(key), "count": count}
            for key, count in duplicates[:10]
        ],
    }


def _coverage_lineage_for_date(
    *,
    trade_date: str,
    item_statuses: dict[str, dict[str, Any]],
    eligible: bool,
    fallback_covered: bool,
) -> dict[str, Any]:
    required_item_entries = [item_statuses.get(item, {}) for item in REQUIRED_COVERAGE_ITEMS]
    run_counter = Counter(
        str(entry.get("run_id") or UNKNOWN_VALUE) for entry in required_item_entries
    )
    source_counter = Counter(
        str(entry.get("source_version") or UNKNOWN_VALUE) for entry in required_item_entries
    )
    rule_counter = Counter(
        str(entry.get("rule_version") or UNKNOWN_VALUE) for entry in required_item_entries
    )
    incomplete_lineage = eligible and any(
        not str(entry.get(field) or "").strip()
        or str(entry.get(field) or "").strip() == UNKNOWN_VALUE
        for entry in required_item_entries
        for field in ("run_id", "source_version", "rule_version")
    )
    mixed_run = len(run_counter) > 1
    mixed_source = len(source_counter) > 1
    mixed_rule = len(rule_counter) > 1
    return {
        "trade_date": trade_date,
        "eligible": eligible,
        "fallback_covered": fallback_covered,
        "run_id_counts": _distribution_list(run_counter),
        "source_version_counts": _distribution_list(source_counter),
        "rule_version_counts": _distribution_list(rule_counter),
        "mixed_run": mixed_run,
        "mixed_source_version": mixed_source,
        "mixed_rule_version": mixed_rule,
        "mixed_lineage": mixed_run or mixed_source or mixed_rule,
        "incomplete_lineage": incomplete_lineage,
    }


def _normalize_date(value: str | Any) -> str:
    text = _optional_text(value)
    if not text:
        raise ValueError("evaluation_date is required.")
    return date.fromisoformat(text).isoformat()


def _parse_optional_date(value: Any) -> date | None:
    text = _optional_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()[:10 if isinstance(value, date) else 200]
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _subtract_months(value: str, months: int) -> str:
    base = date.fromisoformat(value)
    month_index = base.year * 12 + (base.month - 1) - months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only historical replay gap ledger for /stock-analysis.")
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--evaluation-date", required=True)
    parser.add_argument("--audit-window-months", type=int, default=24)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)

    report = build_stock_analysis_replay_gap_ledger(
        duckdb_path=args.duckdb_path,
        evaluation_date=args.evaluation_date,
        audit_window_months=args.audit_window_months,
    )
    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
