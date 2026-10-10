#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.livermore_stock_candidates import (  # noqa: E402
    EXP3B_STOCK_CANDIDATE_POLICY,
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
    stock_candidate_policy_active_market_states,
)
from backend.app.core_finance.matched_baseline import (  # noqa: E402
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.choice_stock_adapter import (  # noqa: E402
    ChoiceStockReadiness,
    choice_stock_readiness_missing,
    load_choice_stock_readiness,
)
from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402
from backend.app.services.market_data_livermore_service import (  # noqa: E402
    PAYLOAD_CACHE_NAME,
    load_livermore_strategy_payload,
)
from backend.app.services.runtime_cache import clear_runtime_cache  # noqa: E402
from backend.app.tasks.livermore_candidate_history_materialize import (  # noqa: E402
    EXECUTION_FORMULA_VERSION,
    FORMULA_VERSION as CANDIDATE_HISTORY_FORMULA_VERSION,
    RULE_VERSION as CANDIDATE_HISTORY_RULE_VERSION,
)

TABLE_OBS = "choice_stock_daily_observation"
MARKDOWN_TITLE = "# Stock Analysis Current-Rule Replay Dry Run"
DATE_KEYS = {
    "as_of_date",
    "business_date",
    "current_reference_date",
    "effective_as_of_date",
    "gate_as_of_date",
    "observation_date",
    "prior_reference_date",
    "publication_date",
    "published_at",
    "reference_date",
    "report_date",
    "requested_as_of_date",
    "resolved_as_of_date",
    "snapshot_as_of_date",
    "source_date",
    "trade_date",
}
SNAPSHOT_TABLES = (
    ("universe", "choice_stock_universe", "as_of_date"),
    ("membership", "choice_stock_sector_membership", "as_of_date"),
    ("limit", "choice_stock_limit_quality", "as_of_date"),
    ("factor", "choice_stock_factor_snapshot", "as_of_date"),
)
# Historical name retained to minimize contract churn. These entries are
# stage-local limits on formal replay certification, not current-run evidence blockers.
BASE_BLOCKERS = (
    "calendar_authority_unavailable",
    "carry_forward_policy_unapproved",
    "selection_only_diagnostic_no_replay_maturity",
    "current_rule_certified_cohort_not_materialized",
    "zero_signal_receipt_not_persisted",
    "matched_baseline_pit_proof_unavailable",
)
REPLAY_READY_COMPLETED_DATES = 20
REPLAY_READY_MATCHED_ENTRIES = 100
PLAN_DIGEST_VERSION = "stock_analysis_current_rule_replay_plan_v2"
OPERATIONAL_FAILURE_EXIT_CODE = 2
@dataclass(frozen=True)
class ReplayConfig:
    duckdb_path: Path
    start_date: str
    end_date: str
    stock_candidate_policy: str
    max_workers: int
    choice_stock_catalog_file: str
    choice_stock_catalog_sha256: str | None
    readiness: ChoiceStockReadiness
    progress_every: int


def build_current_rule_replay_dry_run(
    *,
    duckdb_path: str | Path,
    start_date: str,
    end_date: str,
    stock_candidate_policy: str = EXP3B_STOCK_CANDIDATE_POLICY,
    max_workers: int = 4,
    choice_stock_catalog_file: str | Path | None = None,
    progress_every: int = 0,
) -> dict[str, Any]:
    current_rule_policy = _require_current_rule_policy(stock_candidate_policy)
    settings = get_settings()
    resolved_path = _resolve_duckdb_path(duckdb_path or settings.duckdb_path)
    resolved_start = _normalize_date(start_date)
    resolved_end = _normalize_date(end_date)
    if resolved_start > resolved_end:
        raise ValueError("start_date must be on or before end_date.")
    worker_count = max(1, int(max_workers))
    catalog_path = str(choice_stock_catalog_file or settings.choice_stock_catalog_file or "").strip()
    readiness = (
        load_choice_stock_readiness(catalog_path)
        if catalog_path
        else choice_stock_readiness_missing("")
    )
    config = ReplayConfig(
        duckdb_path=resolved_path,
        start_date=resolved_start,
        end_date=resolved_end,
        stock_candidate_policy=current_rule_policy,
        max_workers=worker_count,
        choice_stock_catalog_file=catalog_path,
        choice_stock_catalog_sha256=_catalog_content_sha256(catalog_path),
        readiness=readiness,
        progress_every=max(0, int(progress_every)),
    )
    db_hash_before = _file_sha256(resolved_path)
    requested_dates = _load_observation_dates(
        duckdb_path=resolved_path,
        start_date=resolved_start,
        end_date=resolved_end,
    )
    old_as_produced = _load_old_as_produced_rows(
        duckdb_path=resolved_path,
        start_date=resolved_start,
        end_date=resolved_end,
        stock_candidate_policy=current_rule_policy,
    )
    if not readiness.ready:
        report = _build_not_ready_report(
            config=config,
            requested_dates=requested_dates,
            old_as_produced=old_as_produced,
            db_hash_before=db_hash_before,
        )
        report["db_sha256_after"] = _file_sha256(resolved_path)
        report["summary"]["db_hash_unchanged"] = (
            report["db_sha256_after"] == report["db_sha256_before"]
        )
        if not report["summary"]["db_hash_unchanged"]:
            report["blockers"] = list(
                _ordered_blockers(
                    [*report["blockers"], "duckdb_hash_changed_during_read_only_replay"]
                )
            )
        return report

    date_results = _run_replay_dates(config=config, requested_dates=requested_dates)
    report = _build_report(
        config=config,
        requested_dates=requested_dates,
        date_results=date_results,
        old_as_produced=old_as_produced,
        db_hash_before=db_hash_before,
    )
    report["db_sha256_after"] = _file_sha256(resolved_path)
    report["summary"]["db_hash_unchanged"] = (
        report["db_sha256_after"] == report["db_sha256_before"]
    )
    if not report["summary"]["db_hash_unchanged"]:
        report["blockers"] = list(
            _ordered_blockers(
                [*report["blockers"], "duckdb_hash_changed_during_read_only_replay"]
            )
        )
    return report


def render_markdown(report: dict[str, Any], *, detail: str = "summary") -> str:
    summary = report["summary"]
    counts = summary["status_counts"]
    blockers = ", ".join(report["blockers"]) or "none"
    diagnostic_limitations = ", ".join(report.get("diagnostic_limitations", [])) or "none"
    lines = [
        MARKDOWN_TITLE,
        "",
        f"- DuckDB: `{report['duckdb_path']}`",
        f"- Requested range: `{report['requested_range']['start_date']}` -> `{report['requested_range']['end_date']}`",
        f"- Requested dates: `{report['requested_range']['requested_date_count']}`",
        f"- Certification status: `{report['certification_status']}`",
        f"- Calendar verifiable: `{str(report['calendar_verifiable']).lower()}`",
        f"- Policy: `{report['frozen_tuple']['selection_policy']}`",
        f"- Choice catalog ready: `{str(report['choice_stock_catalog']['ready']).lower()}`",
        "",
        "## Summary",
        "",
        f"- attempted_dates: {summary['attempted_dates']}",
        f"- selection_completed_with_signals: {counts.get('selection_completed_with_signals', 0)}",
        f"- selection_completed_no_signals: {counts.get('selection_completed_no_signals', 0)}",
        f"- selection_policy_inactive: {counts.get('selection_policy_inactive', 0)}",
        f"- selection_unsupported: {counts.get('selection_unsupported', 0)}",
        f"- loader_error: {counts.get('loader_error', 0)}",
        f"- total_candidate_rows: {summary['candidate_rows_total']}",
        f"- candidate_signal_dates: {summary['candidate_signal_date_count']}",
        f"- duplicate_candidate_rows: {summary['duplicate_candidate_rows']}",
        f"- source_date_mismatches: {summary['requested_resolved_mismatch_count']}",
        f"- future_business_date_violations: {summary['future_business_date_violation_count']}",
        f"- future_availability_violations: {summary['future_availability_violation_count']}",
        "",
        "## Snapshot Freshness",
        "",
    ]
    for name, stats in summary["snapshot_age_summary"].items():
        lines.append(
            f"- {name}: gt30={stats['age_gt_30_count']}, gt90={stats['age_gt_90_count']}, missing={stats['missing_count']}"
        )
    lines.extend(
        [
            "",
            "## Legacy Compare",
            "",
            f"- old_as_produced_reference: {report['legacy_as_produced_compare']['reference_row_count']}",
            f"- old_as_produced_observed: {report['legacy_as_produced_compare']['observed_row_count']}",
            f"- overlap_rows: {report['legacy_as_produced_compare']['overlap_row_count']}",
            f"- overlap_dates: {report['legacy_as_produced_compare']['overlap_date_count']}",
            "",
            "## Blockers",
            "",
            f"- {blockers}",
            "",
            "## Diagnostic Limitations",
            "",
            f"- {diagnostic_limitations}",
            "",
            "## Integrity",
            "",
            f"- db_sha256_before: `{report['db_sha256_before']}`",
            f"- db_sha256_after: `{report['db_sha256_after']}`",
            f"- plan_digest_version: `{report['plan_digest_version']}`",
            f"- plan_digest: `{report['plan_digest']}`",
        ]
    )
    if detail == "dates":
        lines.extend(["", "## Date Results", ""])
        for result in report["date_results"]:
            lines.append(
                f"- {result['trade_date']}: status={result['status']}, market_state={result['market_state']}, "
                f"candidate_count={result['candidate_count']}, resolved={result['resolved_as_of_date']}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay current-rule stock-analysis dates in DuckDB read-only mode.")
    parser.add_argument("--duckdb-path", default=get_settings().duckdb_path)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--choice-stock-catalog-file", default=get_settings().choice_stock_catalog_file)
    parser.add_argument(
        "--stock-candidate-policy",
        choices=(EXP3B_STOCK_CANDIDATE_POLICY,),
        default=EXP3B_STOCK_CANDIDATE_POLICY,
    )
    parser.add_argument("--max-workers", type=int, default=max(1, min(8, (os.cpu_count() or 4))))
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--detail", choices=("summary", "dates"), default="summary")
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args(argv)

    report = build_current_rule_replay_dry_run(
        duckdb_path=args.duckdb_path,
        start_date=args.start_date,
        end_date=args.end_date,
        stock_candidate_policy=args.stock_candidate_policy,
        max_workers=args.max_workers,
        choice_stock_catalog_file=args.choice_stock_catalog_file,
        progress_every=args.progress_every,
    )
    if args.format == "markdown":
        print(render_markdown(report, detail=args.detail))
    else:
        print(json.dumps(_serialize_report(report, detail=args.detail), ensure_ascii=False, indent=2, sort_keys=True))
    return OPERATIONAL_FAILURE_EXIT_CODE if _has_operational_failure(report) else 0


def _run_replay_dates(*, config: ReplayConfig, requested_dates: list[str]) -> list[dict[str, Any]]:
    if not requested_dates:
        return []
    if config.max_workers <= 1:
        return [
            _replay_one_date_fail_closed(config=config, trade_date=trade_date)
            for trade_date in requested_dates
        ]

    results_by_date: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        future_map = {
            executor.submit(
                _replay_one_date_fail_closed,
                config=config,
                trade_date=trade_date,
            ): trade_date
            for trade_date in requested_dates
        }
        completed = 0
        for future in concurrent.futures.as_completed(future_map):
            trade_date = future_map[future]
            try:
                results_by_date[trade_date] = future.result()
            except Exception as exc:  # pragma: no cover - fail-closed guard
                results_by_date[trade_date] = _error_result(
                    trade_date=trade_date,
                    message=f"unhandled replay processing error: {type(exc).__name__}: {exc}",
                    stock_candidate_policy=config.stock_candidate_policy,
                    status_reason="processing_exception",
                )
            completed += 1
            if config.progress_every > 0 and completed % config.progress_every == 0:
                print(
                    f"[stock-analysis-replay] completed {completed}/{len(requested_dates)} dates",
                    file=sys.stderr,
                )
    return [results_by_date[trade_date] for trade_date in requested_dates]


def _replay_one_date_fail_closed(*, config: ReplayConfig, trade_date: str) -> dict[str, Any]:
    try:
        return _replay_one_date(config=config, trade_date=trade_date)
    except Exception as exc:
        return _error_result(
            trade_date=trade_date,
            message=f"unhandled replay processing error: {type(exc).__name__}: {exc}",
            stock_candidate_policy=config.stock_candidate_policy,
            status_reason="processing_exception",
        )


def _replay_one_date(*, config: ReplayConfig, trade_date: str) -> dict[str, Any]:
    requested = date.fromisoformat(trade_date)
    try:
        payload, meta = load_livermore_strategy_payload(
            duckdb_path=str(config.duckdb_path),
            as_of_date=requested,
            stock_readiness=config.readiness,
            backfill_mode=True,
            stock_candidate_policy=config.stock_candidate_policy,
            theme_overlay_reader=None,
        )
    except Exception as exc:
        return _error_result(
            trade_date=trade_date,
            message=f"{type(exc).__name__}: {exc}",
            stock_candidate_policy=config.stock_candidate_policy,
        )
    finally:
        clear_runtime_cache(PAYLOAD_CACHE_NAME)

    return _build_date_result(
        trade_date=trade_date,
        payload=payload if isinstance(payload, dict) else {},
        meta=meta if isinstance(meta, dict) else {},
        stock_candidate_policy=config.stock_candidate_policy,
        readiness=config.readiness,
        snapshot_sources=_load_snapshot_sources(
            duckdb_path=config.duckdb_path,
            as_of_date=trade_date,
        ),
    )


def _build_date_result(
    *,
    trade_date: str,
    payload: dict[str, Any],
    meta: dict[str, Any],
    stock_candidate_policy: str,
    readiness: ChoiceStockReadiness,
    snapshot_sources: dict[str, Any],
) -> dict[str, Any]:
    market_gate = _mapping(payload.get("market_gate"))
    market_state = _text(market_gate.get("state")) or "unknown"
    stock_candidates_raw = payload.get("stock_candidates")
    stock_candidates_present = isinstance(stock_candidates_raw, dict)
    stock_candidates = _mapping(stock_candidates_raw)
    block_reason = _stock_candidate_block_reason(payload)
    candidate_items = [
        item for item in _list_of_dicts(stock_candidates.get("items")) if _text(item.get("stock_code"))
    ]
    candidate_codes = [
        code for item in candidate_items if (code := _text(item.get("stock_code")))
    ]
    candidate_item_count = len(candidate_codes)
    duplicate_candidate_codes = sorted(
        code for code, count in Counter(candidate_codes).items() if count > 1
    )
    reported_candidate_count = _safe_int(stock_candidates.get("candidate_count"))
    candidate_count_matches_items = (
        reported_candidate_count is not None
        and reported_candidate_count == candidate_item_count
    )
    insufficient_count = _safe_int(stock_candidates.get("insufficient_history_count")) or 0
    requested_as_of_date = _text(payload.get("requested_as_of_date")) or trade_date
    resolved_as_of_date = _text(payload.get("as_of_date")) or requested_as_of_date
    requested_matches_resolved = requested_as_of_date == resolved_as_of_date == trade_date
    policy_active = market_state in stock_candidate_policy_active_market_states(stock_candidate_policy)
    selection_policy = _text(stock_candidates.get("selection_policy"))
    formula_version = _text(stock_candidates.get("formula_version"))
    rule_tuple_matches = (
        stock_candidates_present
        and selection_policy == stock_candidate_policy
        and formula_version == STOCK_CANDIDATE_FORMULA_VERSION
    )
    policy_inactive = (
        not policy_active
        and _is_policy_inactive_reason(
            block_reason,
            stock_candidate_policy=stock_candidate_policy,
        )
    )

    if not requested_matches_resolved:
        status = "selection_unsupported"
        status_reason = "requested_resolved_date_mismatch"
    elif not readiness.ready:
        status = "selection_unsupported"
        status_reason = "choice_stock_catalog_not_ready"
    elif not stock_candidates_present:
        if policy_inactive:
            status = "selection_policy_inactive"
            status_reason = "selection_policy_inactive"
        else:
            status = "selection_unsupported"
            status_reason = "stock_candidates_payload_missing"
    elif not rule_tuple_matches:
        status = "selection_unsupported"
        status_reason = "current_rule_tuple_mismatch"
    elif reported_candidate_count is None:
        status = "selection_unsupported"
        status_reason = "candidate_count_missing"
    elif not candidate_count_matches_items:
        status = "selection_unsupported"
        status_reason = "candidate_count_items_mismatch"
    elif duplicate_candidate_codes:
        status = "selection_unsupported"
        status_reason = "duplicate_candidate_codes"
    elif block_reason:
        status = "selection_unsupported"
        status_reason = "stock_candidate_block_reason_with_payload"
    elif reported_candidate_count > 0:
        status = "selection_completed_with_signals"
        status_reason = "current_rule_candidates_present"
    elif policy_active:
        status = "selection_completed_no_signals"
        status_reason = "policy_active_zero_signal"
    else:
        status = "selection_unsupported"
        status_reason = "policy_inactive_payload_present_without_receipt"

    accepted_candidate_codes = (
        list(candidate_codes) if status == "selection_completed_with_signals" else []
    )

    macro_layer = _mapping(_mapping(payload.get("cycle_rotation_framework")).get("macro_layer"))
    macro_components = _build_macro_components(payload=payload, macro_layer=macro_layer)
    future_business_date_violations = _collect_future_business_date_violations(
        trade_date=trade_date,
        payload=payload,
        meta=meta,
    )
    # A data-gap evidence string records an input that the PIT loader already
    # rejected; it is disclosure, not consumed lineage.  Keep the public field
    # while structured dates continue through the recursive check above.
    future_availability_violations: list[dict[str, str]] = []
    module_states = _normalize_module_states(payload.get("module_states"))
    return {
        "trade_date": trade_date,
        "status": status,
        "status_reason": status_reason,
        "requested_as_of_date": requested_as_of_date,
        "resolved_as_of_date": resolved_as_of_date,
        "requested_matches_resolved": requested_matches_resolved,
        "market_state": market_state,
        "market_exposure": _safe_float(market_gate.get("exposure")),
        "selection_policy": selection_policy,
        "expected_selection_policy": stock_candidate_policy,
        "stock_candidate_formula_version": formula_version,
        "expected_stock_candidate_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "rule_tuple_matches": rule_tuple_matches,
        "candidate_count": reported_candidate_count or 0,
        "candidate_item_count": candidate_item_count,
        "candidate_codes": candidate_codes,
        "unique_candidate_codes": sorted(set(candidate_codes)),
        "duplicate_candidate_codes": duplicate_candidate_codes,
        "candidate_duplicate_count": candidate_item_count - len(set(candidate_codes)),
        "candidate_count_matches_items": candidate_count_matches_items,
        "accepted_candidate_count": len(accepted_candidate_codes),
        "accepted_candidate_codes": accepted_candidate_codes,
        "input_stock_count": _safe_int(stock_candidates.get("input_stock_count")),
        "excluded_stock_count": _safe_int(stock_candidates.get("excluded_stock_count")),
        "insufficient_history_count": insufficient_count,
        "stock_candidate_block_reason": block_reason,
        "macro_status": {
            "ready": bool(macro_layer.get("ready")),
            "macro_score": _safe_float(macro_layer.get("macro_score")),
            "available_inputs": _string_list(macro_layer.get("available_inputs")),
            "missing_inputs": _string_list(macro_layer.get("missing_inputs")),
            "evidence": _text(macro_layer.get("evidence")),
        },
        "macro_components": macro_components,
        "future_business_date_violations": future_business_date_violations,
        "future_availability_violations": future_availability_violations,
        "module_states": module_states,
        "meta_summary": {
            "quality_flag": _text(meta.get("quality_flag")),
            "vendor_status": _text(meta.get("vendor_status")),
            "fallback_mode": _text(meta.get("fallback_mode")),
            "source_version": _text(meta.get("source_version")),
            "vendor_version": _text(meta.get("vendor_version")),
            "tables_used": _string_list(meta.get("tables_used")),
            "evidence_rows": _safe_int(meta.get("evidence_rows")),
        },
        "snapshot_sources": snapshot_sources,
    }


def _build_not_ready_report(
    *,
    config: ReplayConfig,
    requested_dates: list[str],
    old_as_produced: list[dict[str, str]],
    db_hash_before: str,
) -> dict[str, Any]:
    summary = {
        "attempted_dates": 0,
        "candidate_rows_total": 0,
        "candidate_output_rows_total": 0,
        "candidate_signal_date_count": 0,
        "duplicate_candidate_rows": 0,
        "requested_resolved_mismatch_count": 0,
        "future_business_date_violation_count": 0,
        "future_availability_violation_count": 0,
        "future_input_date_violation_count": 0,
        "future_input_date_violation_date_count": 0,
        "status_counts": {"selection_unsupported": len(requested_dates)},
        "market_state_counts": {},
        "formula_version_counts": {},
        "selection_policy_counts": {},
        "macro_component_status_counts": {},
        "module_status_counts": {},
        "snapshot_age_summary": {
            name: {"age_gt_30_count": 0, "age_gt_90_count": 0, "missing_count": len(requested_dates)}
            for name, _, _ in SNAPSHOT_TABLES
        },
    }
    report = _base_report(
        config=config,
        requested_dates=requested_dates,
        summary=summary,
        date_results=[],
        old_as_produced=old_as_produced,
        db_hash_before=db_hash_before,
    )
    report["blockers"] = list(_ordered_blockers(["choice_stock_catalog_not_ready"]))
    report["summary"]["status_counts"] = {"selection_unsupported": len(requested_dates)}
    return report


def _build_report(
    *,
    config: ReplayConfig,
    requested_dates: list[str],
    date_results: list[dict[str, Any]],
    old_as_produced: list[dict[str, str]],
    db_hash_before: str,
) -> dict[str, Any]:
    raw_candidate_keys = [
        (result["trade_date"], code)
        for result in date_results
        for code in result["candidate_codes"]
    ]
    accepted_candidate_keys = [
        (result["trade_date"], code)
        for result in date_results
        for code in result["accepted_candidate_codes"]
    ]
    status_counts = Counter(result["status"] for result in date_results)
    market_counts = Counter(result["market_state"] for result in date_results if result["market_state"])
    formula_counts = Counter(
        result["stock_candidate_formula_version"] or "missing"
        for result in date_results
    )
    policy_counts = Counter(result["selection_policy"] or "missing" for result in date_results)
    macro_counts = Counter()
    module_status_counts = Counter()
    snapshot_age_summary = {
        name: {"age_gt_30_count": 0, "age_gt_90_count": 0, "missing_count": 0}
        for name, _, _ in SNAPSHOT_TABLES
    }
    mismatch_count = 0
    future_business_violation_count = 0
    future_availability_violation_count = 0
    future_input_violation_date_count = 0
    for result in date_results:
        if (
            result["status"] != "loader_error"
            and result["requested_matches_resolved"] is False
        ):
            mismatch_count += 1
        date_has_future_violation = False
        if result["future_business_date_violations"]:
            date_has_future_violation = True
            future_business_violation_count += len(result["future_business_date_violations"])
        if result["future_availability_violations"]:
            date_has_future_violation = True
            future_availability_violation_count += len(result["future_availability_violations"])
        if date_has_future_violation:
            future_input_violation_date_count += 1
        for component in result["macro_components"].values():
            macro_counts[str(component.get("status") or "unknown")] += 1
        for state in result["module_states"]:
            module_status_counts[str(state.get("state") or "unknown")] += 1
        for name, source in result["snapshot_sources"].items():
            if source["source_date"] is None:
                snapshot_age_summary[name]["missing_count"] += 1
                continue
            age = _safe_int(source.get("natural_age_days"))
            if age is not None and age > 30:
                snapshot_age_summary[name]["age_gt_30_count"] += 1
            if age is not None and age > 90:
                snapshot_age_summary[name]["age_gt_90_count"] += 1
    duplicate_counter = Counter(raw_candidate_keys)
    duplicate_rows = sum(count - 1 for count in duplicate_counter.values() if count > 1)
    replay_key_set = set(accepted_candidate_keys)
    old_key_set = {(row["trade_date"], row["stock_code"]) for row in old_as_produced}
    overlap_keys = sorted(replay_key_set & old_key_set)
    blockers: list[str] = []
    if mismatch_count:
        blockers.append("requested_resolved_date_mismatch_detected")
    if future_business_violation_count:
        blockers.append("future_business_date_violation_detected")
    if future_availability_violation_count:
        blockers.append("future_availability_date_violation_detected")
    if any(result["duplicate_candidate_codes"] for result in date_results):
        blockers.append("duplicate_candidate_key_detected")
    if any(
        not result["candidate_count_matches_items"]
        and result["status"] != "loader_error"
        and result["stock_candidate_formula_version"] is not None
        for result in date_results
    ):
        blockers.append("candidate_count_items_mismatch_detected")
    if any(
        not result["rule_tuple_matches"]
        and result["status"] != "loader_error"
        and result["stock_candidate_formula_version"] is not None
        for result in date_results
    ):
        blockers.append("current_rule_tuple_mismatch_detected")
    if status_counts.get("loader_error", 0):
        blockers.append("loader_errors_present")
    if status_counts.get("selection_unsupported", 0):
        blockers.append("unsupported_dates_present")
    summary = {
        "attempted_dates": len(date_results),
        "candidate_rows_total": sum(result["accepted_candidate_count"] for result in date_results),
        "candidate_output_rows_total": sum(result["candidate_item_count"] for result in date_results),
        "candidate_signal_date_count": sum(
            1 for result in date_results if result["accepted_candidate_count"] > 0
        ),
        "duplicate_candidate_rows": duplicate_rows,
        "requested_resolved_mismatch_count": mismatch_count,
        "future_business_date_violation_count": future_business_violation_count,
        "future_availability_violation_count": future_availability_violation_count,
        "future_input_date_violation_count": (
            future_business_violation_count + future_availability_violation_count
        ),
        "future_input_date_violation_date_count": future_input_violation_date_count,
        "status_counts": dict(sorted(status_counts.items())),
        "market_state_counts": dict(sorted(market_counts.items())),
        "formula_version_counts": dict(sorted(formula_counts.items())),
        "selection_policy_counts": dict(sorted(policy_counts.items())),
        "macro_component_status_counts": dict(sorted(macro_counts.items())),
        "module_status_counts": dict(sorted(module_status_counts.items())),
        "snapshot_age_summary": snapshot_age_summary,
    }
    report = _base_report(
        config=config,
        requested_dates=requested_dates,
        summary=summary,
        date_results=date_results,
        old_as_produced=old_as_produced,
        db_hash_before=db_hash_before,
    )
    report["legacy_as_produced_compare"]["overlap_row_count"] = len(overlap_keys)
    report["legacy_as_produced_compare"]["overlap_date_count"] = len({trade_date for trade_date, _ in overlap_keys})
    report["legacy_as_produced_compare"]["overlap_sample"] = [
        {"trade_date": trade_date, "stock_code": stock_code}
        for trade_date, stock_code in overlap_keys[:10]
    ]
    report["blockers"] = list(_ordered_blockers(blockers))
    return report


def _base_report(
    *,
    config: ReplayConfig,
    requested_dates: list[str],
    summary: dict[str, Any],
    date_results: list[dict[str, Any]],
    old_as_produced: list[dict[str, str]],
    db_hash_before: str,
) -> dict[str, Any]:
    plan_digest = _plan_digest(
        requested_dates=requested_dates,
        policy=config.stock_candidate_policy,
        readiness=config.readiness,
        catalog_content_sha256=config.choice_stock_catalog_sha256,
    )
    return {
        "page_route": "/stock-analysis",
        "mode": "diagnostic_only",
        "formal_use_allowed": False,
        "certification_status": "diagnostic_only",
        "calendar_verifiable": False,
        "coverage_policy": {
            "calendar_authority": "choice_stock_daily_observation_only",
            "calendar_receipt_sha256": None,
            "observed_date_axis_sha256": _sha256_text(
                json.dumps(requested_dates, ensure_ascii=False, separators=(",", ":"))
            ),
            "audit_bypass_approved": False,
            "carry_forward_approved": False,
            "snapshot_age_basis": "latest_available_table_date_not_certified_loader_lineage",
        },
        "duckdb_path": str(config.duckdb_path),
        "requested_range": {
            "start_date": config.start_date,
            "end_date": config.end_date,
            "requested_date_count": len(requested_dates),
        },
        "choice_stock_catalog": {
            "path": config.readiness.catalog_path,
            "ready": config.readiness.ready,
            "status": config.readiness.status,
            "message": config.readiness.message,
            "fingerprint": config.choice_stock_catalog_sha256,
        },
        "frozen_tuple": {
            "candidate_history_rule_version": CANDIDATE_HISTORY_RULE_VERSION,
            "candidate_history_formula_version": CANDIDATE_HISTORY_FORMULA_VERSION,
            "stock_candidate_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
            "selection_policy": config.stock_candidate_policy,
            "execution_formula_version": EXECUTION_FORMULA_VERSION,
            "matched_baseline_formula_version": MATCHED_BASELINE_FORMULA_VERSION,
            "metric_basis": "net_next_open_adj",
        },
        "summary": summary,
        "replay_closure_evaluation": {
            "status": "not_evaluated",
            "reason": "selection_only_diagnostic",
            "completed_dates": None,
            "pending_tail_dates": None,
            "blocking_pending_dates": None,
            "unsupported_dates": None,
            "proxy_only_dates": None,
            "matched_entry_count": None,
            "ready_thresholds": {
                "completed_dates": REPLAY_READY_COMPLETED_DATES,
                "matched_entry_count": REPLAY_READY_MATCHED_ENTRIES,
            },
        },
        "diagnostic_planned_counts": {
            "current_rule_candidate_fact_rows": summary.get("candidate_rows_total", 0),
            "active_policy_zero_signal_receipt_rows": summary.get("status_counts", {}).get(
                "selection_completed_no_signals", 0
            ),
            "policy_inactive_receipt_rows": summary.get("status_counts", {}).get(
                "selection_policy_inactive", 0
            ),
            "matched_baseline_pit_proof_rows": None,
            "persisted_rows": 0,
        },
        "date_results": date_results,
        "legacy_as_produced_compare": {
            "reference_row_count": len(old_as_produced),
            "observed_row_count": len(old_as_produced),
            "observed_date_count": len({row["trade_date"] for row in old_as_produced}),
            "overlap_row_count": 0,
            "overlap_date_count": 0,
            "overlap_sample": [],
        },
        "blockers": [],
        "diagnostic_limitations": list(BASE_BLOCKERS),
        "plan_digest_version": PLAN_DIGEST_VERSION,
        "plan_digest": plan_digest,
        "db_sha256_before": db_hash_before,
        "db_sha256_after": db_hash_before,
    }


def _load_observation_dates(*, duckdb_path: Path, start_date: str, end_date: str) -> list[str]:
    with read_only_connection(str(duckdb_path)) as conn:
        rows = conn.execute(
            f"""
            select distinct cast(trade_date as date) as trade_date
            from {TABLE_OBS}
            where cast(trade_date as date) >= cast(? as date)
              and cast(trade_date as date) <= cast(? as date)
            order by trade_date
            """,
            [start_date, end_date],
        ).fetchall()
    return [text for row in rows if (text := _text(row[0]))]


def _load_snapshot_sources(*, duckdb_path: Path, as_of_date: str) -> dict[str, Any]:
    with read_only_connection(str(duckdb_path)) as conn:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        payload: dict[str, Any] = {}
        for name, table_name, date_column in SNAPSHOT_TABLES:
            if table_name not in tables:
                payload[name] = {"table": table_name, "source_date": None, "natural_age_days": None}
                continue
            row = conn.execute(
                f"""
                select max(cast({date_column} as date))
                from {table_name}
                where cast({date_column} as date) <= cast(? as date)
                """,
                [as_of_date],
            ).fetchone()
            source_date = _text(row[0]) if row else None
            payload[name] = {
                "table": table_name,
                "source_date": source_date,
                "natural_age_days": _natural_day_age(source_date, as_of_date),
            }
        return payload


def _load_old_as_produced_rows(
    *,
    duckdb_path: Path,
    start_date: str,
    end_date: str,
    stock_candidate_policy: str,
) -> list[dict[str, str]]:
    with read_only_connection(str(duckdb_path)) as conn:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if "livermore_candidate_history" not in tables:
            return []
        columns = {str(row[1]) for row in conn.execute("pragma table_info('livermore_candidate_history')").fetchall()}
        required = {"snapshot_as_of_date", "stock_code", "signal_kind", "signal_evidence_json"}
        if not required.issubset(columns):
            return []
        has_selection_policy = "selection_policy" in columns
        rows = conn.execute(
            f"""
            select snapshot_as_of_date, stock_code, signal_evidence_json,
                   {'selection_policy' if has_selection_policy else 'null'} as selection_policy
            from livermore_candidate_history
            where cast(snapshot_as_of_date as date) >= cast(? as date)
              and cast(snapshot_as_of_date as date) <= cast(? as date)
              and signal_kind = 'stock_candidate'
            """,
            [start_date, end_date],
        ).fetchall()
    matched: list[dict[str, str]] = []
    for snapshot_as_of_date, stock_code, evidence_raw, selection_policy_raw in rows:
        evidence = _parse_json_object(evidence_raw)
        selection_policy = (
            _text(selection_policy_raw)
            if has_selection_policy
            else _text(evidence.get("selection_policy"))
        )
        if selection_policy != stock_candidate_policy:
            continue
        if _text(evidence.get("selection_formula_version")) != STOCK_CANDIDATE_FORMULA_VERSION:
            continue
        trade_date = _text(snapshot_as_of_date)
        code = _text(stock_code)
        if trade_date and code:
            matched.append({"trade_date": trade_date, "stock_code": code})
    matched.sort(key=lambda item: (item["trade_date"], item["stock_code"]))
    return matched


def _stock_candidate_block_reason(payload: dict[str, Any]) -> str | None:
    for item in _list_of_dicts(payload.get("unsupported_outputs")):
        if _text(item.get("key")) == "stock_candidates":
            return _text(item.get("reason"))
    return None


def _build_macro_components(*, payload: dict[str, Any], macro_layer: dict[str, Any]) -> dict[str, Any]:
    gaps_by_family = {
        _text(item.get("input_family")): item
        for item in _list_of_dicts(payload.get("data_gaps"))
        if _text(item.get("input_family"))
    }
    lineage = _mapping(macro_layer.get("lineage"))
    components: dict[str, Any] = {}
    for key in ("PMI", "credit_impulse", "price_spread"):
        lower_key = key.lower()
        gap = _mapping(gaps_by_family.get(key) or gaps_by_family.get(lower_key))
        lineage_entry = _mapping(lineage.get(lower_key) or lineage.get(key))
        source_date = (
            _text(lineage_entry.get("business_date"))
            or _text(lineage_entry.get("trade_date"))
            or _text(lineage_entry.get("current_reference_date"))
            or _text(lineage_entry.get("source_date"))
        )
        status = _text(gap.get("status"))
        if status is None:
            available_inputs = {item.lower() for item in _string_list(macro_layer.get("available_inputs"))}
            status = "ready" if lower_key in available_inputs else "missing"
        components[key] = {
            "status": status,
            "evidence": _text(gap.get("evidence")) or _text(lineage_entry.get("evidence")),
            "source_date": source_date,
            "lineage": lineage_entry,
        }
    return components


def _normalize_module_states(raw: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _list_of_dicts(raw):
        result.append(
            {
                "key": _text(item.get("key")),
                "state": _text(item.get("state")) or _text(item.get("status")),
                "source_date": _text(item.get("source_date")) or _text(item.get("as_of_date")),
                "lag_days": _safe_int(item.get("lag_days")),
                "reasons": _string_list(item.get("reasons")) or (
                    [_text(item.get("reason"))] if _text(item.get("reason")) else []
                ),
            }
        )
    return result


def _is_policy_inactive_reason(
    reason: str | None,
    *,
    stock_candidate_policy: str,
) -> bool:
    normalized = str(reason or "").strip().lower()
    policy = str(stock_candidate_policy or "").strip().lower()
    return bool(
        normalized
        and policy
        and "stock candidate policy" in normalized
        and policy in normalized
        and " is inactive in " in normalized
        and "active market states are " in normalized
    )


def _collect_future_business_date_violations(
    *,
    trade_date: str,
    payload: dict[str, Any],
    meta: dict[str, Any],
) -> list[dict[str, str]]:
    cutoff = date.fromisoformat(trade_date)
    violations: list[dict[str, str]] = []
    for path, key, value in _iter_date_values(payload, prefix="payload"):
        if key not in DATE_KEYS:
            continue
        parsed = _parse_optional_date(value)
        if parsed is not None and parsed > cutoff:
            violations.append({"path": path, "key": key, "value": parsed.isoformat()})
    for path, key, value in _iter_date_values(meta, prefix="meta"):
        if key not in DATE_KEYS:
            continue
        parsed = _parse_optional_date(value)
        if parsed is not None and parsed > cutoff:
            violations.append({"path": path, "key": key, "value": parsed.isoformat()})
    violations.sort(key=lambda item: (item["path"], item["key"], item["value"]))
    return violations


def _iter_date_values(value: Any, *, prefix: str) -> list[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            if isinstance(child, (dict, list)):
                found.extend(_iter_date_values(child, prefix=child_prefix))
            else:
                found.append((child_prefix, str(key), child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_iter_date_values(child, prefix=f"{prefix}[{index}]"))
    return found


def _error_result(
    *,
    trade_date: str,
    message: str,
    stock_candidate_policy: str,
    status_reason: str = "loader_exception",
) -> dict[str, Any]:
    return {
        "trade_date": trade_date,
        "status": "loader_error",
        "status_reason": status_reason,
        "requested_as_of_date": trade_date,
        "resolved_as_of_date": None,
        "requested_matches_resolved": None,
        "market_state": "error",
        "market_exposure": None,
        "selection_policy": stock_candidate_policy,
        "expected_selection_policy": stock_candidate_policy,
        "stock_candidate_formula_version": None,
        "expected_stock_candidate_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "rule_tuple_matches": False,
        "candidate_count": 0,
        "candidate_item_count": 0,
        "candidate_codes": [],
        "unique_candidate_codes": [],
        "duplicate_candidate_codes": [],
        "candidate_duplicate_count": 0,
        "candidate_count_matches_items": False,
        "accepted_candidate_count": 0,
        "accepted_candidate_codes": [],
        "input_stock_count": None,
        "excluded_stock_count": None,
        "insufficient_history_count": 0,
        "stock_candidate_block_reason": message,
        "macro_status": {
            "ready": False,
            "macro_score": None,
            "available_inputs": [],
            "missing_inputs": [],
            "evidence": message,
        },
        "macro_components": {},
        "future_business_date_violations": [],
        "future_availability_violations": [],
        "module_states": [],
        "meta_summary": {
            "quality_flag": "error",
            "vendor_status": "error",
            "fallback_mode": "none",
            "source_version": None,
            "vendor_version": None,
            "tables_used": [],
            "evidence_rows": 0,
        },
        "snapshot_sources": {
            name: {"table": table_name, "source_date": None, "natural_age_days": None}
            for name, table_name, _ in SNAPSHOT_TABLES
        },
    }


def _serialize_report(report: dict[str, Any], *, detail: str) -> dict[str, Any]:
    if detail == "dates":
        return report
    trimmed = dict(report)
    trimmed["date_results"] = []
    return trimmed


def _has_operational_failure(report: dict[str, Any]) -> bool:
    catalog = _mapping(report.get("choice_stock_catalog"))
    summary = _mapping(report.get("summary"))
    status_counts = _mapping(summary.get("status_counts"))
    blockers = set(_string_list(report.get("blockers")))
    return bool(
        catalog.get("ready") is not True
        or (_safe_int(status_counts.get("loader_error")) or 0) > 0
        or summary.get("db_hash_unchanged") is False
        or "duckdb_hash_changed_during_read_only_replay" in blockers
    )


def _ordered_blockers(extra: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for blocker in extra:
        if blocker not in seen:
            ordered.append(blocker)
            seen.add(blocker)
    return ordered


def _resolve_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    return path


def _normalize_date(value: str | Any) -> str:
    text = _text(value)
    if not text:
        raise ValueError("date is required.")
    return date.fromisoformat(text).isoformat()


def _parse_optional_date(value: Any) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _natural_day_age(source_date: str | None, as_of_date: str) -> int | None:
    if source_date is None:
        return None
    source = _parse_optional_date(source_date)
    anchor = _parse_optional_date(as_of_date)
    if source is None or anchor is None:
        return None
    return (anchor - source).days


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _catalog_content_sha256(path_value: str | Path | None) -> str | None:
    normalized = str(path_value or "").strip()
    if not normalized:
        return None
    path = Path(normalized)
    if not path.is_file():
        return None
    try:
        return _file_sha256(path)
    except FileNotFoundError:
        return None


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _plan_digest(
    *,
    requested_dates: list[str],
    policy: str,
    readiness: ChoiceStockReadiness,
    catalog_content_sha256: str | None,
) -> str:
    payload = {
        "plan_digest_version": PLAN_DIGEST_VERSION,
        "requested_dates": requested_dates,
        "policy": policy,
        "catalog_content_sha256": catalog_content_sha256,
        "readiness": _stable_readiness_semantics(readiness),
        "frozen_tuple": {
            "candidate_history_rule_version": CANDIDATE_HISTORY_RULE_VERSION,
            "candidate_history_formula_version": CANDIDATE_HISTORY_FORMULA_VERSION,
            "stock_candidate_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
            "selection_policy": policy,
            "execution_formula_version": EXECUTION_FORMULA_VERSION,
            "matched_baseline_formula_version": MATCHED_BASELINE_FORMULA_VERSION,
            "metric_basis": "net_next_open_adj",
        },
    }
    return _sha256_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _stable_readiness_semantics(readiness: ChoiceStockReadiness) -> dict[str, Any]:
    raw = _mapping(readiness.model_dump(mode="json"))
    optional_input_status = _mapping(raw.get("optional_input_status"))
    return {
        "ready": bool(raw.get("ready")),
        "status": _text(raw.get("status")),
        "vendor_name": _text(raw.get("vendor_name")),
        "missing_input_families": sorted(_string_list(raw.get("missing_input_families"))),
        "unconfirmed_fields": sorted(_string_list(raw.get("unconfirmed_fields"))),
        "optional_input_status": {
            str(key): optional_input_status[key]
            for key in sorted(optional_input_status, key=str)
        },
    }


def _require_current_rule_policy(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized != EXP3B_STOCK_CANDIDATE_POLICY:
        raise ValueError(
            "current-rule replay requires "
            f"stock_candidate_policy='{EXP3B_STOCK_CANDIDATE_POLICY}'."
        )
    return EXP3B_STOCK_CANDIDATE_POLICY


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = _text(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
