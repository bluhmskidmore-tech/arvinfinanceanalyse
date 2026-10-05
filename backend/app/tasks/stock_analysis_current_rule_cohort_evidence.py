"""Read-only evidence collector for current-rule certified stock-analysis cohorts.

This module deliberately depends on a few private helpers from the existing
Livermore execution and matched-baseline flows so the production evidence path
reuses the governed formulas instead of re-implementing them. The boundary is
kept read-only: the collector opens DuckDB with ``read_only=True`` and never
writes files or database state.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
)
from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    _control_execution_pit_proof,
    generate_matched_baseline_pit_proof_rows,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    ALLOWED_DECISION_METRIC_BASIS,
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
    CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_REASON,
    CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS,
    REQUIRED_VERSION_TUPLE_FIELDS,
    _validate_runner_result,
)
from backend.app.repositories.choice_stock_adapter import (
    ChoiceStockReadiness,
    choice_stock_readiness_missing,
    load_choice_stock_readiness,
)
from backend.app.services.market_data_livermore_service import (
    PAYLOAD_CACHE_NAME,
    load_livermore_strategy_payload,
)
from backend.app.services.runtime_cache import clear_runtime_cache
from backend.app.tasks import livermore_candidate_history_materialize as execution_task
from backend.app.tasks import stock_analysis_current_rule_cohort_materialize as bundle_task

CONTROL_COUNT = 20
LOADER_ERROR_MESSAGE_MAX_CHARS = 240
SIGNAL_STATUS = "selection_completed_with_signals"
ZERO_STATUS = "selection_completed_no_signals"
POLICY_INACTIVE_STATUS = "selection_policy_inactive"
LOADER_ERROR_STATUS = "loader_error"
UNSUPPORTED_STATUS = "selection_unsupported"
REQUIRED_RUNNER_STATUSES = {
    SIGNAL_STATUS,
    ZERO_STATUS,
    POLICY_INACTIVE_STATUS,
    LOADER_ERROR_STATUS,
    UNSUPPORTED_STATUS,
}


@dataclass(frozen=True)
class _SourceReceiptBundle:
    combined_receipt: dict[str, Any]
    source_hashes: tuple[str, ...]
    source_index: dict[tuple[str, str, str, str, str], str]


def collect_stock_analysis_current_rule_cohort_evidence(
    *,
    duckdb_path: str | Path,
    evaluation_as_of_date: str,
    governed_run_id: str,
    runner_results: Sequence[Mapping[str, Any]],
    source_availability_receipts: Sequence[Mapping[str, Any]],
    frozen_version_tuple: Mapping[str, Any],
    choice_stock_readiness: ChoiceStockReadiness | Mapping[str, Any] | None = None,
    choice_stock_catalog_file: str | Path | None = None,
) -> dict[str, Any]:
    evaluation = _date_text(evaluation_as_of_date, field_name="evaluation_as_of_date")
    target = Path(duckdb_path).resolve()
    if not target.is_file():
        return {
            "status": "blocked",
            "evaluation_as_of_date": evaluation,
            "facts": [],
            "date_certificates": [],
            "zero_signal_runner_results": {},
            "date_evidence": [],
            "blockers": ["duckdb_path_missing"],
            "counts": _empty_counts(),
        }

    try:
        version_tuple = _normalize_version_tuple(frozen_version_tuple)
        normalized_governed_run_id = _required_text(
            governed_run_id,
            field_name="governed_run_id",
        )
        readiness = _resolve_choice_stock_readiness(
            choice_stock_readiness=choice_stock_readiness,
            choice_stock_catalog_file=choice_stock_catalog_file,
        )
        source_bundle = _prepare_source_receipts(
            source_availability_receipts=source_availability_receipts,
            evaluation_as_of_date=evaluation,
        )
        normalized_runner_results = _normalize_runner_results(
            runner_results=runner_results,
            evaluation_as_of_date=evaluation,
        )
    except ValueError as exc:
        return {
            "status": "blocked",
            "evaluation_as_of_date": evaluation,
            "facts": [],
            "date_certificates": [],
            "zero_signal_runner_results": {},
            "date_evidence": [],
            "blockers": [f"input_validation_failed:{type(exc).__name__}:{exc}"],
            "counts": _empty_counts(),
        }
    if readiness.ready is not True:
        return {
            "status": "blocked",
            "evaluation_as_of_date": evaluation,
            "facts": [],
            "date_certificates": [],
            "zero_signal_runner_results": {},
            "date_evidence": [],
            "blockers": ["choice_stock_readiness_not_ready"],
            "counts": _empty_counts(),
        }

    if not normalized_runner_results:
        return {
            "status": "blocked",
            "evaluation_as_of_date": evaluation,
            "facts": [],
            "date_certificates": [],
            "zero_signal_runner_results": {},
            "date_evidence": [],
            "blockers": ["runner_results_empty"],
            "counts": _empty_counts(),
        }

    blockers: list[str] = []
    date_evidence: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    date_certificates: list[dict[str, Any]] = []
    zero_signal_runner_results: dict[str, dict[str, Any]] = {}

    conn = duckdb.connect(str(target), read_only=True)
    try:
        for runner_result in normalized_runner_results:
            trade_date = str(runner_result["trade_date"])
            status = str(runner_result["status"])
            date_blockers = _runner_level_blockers(
                runner_result=runner_result,
                evaluation_as_of_date=evaluation,
            )
            if status == ZERO_STATUS and not date_blockers:
                zero_error = _validate_zero_signal_runner_result(
                    runner_result=runner_result,
                    trade_date=trade_date,
                    version_tuple=version_tuple,
                )
                if zero_error is not None:
                    date_blockers.append(zero_error)
            elif status != SIGNAL_STATUS and not date_blockers:
                date_blockers.append(f"runner_status_not_certifiable:{status}")

            if status == SIGNAL_STATUS and not date_blockers:
                collected = _collect_signal_date_evidence(
                    conn=conn,
                    duckdb_path=target,
                    governed_run_id=normalized_governed_run_id,
                    trade_date=trade_date,
                    evaluation_as_of_date=evaluation,
                    runner_result=runner_result,
                    source_bundle=source_bundle,
                    version_tuple=version_tuple,
                    stock_readiness=readiness,
                )
                date_blockers.extend(collected["blockers"])
                if not date_blockers:
                    facts.extend(collected["facts"])
                    date_certificates.append(collected["date_certificate"])
            elif status == ZERO_STATUS and not date_blockers:
                zero_signal_runner_results[trade_date] = dict(runner_result)
                date_certificates.append(
                    _zero_signal_certificate_row(
                        trade_date=trade_date,
                        source_hashes=source_bundle.source_hashes,
                        version_tuple=version_tuple,
                    )
                )

            if date_blockers:
                blockers.extend(date_blockers)
                date_evidence.append(
                    {
                        "trade_date": trade_date,
                        "status": "blocked",
                        "runner_status": status,
                        "runner_result": dict(runner_result),
                        "signal_facts": [],
                        "candidate_count": int(runner_result.get("accepted_candidate_count") or 0),
                        "matched_entry_count": 0,
                        "blockers": sorted(set(date_blockers)),
                    }
                )
            else:
                matched_entry_count = (
                    0
                    if status == ZERO_STATUS
                    else sum(
                        1
                        for row in facts
                        if row.get("signal_date") == trade_date
                    )
                )
                date_evidence.append(
                    {
                        "trade_date": trade_date,
                        "status": "ready",
                        "runner_status": status,
                        "runner_result": dict(runner_result),
                        "signal_facts": []
                        if status == ZERO_STATUS
                        else [
                            dict(row)
                            for row in facts
                            if row.get("signal_date") == trade_date
                        ],
                        "candidate_count": int(runner_result.get("accepted_candidate_count") or 0),
                        "matched_entry_count": matched_entry_count,
                        "blockers": [],
                    }
                )
    finally:
        conn.close()

    counts = _build_counts(
        facts=facts,
        date_certificates=date_certificates,
        date_evidence=date_evidence,
    )
    if counts["completed_dates"] < bundle_task.MIN_COMPLETED_DATES:
        blockers.append("completed_dates_below_threshold")
    if counts["matched_entry_count"] < bundle_task.MIN_MATCHED_ENTRIES:
        blockers.append("matched_entry_count_below_threshold")
    return {
        "status": "blocked" if blockers else "ready",
        "evaluation_as_of_date": evaluation,
        "facts": facts,
        "date_certificates": date_certificates,
        "zero_signal_runner_results": zero_signal_runner_results,
        "date_evidence": date_evidence,
        "blockers": _ordered(blockers),
        "counts": counts,
        "source_availability_receipt_sha256s": list(source_bundle.source_hashes),
    }


def _collect_signal_date_evidence(
    *,
    conn: duckdb.DuckDBPyConnection,
    duckdb_path: Path,
    governed_run_id: str,
    trade_date: str,
    evaluation_as_of_date: str,
    runner_result: Mapping[str, Any],
    source_bundle: _SourceReceiptBundle,
    version_tuple: Mapping[str, Any],
    stock_readiness: ChoiceStockReadiness,
) -> dict[str, Any]:
    blockers: list[str] = []
    payload, meta, items = _reload_signal_items(
        duckdb_path=duckdb_path,
        trade_date=trade_date,
        stock_readiness=stock_readiness,
    )
    if payload is None:
        return {
            "facts": [],
            "date_certificate": None,
            "blockers": [_text(meta.get("loader_error")) or "selection_loader_error"],
        }

    if str(meta.get("fallback_mode") or "none") != "none":
        blockers.append("selection_fallback_mode_present")

    selection_keys = _selection_keys_from_items(items, trade_date=trade_date)
    runner_keys = _runner_candidate_keys(runner_result=runner_result, trade_date=trade_date)
    if runner_keys != selection_keys:
        blockers.append("candidate_key_set_mismatch:runner_vs_selection")

    if not selection_keys:
        blockers.append("selection_items_empty_on_signal_date")
    runner_key_blockers = _runner_candidate_key_blockers(
        runner_result=runner_result,
        trade_date=trade_date,
    )
    blockers.extend(runner_key_blockers)

    signal_facts: list[dict[str, Any]] = []
    candidate_rows_for_controls: list[dict[str, Any]] = []
    candidate_execution_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    candidate_item_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    candidate_pit_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in items:
        key = _candidate_key(
            trade_date=trade_date,
            stock_code=_text(item.get("stock_code")),
            signal_kind="stock_candidate",
        )
        if key is None:
            blockers.append("selection_item_missing_stock_code")
            continue
        execution = execution_task._execution_returns_for_candidate(
            conn,
            stock_code=key[1],
            snapshot_as_of_date=trade_date,
        )
        if not isinstance(execution, dict):
            blockers.append(f"candidate_execution_missing:{key[1]}")
            continue
        future_execution_reason = _execution_future_reason(
            execution=execution,
            evaluation_as_of_date=evaluation_as_of_date,
        )
        if future_execution_reason is not None:
            blockers.append(f"{future_execution_reason}:{key[1]}")
            continue
        execution_blocker = _candidate_execution_blocker(
            execution=execution,
            stock_code=key[1],
        )
        if execution_blocker is not None:
            blockers.append(execution_blocker)
            continue
        candidate_pit = _control_execution_pit_proof(
            conn,
            stock_code=key[1],
            signal_date=trade_date,
            evaluation_as_of_date=evaluation_as_of_date,
            source_availability_index=_matched_baseline_source_index(source_bundle.source_index),
        )
        candidate_pit_blocker = _candidate_pit_blocker(
            candidate_pit=candidate_pit,
            stock_code=key[1],
        )
        if candidate_pit_blocker is not None:
            blockers.append(candidate_pit_blocker)
            continue
        mismatch = _candidate_execution_pit_mismatch(
            execution=execution,
            candidate_pit=candidate_pit,
            stock_code=key[1],
        )
        if mismatch is not None:
            blockers.append(mismatch)
            continue
        candidate_sources = _mapping(candidate_pit.get("source_evidence"))
        try:
            bundle_task._validate_v4_limit_price_evidence(
                candidate_sources.get("limit_price"),
                observation=_mapping(candidate_sources.get("observation")),
                source_index=source_bundle.source_index,
                evaluation=evaluation_as_of_date,
                entry_date=_text(execution.get("entry_date")) or "",
                exit_date_5d=_text(execution.get("exit_date_5d")) or "",
                exit_date_20d=_text(execution.get("exit_date_20d")) or "",
                field_label="candidate source evidence",
            )
        except bundle_task.CurrentRuleCohortError:
            blockers.append(f"candidate_limit_price_evidence_invalid:{key[1]}")
            continue
        candidate_execution_by_key[key] = execution
        candidate_item_by_key[key] = item
        candidate_rows_for_controls.append(
            {
                "signal_date": trade_date,
                "stock_code": key[1],
                "signal_kind": "stock_candidate",
                "market_state": _text(item.get("market_state")) or _text(runner_result.get("market_state")) or "unknown",
                "candidate_rank": _int_or_default(item.get("rank"), default=999_999),
                "stock_name": _text(item.get("stock_name")) or key[1],
                "sector_code": _text(item.get("sector_code")),
                "sector_name": _text(item.get("sector_name")),
                "run_id": governed_run_id,
            }
        )
        candidate_pit_by_key[key] = dict(candidate_pit)

    fact_keys_from_execution = set(candidate_execution_by_key)
    if selection_keys != fact_keys_from_execution:
        blockers.append("candidate_key_set_mismatch:selection_vs_execution")
    if runner_keys != fact_keys_from_execution:
        blockers.append("candidate_key_set_mismatch:runner_vs_execution")
    if blockers:
        return {"facts": [], "date_certificate": None, "blockers": _ordered(blockers)}

    control_rows = generate_matched_baseline_pit_proof_rows(
        conn,
        candidate_rows=candidate_rows_for_controls,
        evaluation_as_of_date=evaluation_as_of_date,
        source_availability_receipt=source_bundle.combined_receipt,
        sample_size=CONTROL_COUNT,
    )
    controls_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in control_rows:
        key = _candidate_key(
            trade_date=_text(row.get("signal_date")),
            stock_code=_text(row.get("candidate_stock_code")),
            signal_kind=_text(row.get("signal_kind")) or "stock_candidate",
        )
        if key is None:
            blockers.append("control_row_missing_candidate_key")
            continue
        controls_by_key[key].append(dict(row))

    if blockers:
        return {"facts": [], "date_certificate": None, "blockers": _ordered(blockers)}

    for key in sorted(fact_keys_from_execution):
        item = candidate_item_by_key[key]
        execution = candidate_execution_by_key[key]
        control_group_rows = controls_by_key.get(key, [])
        control_blocker = _control_row_blocker(
            candidate_key=key,
            control_rows=control_group_rows,
            evaluation_as_of_date=evaluation_as_of_date,
            source_hashes=source_bundle.source_hashes,
            source_index=source_bundle.source_index,
        )
        if control_blocker is not None:
            blockers.append(control_blocker)
            continue
        matched_alpha_5d = float(cast(float, execution["return_5d_net_adj"])) - (
            sum(float(row["control_return_5d_net_adj"]) for row in control_group_rows) / CONTROL_COUNT
        )
        matched_alpha_20d = float(cast(float, execution["return_20d_net_adj"])) - (
            sum(float(row["control_return_20d_net_adj"]) for row in control_group_rows) / CONTROL_COUNT
        )
        signal_facts.append(
            {
                "signal_date": trade_date,
                "stock_code": key[1],
                "stock_name": _text(item.get("stock_name")) or key[1],
                "signal_kind": key[2],
                "candidate_rank": _int_or_default(item.get("rank"), default=999_999),
                "market_state": _text(item.get("market_state")) or _text(runner_result.get("market_state")) or "unknown",
                "entry_date": execution["entry_date"],
                "entry_price": execution["entry_price"],
                "entry_price_kind": execution["entry_price_kind"],
                "entry_executable": execution["entry_executable"],
                "exit_date_5d": execution["exit_date_5d"],
                "exit_price_5d": execution["exit_price_5d"],
                "return_5d_net_adj": execution["return_5d_net_adj"],
                "exit_date_20d": execution["exit_date_20d"],
                "exit_price_20d": execution["exit_price_20d"],
                "return_20d_net_adj": execution["return_20d_net_adj"],
                "price_adjustment_mode": execution["price_adjustment_mode"],
                "candidate_data_status": "usable",
                "execution_data_status": "usable",
                "matched_baseline_status": "usable",
                "matched_baseline_control_count": CONTROL_COUNT,
                "matched_alpha_5d": matched_alpha_5d,
                "matched_alpha_20d": matched_alpha_20d,
                "control_eval_basis": ALLOWED_DECISION_METRIC_BASIS,
                "control_pit_proof": {
                    "source_availability_receipt_sha256s": list(source_bundle.source_hashes),
                    "controls": control_group_rows,
                },
                "candidate_source_evidence": dict(
                    _mapping(candidate_pit_by_key[key].get("source_evidence"))
                ),
                "evidence": {
                    "runner_status": runner_result.get("status"),
                    "runner_status_reason": runner_result.get("status_reason"),
                    "selection_formula_version": version_tuple["stock_candidate_selection_formula_version"],
                    "governed_run_id": governed_run_id,
                    "candidate_pit_summary": {
                        "entry": {
                            "trade_date": _mapping(candidate_pit_by_key[key].get("entry")).get("trade_date"),
                            "price_kind": _mapping(candidate_pit_by_key[key].get("entry")).get("price_kind"),
                            "usable": _mapping(candidate_pit_by_key[key].get("entry")).get("usable"),
                        },
                        "horizons": {
                            horizon: {
                                "trade_date": _mapping(
                                    _mapping(candidate_pit_by_key[key].get("horizons")).get(horizon)
                                ).get("trade_date"),
                                "usable": _mapping(
                                    _mapping(candidate_pit_by_key[key].get("horizons")).get(horizon)
                                ).get("usable"),
                            }
                            for horizon in ("5d", "20d")
                        },
                    },
                },
                **{field: version_tuple[field] for field in bundle_task.ROW_VERSION_FIELDS},
            }
        )

    final_fact_keys = {
        key
        for row in signal_facts
        if (key := _candidate_key(trade_date=_text(row.get("signal_date")), stock_code=_text(row.get("stock_code")), signal_kind=_text(row.get("signal_kind"))))
        is not None
    }
    if selection_keys != final_fact_keys:
        blockers.append("candidate_key_set_mismatch:selection_vs_facts")
    if runner_keys != final_fact_keys:
        blockers.append("candidate_key_set_mismatch:runner_vs_facts")
    if blockers:
        return {"facts": [], "date_certificate": None, "blockers": _ordered(blockers)}

    date_certificate = _signal_date_certificate_row(
        trade_date=trade_date,
        fact_count=len(signal_facts),
        source_hashes=source_bundle.source_hashes,
        version_tuple=version_tuple,
    )
    return {
        "facts": signal_facts,
        "date_certificate": date_certificate,
        "blockers": [],
    }


def _reload_signal_items(
    *,
    duckdb_path: Path,
    trade_date: str,
    stock_readiness: ChoiceStockReadiness,
) -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, Any]]]:
    payload: dict[str, Any] | None = None
    meta: dict[str, Any] = {}
    try:
        loaded_payload, loaded_meta = load_livermore_strategy_payload(
            duckdb_path=str(duckdb_path),
            as_of_date=date.fromisoformat(trade_date),
            stock_readiness=stock_readiness,
            backfill_mode=True,
            stock_candidate_policy=EXP3B_STOCK_CANDIDATE_POLICY,
            theme_overlay_reader=None,
        )
        payload = dict(loaded_payload) if isinstance(loaded_payload, dict) else {}
        meta = dict(loaded_meta) if isinstance(loaded_meta, dict) else {}
    except Exception as exc:  # noqa: BLE001 - Any strategy-loader failure becomes a sanitized blocker and no signal evidence, never cohort authority.
        meta = {"loader_error": _loader_error_blocker(exc)}
        payload = None
    finally:
        clear_runtime_cache(PAYLOAD_CACHE_NAME)
    if payload is None:
        return None, meta, []
    if _text(payload.get("as_of_date")) != trade_date:
        return payload, meta, []
    stock_candidates = payload.get("stock_candidates")
    if not isinstance(stock_candidates, dict):
        return payload, meta, []
    if _text(stock_candidates.get("selection_policy")) != EXP3B_STOCK_CANDIDATE_POLICY:
        return payload, meta, []
    if _text(stock_candidates.get("formula_version")) != STOCK_CANDIDATE_FORMULA_VERSION:
        return payload, meta, []
    items = [
        item
        for item in execution_task._build_signal_rows(payload)
        if isinstance(item, dict)
        and _text(item.get("signal_kind")) == "stock_candidate"
        and _text(item.get("stock_code"))
    ]
    items.sort(
        key=lambda item: (
            _int_or_default(item.get("rank"), default=999_999),
            _text(item.get("stock_code")) or "",
        )
    )
    return payload, meta, items


def _prepare_source_receipts(
    *,
    source_availability_receipts: Sequence[Mapping[str, Any]],
    evaluation_as_of_date: str,
) -> _SourceReceiptBundle:
    if not source_availability_receipts:
        raise ValueError("source_availability_receipts is required.")
    source_hashes: list[str] = []
    source_index: dict[tuple[str, str, str, str, str], str] = {}
    combined_sources: list[dict[str, Any]] = []
    for index, raw_receipt in enumerate(source_availability_receipts):
        receipt = dict(raw_receipt)
        source_hash = bundle_task._canonical_sha256(receipt)
        if source_hash in source_hashes:
            raise ValueError("duplicate source availability receipt hash.")
        source_hashes.append(source_hash)
        receipt_index = bundle_task._validate_source_availability_receipt(
            receipt,
            evaluation=evaluation_as_of_date,
        )
        overlapping = set(source_index).intersection(receipt_index)
        if overlapping:
            raise ValueError("duplicate source availability key across receipts.")
        source_index.update(receipt_index)
        raw_sources = receipt.get("sources")
        if not isinstance(raw_sources, list):
            raise ValueError(f"source_availability_receipts[{index}].sources must be a list.")
        for raw_source in raw_sources:
            if not isinstance(raw_source, dict):
                raise ValueError("source availability sources must be objects.")
            combined_sources.append(dict(raw_source))
    combined_receipt = {
        "receipt_kind": "pit_source_availability_v1",
        "sources": combined_sources,
    }
    return _SourceReceiptBundle(
        combined_receipt=combined_receipt,
        source_hashes=tuple(sorted(source_hashes)),
        source_index=source_index,
    )


def _normalize_version_tuple(value: Mapping[str, Any]) -> dict[str, Any]:
    version_tuple = dict(value)
    missing = [field for field in REQUIRED_VERSION_TUPLE_FIELDS if field not in version_tuple]
    if missing:
        raise ValueError("frozen_version_tuple missing required fields: " + ", ".join(missing))
    if _text(version_tuple.get("macro_formula_version")) is None:
        raise ValueError("macro_formula_version is required.")
    if version_tuple.get("stock_candidate_selection_policy") != EXP3B_STOCK_CANDIDATE_POLICY:
        raise ValueError("stock_candidate_selection_policy must equal exp3b.")
    if version_tuple.get("stock_candidate_selection_formula_version") != STOCK_CANDIDATE_FORMULA_VERSION:
        raise ValueError("stock_candidate_selection_formula_version must equal current v7.")
    if version_tuple.get("matched_baseline_formula_version") != MATCHED_BASELINE_FORMULA_VERSION:
        raise ValueError("matched_baseline_formula_version must equal current v3.")
    if version_tuple.get("decision_metric_basis") != ALLOWED_DECISION_METRIC_BASIS:
        raise ValueError("decision_metric_basis must equal net_next_open_adj.")
    if version_tuple.get("coverage_authority_mode") != CURRENT_RULE_COVERAGE_AUTHORITY_MODE:
        raise ValueError("coverage_authority_mode mismatch.")
    if version_tuple.get("strict_coverage") is not True:
        raise ValueError("strict_coverage must be true.")
    if version_tuple.get("fallback_covered") is not False:
        raise ValueError("fallback_covered must be false.")
    return version_tuple


def _resolve_choice_stock_readiness(
    *,
    choice_stock_readiness: ChoiceStockReadiness | Mapping[str, Any] | None,
    choice_stock_catalog_file: str | Path | None,
) -> ChoiceStockReadiness:
    if isinstance(choice_stock_readiness, ChoiceStockReadiness):
        return choice_stock_readiness
    if (
        choice_stock_readiness is not None
        and hasattr(choice_stock_readiness, "ready")
        and hasattr(choice_stock_readiness, "status")
    ):
        return choice_stock_readiness  # type: ignore[return-value]
    if isinstance(choice_stock_readiness, Mapping):
        class _MappingReadiness:
            def __init__(self, raw: Mapping[str, Any]) -> None:
                self._raw = dict(raw)
                self.ready = bool(raw.get("ready"))
                self.status = str(raw.get("status") or "")

            def model_dump(self, mode: str = "json") -> dict[str, Any]:
                return dict(self._raw)

        return _MappingReadiness(choice_stock_readiness)  # type: ignore[return-value]
    catalog = str(choice_stock_catalog_file or "").strip()
    if not catalog:
        return choice_stock_readiness_missing("")
    return load_choice_stock_readiness(catalog)


def _normalize_runner_results(
    *,
    runner_results: Sequence[Mapping[str, Any]],
    evaluation_as_of_date: str,
) -> list[dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(runner_results):
        item = dict(raw)
        trade_date = _date_text(
            item.get("trade_date") or item.get("requested_as_of_date"),
            field_name=f"runner_results[{index}].trade_date",
        )
        item["trade_date"] = trade_date
        status = _text(item.get("status"))
        if status not in REQUIRED_RUNNER_STATUSES:
            raise ValueError(f"runner_results[{index}] has unsupported status: {status}")
        if trade_date in normalized:
            raise ValueError(f"duplicate runner_result trade_date: {trade_date}")
        if trade_date > evaluation_as_of_date:
            item.setdefault("future_business_date_violations", []).append(
                {"path": "runner.trade_date", "key": "trade_date", "value": trade_date}
            )
        normalized[trade_date] = item
    return [normalized[key] for key in sorted(normalized)]


def _runner_level_blockers(
    *,
    runner_result: Mapping[str, Any],
    evaluation_as_of_date: str,
) -> list[str]:
    blockers: list[str] = []
    trade_date = str(runner_result["trade_date"])
    if trade_date > evaluation_as_of_date:
        blockers.append("runner_trade_date_after_evaluation")
    if _list_length(runner_result.get("future_business_date_violations")):
        blockers.append("runner_future_business_date_violation")
    if _list_length(runner_result.get("future_availability_violations")):
        blockers.append("runner_future_availability_violation")
    if _list_length(runner_result.get("blockers")):
        blockers.append("runner_blockers_present")
    return blockers


def _validate_zero_signal_runner_result(
    *,
    runner_result: Mapping[str, Any],
    trade_date: str,
    version_tuple: Mapping[str, Any],
) -> str | None:
    try:
        _validate_runner_result(
            runner_result=runner_result,
            trade_date=trade_date,
            version_tuple=version_tuple,
        )
    except Exception as exc:  # noqa: BLE001 - Certificate-validator failures must invalidate zero-signal evidence instead of granting authority or aborting blocker assembly.
        return f"zero_signal_runner_invalid:{type(exc).__name__}:{exc}"
    return None


def _runner_candidate_keys(
    *,
    runner_result: Mapping[str, Any],
    trade_date: str,
) -> set[tuple[str, str, str]]:
    accepted = _string_list(
        runner_result.get("accepted_candidate_codes")
        or runner_result.get("candidate_codes")
        or []
    )
    return {
        key
        for code in accepted
        if (key := _candidate_key(trade_date=trade_date, stock_code=code, signal_kind="stock_candidate"))
        is not None
    }


def _runner_candidate_key_blockers(
    *,
    runner_result: Mapping[str, Any],
    trade_date: str,
) -> list[str]:
    status = _text(runner_result.get("status"))
    if status != SIGNAL_STATUS:
        return []
    candidate_codes = _normalized_candidate_code_list(runner_result.get("candidate_codes"))
    accepted_codes = _normalized_candidate_code_list(runner_result.get("accepted_candidate_codes"))
    unique_codes = _normalized_candidate_code_list(runner_result.get("unique_candidate_codes"))
    duplicate_codes = _normalized_candidate_code_list(runner_result.get("duplicate_candidate_codes"))
    candidate_count = _int_or_default(runner_result.get("candidate_count"), default=-1)
    candidate_item_count = _int_or_default(runner_result.get("candidate_item_count"), default=-1)
    accepted_candidate_count = _int_or_default(
        runner_result.get("accepted_candidate_count"),
        default=-1,
    )
    blockers: list[str] = []
    if duplicate_codes:
        blockers.append("runner_duplicate_candidate_codes_present")
    if len(set(candidate_codes)) != len(candidate_codes):
        blockers.append("runner_candidate_codes_not_unique")
    if candidate_count != len(candidate_codes):
        blockers.append("runner_candidate_count_mismatch")
    if candidate_item_count != len(candidate_codes):
        blockers.append("runner_candidate_item_count_mismatch")
    if accepted_candidate_count != len(accepted_codes):
        blockers.append("runner_accepted_candidate_count_mismatch")
    if candidate_codes != accepted_codes:
        blockers.append("runner_candidate_vs_accepted_codes_mismatch")
    if set(candidate_codes) != set(unique_codes):
        blockers.append("runner_candidate_vs_unique_codes_mismatch")
    candidate_keys = _runner_candidate_keys(runner_result=runner_result, trade_date=trade_date)
    if len(candidate_keys) != len(candidate_codes):
        blockers.append("runner_candidate_key_set_deduplicated")
    return blockers


def _selection_keys_from_items(
    items: Sequence[Mapping[str, Any]],
    *,
    trade_date: str,
) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for item in items:
        stock_code = _text(item.get("stock_code"))
        if stock_code is None:
            continue
        key = _candidate_key(
            trade_date=trade_date,
            stock_code=stock_code,
            signal_kind="stock_candidate",
        )
        if key is not None:
            keys.add(key)
    return keys


def _candidate_execution_blocker(
    *,
    execution: Mapping[str, Any],
    stock_code: str,
) -> str | None:
    if execution.get("entry_executable") is not True:
        return f"candidate_entry_not_executable:{stock_code}"
    if execution.get("entry_price_kind") != "next_open":
        return f"candidate_entry_not_next_open:{stock_code}"
    if execution.get("price_adjustment_mode") != "adj_factor_ratio":
        return f"candidate_price_adjustment_mode_invalid:{stock_code}"
    if execution.get("data_status") != "complete":
        return f"candidate_execution_not_complete:{stock_code}"
    required_fields = (
        "entry_date",
        "entry_price",
        "exit_date_5d",
        "exit_price_5d",
        "return_5d_net_adj",
        "exit_date_20d",
        "exit_price_20d",
        "return_20d_net_adj",
    )
    for field in required_fields:
        if execution.get(field) is None:
            return f"candidate_execution_missing_{field}:{stock_code}"
    return None


def _execution_future_reason(
    *,
    execution: Mapping[str, Any],
    evaluation_as_of_date: str,
) -> str | None:
    for field in ("entry_date", "exit_date_5d", "exit_date_20d"):
        text = _text(execution.get(field))
        if text is not None and text > evaluation_as_of_date:
            return "candidate_execution_after_evaluation"
    return None


def _candidate_pit_blocker(
    *,
    candidate_pit: Mapping[str, Any],
    stock_code: str,
) -> str | None:
    entry = _mapping(candidate_pit.get("entry"))
    horizons = _mapping(candidate_pit.get("horizons"))
    if entry.get("usable") is not True or entry.get("executable") is not True:
        return f"candidate_pit_entry_unusable:{stock_code}"
    for horizon in ("5d", "20d"):
        payload = _mapping(horizons.get(horizon))
        if payload.get("usable") is not True:
            return f"candidate_pit_{horizon}_unusable:{stock_code}"
    if candidate_pit.get("failure_reason"):
        return f"candidate_pit_failure_reason_present:{stock_code}"
    return None


def _candidate_execution_pit_mismatch(
    *,
    execution: Mapping[str, Any],
    candidate_pit: Mapping[str, Any],
    stock_code: str,
) -> str | None:
    entry = _mapping(candidate_pit.get("entry"))
    horizons = _mapping(candidate_pit.get("horizons"))
    checks = (
        (execution.get("entry_date"), entry.get("trade_date"), "entry_date"),
        (execution.get("entry_price"), entry.get("price"), "entry_price"),
        (execution.get("exit_date_5d"), _mapping(horizons.get("5d")).get("trade_date"), "exit_date_5d"),
        (execution.get("exit_price_5d"), _mapping(horizons.get("5d")).get("price"), "exit_price_5d"),
        (execution.get("return_5d_net_adj"), _mapping(horizons.get("5d")).get("net_adj_return"), "return_5d_net_adj"),
        (execution.get("exit_date_20d"), _mapping(horizons.get("20d")).get("trade_date"), "exit_date_20d"),
        (execution.get("exit_price_20d"), _mapping(horizons.get("20d")).get("price"), "exit_price_20d"),
        (execution.get("return_20d_net_adj"), _mapping(horizons.get("20d")).get("net_adj_return"), "return_20d_net_adj"),
    )
    for left, right, field in checks:
        if isinstance(left, (int, float)) or isinstance(right, (int, float)):
            if left is None or right is None or abs(float(left) - float(right)) > 1e-12:
                return f"candidate_execution_pit_mismatch:{stock_code}:{field}"
        elif _text(left) != _text(right):
            return f"candidate_execution_pit_mismatch:{stock_code}:{field}"
    return None


def _control_row_blocker(
    *,
    candidate_key: tuple[str, str, str],
    control_rows: Sequence[Mapping[str, Any]],
    evaluation_as_of_date: str,
    source_hashes: tuple[str, ...],
    source_index: Mapping[tuple[str, str, str, str, str], str],
) -> str | None:
    if len(control_rows) != CONTROL_COUNT:
        return f"control_count_mismatch:{candidate_key[1]}"
    control_codes: set[str] = set()
    for row in control_rows:
        code = _text(row.get("control_stock_code"))
        if code is None or code == candidate_key[1] or code in control_codes:
            return f"control_codes_invalid:{candidate_key[1]}"
        control_codes.add(code)
        if row.get("control_entry_executable") is not True:
            return f"control_entry_not_executable:{candidate_key[1]}"
        if row.get("control_entry_usable") is not True:
            return f"control_entry_not_usable:{candidate_key[1]}"
        if row.get("control_return_5d_usable") is not True or row.get("control_return_20d_usable") is not True:
            return f"control_horizon_not_usable:{candidate_key[1]}"
        for field in (
            "control_entry_failure_reason",
            "control_failure_reason_5d",
            "control_failure_reason_20d",
            "control_failure_reason",
        ):
            if row.get(field):
                return f"control_failure_reason_present:{candidate_key[1]}"
        if row.get("formula_version") != MATCHED_BASELINE_FORMULA_VERSION:
            return f"control_formula_version_mismatch:{candidate_key[1]}"
        if row.get("metric_basis") != ALLOWED_DECISION_METRIC_BASIS:
            return f"control_metric_basis_mismatch:{candidate_key[1]}"
        if row.get("price_adjustment_mode") != "adj_factor_ratio":
            return f"control_price_adjustment_mode_mismatch:{candidate_key[1]}"
        if row.get("control_entry_price_kind") != "open":
            return f"control_entry_price_kind_mismatch:{candidate_key[1]}"
        if row.get("evaluation_as_of_date") != evaluation_as_of_date:
            return f"control_evaluation_date_mismatch:{candidate_key[1]}"
        if row.get("candidate_stock_code") != candidate_key[1]:
            return f"control_candidate_stock_mismatch:{candidate_key[1]}"
        if row.get("signal_date") != candidate_key[0] or row.get("signal_kind") != candidate_key[2]:
            return f"control_candidate_key_mismatch:{candidate_key[1]}"
        if _text(row.get("control_entry_date")) is None or _text(row.get("control_exit_date_5d")) is None or _text(row.get("control_exit_date_20d")) is None:
            return f"control_leaf_missing:{candidate_key[1]}"
        if cast(str, _text(row.get("control_exit_date_20d"))) > evaluation_as_of_date:
            return f"control_exit_after_evaluation:{candidate_key[1]}"
        source_evidence = _mapping(row.get("source_evidence"))
        source_error = _source_evidence_blocker(
            source_evidence=source_evidence,
            source_hashes=source_hashes,
            evaluation_as_of_date=evaluation_as_of_date,
            source_index=source_index,
            entry_date=_text(row.get("control_entry_date")) or "",
            exit_date_5d=_text(row.get("control_exit_date_5d")) or "",
            exit_date_20d=_text(row.get("control_exit_date_20d")) or "",
        )
        if source_error is not None:
            return f"{source_error}:{candidate_key[1]}"
    return None


def _source_evidence_blocker(
    *,
    source_evidence: Mapping[str, Any],
    source_hashes: tuple[str, ...],
    evaluation_as_of_date: str,
    source_index: Mapping[tuple[str, str, str, str, str], str],
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
) -> str | None:
    observation = _mapping(source_evidence.get("observation"))
    adjustment = _mapping(source_evidence.get("adjustment_factor"))
    for group_name, group in (("observation", observation), ("adjustment_factor", adjustment)):
        required_leafs = {"entry", "exit_5d", "exit_20d"}
        if not required_leafs.issubset(set(group)):
            return f"control_source_leaf_missing:{group_name}"
        for leaf_name in ("entry", "exit_5d", "exit_20d"):
            leaf = _mapping(group.get(leaf_name))
            if leaf.get("availability_status") != "available":
                return f"control_source_unavailable:{group_name}:{leaf_name}"
            available_at = _text(leaf.get("available_at"))
            if available_at is None or available_at > evaluation_as_of_date:
                return f"control_source_after_evaluation:{group_name}:{leaf_name}"
            table = _text(group.get("table"))
            if table is None:
                return f"control_source_table_missing:{group_name}"
            source_version = _text(leaf.get("source_version"))
            run_id = _text(leaf.get("run_id"))
            if source_version is None or run_id is None:
                return f"control_source_metadata_missing:{group_name}:{leaf_name}"
            receipt_key = (
                table,
                source_version,
                _text(leaf.get("vendor_version")) or "",
                _text(leaf.get("rule_version")) or "",
                run_id,
            )
            if source_index.get(receipt_key) != available_at:
                return f"control_source_receipt_mismatch:{group_name}:{leaf_name}"
    if not source_hashes:
        return "source_receipts_missing"
    try:
        bundle_task._validate_v4_limit_price_evidence(
            source_evidence.get("limit_price"),
            observation=observation,
            source_index=source_index,
            evaluation=evaluation_as_of_date,
            entry_date=entry_date,
            exit_date_5d=exit_date_5d,
            exit_date_20d=exit_date_20d,
            field_label="control source evidence",
        )
    except bundle_task.CurrentRuleCohortError:
        return "control_limit_price_evidence_invalid"
    return None


def _signal_date_certificate_row(
    *,
    trade_date: str,
    fact_count: int,
    source_hashes: tuple[str, ...],
    version_tuple: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "trade_date": trade_date,
        "certificate_status": "completed_with_signals",
        "reason_code": "current_rule_fully_proven",
        "affects_completed_stats": True,
        "candidate_count": fact_count,
        "executable_candidate_count": fact_count,
        "t5_usable_count": fact_count,
        "t20_usable_count": fact_count,
        "matched_entry_count": fact_count,
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
        "unsupported_source_count": 0,
        "proxy_only_evidence_count": 0,
        "blocking_gap_count": 0,
        "control_entry_proven_count": fact_count * CONTROL_COUNT,
        "control_exit_proven_5d_count": fact_count * CONTROL_COUNT,
        "control_exit_proven_20d_count": fact_count * CONTROL_COUNT,
        "control_eval_proof": {
            "source_availability_receipt_sha256s": list(source_hashes),
        },
        "source_coverage": {"strict": True, "fallback": False},
        "blocker_detail": {},
        **{field: version_tuple[field] for field in bundle_task.ROW_VERSION_FIELDS},
    }


def _zero_signal_certificate_row(
    *,
    trade_date: str,
    source_hashes: tuple[str, ...],
    version_tuple: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "trade_date": trade_date,
        "certificate_status": CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS,
        "reason_code": CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_REASON,
        "affects_completed_stats": True,
        "candidate_count": 0,
        "executable_candidate_count": 0,
        "t5_usable_count": 0,
        "t20_usable_count": 0,
        "matched_entry_count": 0,
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
        "unsupported_source_count": 0,
        "proxy_only_evidence_count": 0,
        "blocking_gap_count": 0,
        "control_entry_proven_count": 0,
        "control_exit_proven_5d_count": 0,
        "control_exit_proven_20d_count": 0,
        "control_eval_proof": {
            "source_availability_receipt_sha256s": list(source_hashes),
        },
        "source_coverage": {"strict": True, "fallback": False},
        "blocker_detail": {},
        **{field: version_tuple[field] for field in bundle_task.ROW_VERSION_FIELDS},
    }


def _build_counts(
    *,
    facts: Sequence[Mapping[str, Any]],
    date_certificates: Sequence[Mapping[str, Any]],
    date_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    counts = _empty_counts()
    counts["blocked_dates"] = sum(item.get("status") == "blocked" for item in date_evidence)
    counts["completed_dates"] = len(date_certificates)
    counts["completed_with_signals_dates"] = sum(
        item.get("certificate_status") == "completed_with_signals"
        for item in date_certificates
    )
    counts["completed_no_signal_dates"] = sum(
        item.get("certificate_status") == CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS
        for item in date_certificates
    )
    counts["matched_entry_count"] = len(facts)
    counts["t5_usable_count"] = len(facts)
    counts["t20_usable_count"] = len(facts)
    return counts


def _empty_counts() -> dict[str, int]:
    return {
        "blocked_dates": 0,
        "completed_dates": 0,
        "completed_with_signals_dates": 0,
        "completed_no_signal_dates": 0,
        "matched_entry_count": 0,
        "t5_usable_count": 0,
        "t20_usable_count": 0,
    }


def _matched_baseline_source_index(
    source_index: Mapping[tuple[str, str, str, str, str], str],
) -> dict[tuple[str, str | None, str | None, str | None, str | None], str]:
    return {
        (
            table,
            source_version,
            vendor_version or None,
            rule_version or None,
            run_id,
        ): available_at
        for (table, source_version, vendor_version, rule_version, run_id), available_at in source_index.items()
    }


def _candidate_key(
    *,
    trade_date: str | None,
    stock_code: str | None,
    signal_kind: str | None,
) -> tuple[str, str, str] | None:
    normalized_date = _text(trade_date)
    normalized_code = _text(stock_code)
    normalized_kind = _text(signal_kind) or "stock_candidate"
    if normalized_date is None or normalized_code is None:
        return None
    return normalized_date, normalized_code.upper(), normalized_kind


def _ordered(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            ordered.append(normalized)
            seen.add(normalized)
    return ordered


def _loader_error_blocker(exc: Exception) -> str:
    error_type = exc.__class__.__name__ or "Exception"
    message = _sanitize_loader_error_message(str(exc))
    if message is None:
        return f"selection_loader_error:{error_type}"
    return f"selection_loader_error:{error_type}:{message}"


def _sanitize_loader_error_message(value: str) -> str | None:
    text = _text(value)
    if text is None:
        return None
    text = re.sub(r"(?:[A-Za-z]:\\|\\\\)[^\s]+", "<path>", text)
    text = re.sub(r"(?:(?<=\s)|^)(?:\.\.?/|/)[^\s]+", "<path>", text)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    if len(text) > LOADER_ERROR_MESSAGE_MAX_CHARS:
        text = f"{text[: LOADER_ERROR_MESSAGE_MAX_CHARS - 3].rstrip()}..."
    return text or None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    out: list[str] = []
    for item in value:
        text = _text(item)
        if text is not None:
            out.append(text)
    return out


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_default(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _required_text(value: Any, *, field_name: str) -> str:
    text = _text(value)
    if text is None:
        raise ValueError(f"{field_name} is required.")
    return text


def _normalized_candidate_code_list(value: Any) -> list[str]:
    return [
        text.upper()
        for text in _string_list(value)
        if text is not None
    ]


def _date_text(value: Any, *, field_name: str) -> str:
    text = _text(value)
    if text is None:
        raise ValueError(f"{field_name} is required.")
    parsed = date.fromisoformat(text)
    if parsed.isoformat() != text:
        raise ValueError(f"{field_name} must be strict YYYY-MM-DD.")
    return text


def _list_length(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0
