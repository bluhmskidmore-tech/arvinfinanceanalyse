from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
    stock_candidate_policy_active_market_states,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    APPROVED_AUTHORITY_STATUS,
    validate_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    ALLOWED_DECISION_METRIC_BASIS,
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
    CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_REASON,
    CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS,
    REQUIRED_VERSION_TUPLE_FIELDS,
    build_current_rule_zero_signal_certificate,
)
from backend.app.tasks.stock_analysis_current_rule_cohort_materialize import (
    BUNDLE_KIND,
    COHORT_MODE,
    CONTROL_COUNT,
    MIN_COMPLETED_DATES,
    MIN_MATCHED_ENTRIES,
    PAGE_ID,
    ROW_VERSION_FIELDS,
    CurrentRuleCohortError,
    _validate_source_availability_receipt,
    _validate_v4_limit_price_evidence,
    build_stock_analysis_current_rule_cohort_dry_run,
)

GOVERNED_RUN_ID_PREFIX = "stock-analysis-current-rule-governed-v1"
MAX_JSON_INPUT_BYTES = 5 * 1024 * 1024


def derive_expected_stock_analysis_current_rule_governed_run_id(
    *,
    calendar_receipt_sha256: str,
    source_availability_receipt_sha256s: Sequence[str],
    frozen_version_tuple: Mapping[str, Any],
    evaluation_as_of_date: str,
    open_dates: Sequence[str],
) -> str:
    normalized_source_receipt_sha256s = sorted(
        _sha256_text(value, "source_availability_receipt_sha256s[]")
        for value in source_availability_receipt_sha256s
    )
    if not normalized_source_receipt_sha256s:
        raise CurrentRuleCohortError(
            "source_availability_receipt_sha256s must contain at least one receipt hash"
        )
    normalized_open_dates = [
        _date_text(value, "open_dates[]") for value in open_dates
    ]
    if not normalized_open_dates:
        raise CurrentRuleCohortError("open_dates must contain at least one open trade date")
    digest = _canonical_sha256(
        {
            "calendar_receipt_sha256": _sha256_text(
                calendar_receipt_sha256,
                "calendar_receipt_sha256",
            ),
            "source_availability_receipt_sha256s": normalized_source_receipt_sha256s,
            "frozen_version_tuple": _freeze_version_tuple(frozen_version_tuple),
            "evaluation_as_of_date": _date_text(
                evaluation_as_of_date,
                "evaluation_as_of_date",
            ),
            "open_dates": normalized_open_dates,
        }
    )
    return f"{GOVERNED_RUN_ID_PREFIX}-{digest}"


def produce_stock_analysis_current_rule_cohort_bundle(
    *,
    duckdb_path: str | Path,
    approved_calendar_receipt_path: str | Path,
    source_availability_receipt_paths: Sequence[str | Path],
    trusted_evidence_root: str | Path,
    output_root: str | Path,
    batch_name: str,
    cohort_id: str,
    run_id: str,
    governed_run_id: str,
    evaluation_as_of_date: str,
    frozen_version_tuple: Mapping[str, Any],
    date_evidence: Sequence[Mapping[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    target = _existing_file(duckdb_path, field_name="duckdb_path")
    trusted_root = _existing_directory(
        trusted_evidence_root,
        field_name="trusted_evidence_root",
    )
    output_dir = _existing_directory(output_root, field_name="output_root")
    batch_dir = _prepare_output_directory(output_dir, batch_name=batch_name)
    created_at_text = _datetime_text(created_at, field_name="created_at")
    created_at_dt = _parse_datetime(created_at_text, field_name="created_at")
    evaluation = _date_text(
        evaluation_as_of_date,
        field_name="evaluation_as_of_date",
    )
    version_tuple = _freeze_version_tuple(frozen_version_tuple)

    calendar_source_path = _trusted_existing_file(
        trusted_root=trusted_root,
        raw_path=approved_calendar_receipt_path,
        field_name="approved_calendar_receipt_path",
    )
    calendar_payload = _load_json_object(
        calendar_source_path,
        field_name="approved_calendar_receipt_path",
    )
    ok, errors = validate_stock_analysis_calendar_receipt(calendar_payload)
    if not ok:
        raise CurrentRuleCohortError(
            "approved calendar receipt is invalid: " + "; ".join(errors)
        )
    if calendar_payload.get("authority_status") != APPROVED_AUTHORITY_STATUS:
        raise CurrentRuleCohortError("approved calendar receipt must be approved")
    if calendar_payload.get("certification_allowed") is not True:
        raise CurrentRuleCohortError(
            "approved calendar receipt must allow certification"
        )
    calendar_sha = _sha256_text(
        calendar_payload.get("canonical_receipt_sha256"),
        "approved_calendar_receipt_path.canonical_receipt_sha256",
    )
    open_dates = _open_calendar_dates(calendar_payload)
    if not open_dates:
        raise CurrentRuleCohortError(
            "approved calendar receipt must contain at least one open trade date"
        )
    request = _mapping(calendar_payload.get("request"), "calendar.request")
    request_start = _date_text(
        request.get("start_date"),
        "calendar.request.start_date",
    )
    request_end = _date_text(
        request.get("end_date"),
        "calendar.request.end_date",
    )
    if open_dates[0] != request_start or open_dates[-1] != request_end:
        raise CurrentRuleCohortError(
            "approved calendar request bounds must start and end on open dates"
        )

    copied_calendar_path = batch_dir / "calendar-receipt.json"
    _write_new_or_identical_json(
        copied_calendar_path,
        calendar_payload,
        governed_root=batch_dir,
    )

    source_receipt_refs: list[dict[str, str]] = []
    source_receipt_sha256s: list[str] = []
    source_index: dict[tuple[str, str, str, str, str], str] = {}
    for index, raw_path in enumerate(source_availability_receipt_paths):
        source_path = _trusted_existing_file(
            trusted_root=trusted_root,
            raw_path=raw_path,
            field_name=f"source_availability_receipt_paths[{index}]",
        )
        source_payload = _load_json_object(
            source_path,
            field_name=f"source_availability_receipt_paths[{index}]",
        )
        source_sha = _canonical_sha256(source_payload)
        receipt_index = _validate_source_availability_receipt(
            source_payload,
            evaluation=evaluation,
        )
        duplicate_keys = set(source_index).intersection(receipt_index)
        if duplicate_keys:
            raise CurrentRuleCohortError(
                "duplicate source availability key across persisted receipts"
            )
        source_index.update(receipt_index)
        source_receipt_sha256s.append(source_sha)
        copied_source_path = batch_dir / f"source-availability-{index + 1:02d}.json"
        _write_new_or_identical_json(
            copied_source_path,
            source_payload,
            governed_root=batch_dir,
        )
        source_receipt_refs.append(
            {
                "path": copied_source_path.relative_to(batch_dir).as_posix(),
                "sha256": source_sha,
            }
        )
    if not source_receipt_sha256s:
        raise CurrentRuleCohortError(
            "at least one persisted source availability receipt is required"
        )
    source_receipt_sha256s = sorted(source_receipt_sha256s)
    expected_governed_run_id = derive_expected_stock_analysis_current_rule_governed_run_id(
        calendar_receipt_sha256=calendar_sha,
        source_availability_receipt_sha256s=source_receipt_sha256s,
        frozen_version_tuple=version_tuple,
        evaluation_as_of_date=evaluation,
        open_dates=open_dates,
    )
    provided_governed_run_id = _text(governed_run_id, "governed_run_id")
    if provided_governed_run_id != expected_governed_run_id:
        raise CurrentRuleCohortError(
            "governed_run_id does not match the stable derived current-rule identity"
        )

    evidence_by_date = _normalize_date_evidence(date_evidence)
    if set(evidence_by_date) != set(open_dates):
        missing_dates = sorted(set(open_dates) - set(evidence_by_date))
        extra_dates = sorted(set(evidence_by_date) - set(open_dates))
        detail: list[str] = []
        if missing_dates:
            detail.append("missing: " + ", ".join(missing_dates))
        if extra_dates:
            detail.append("unexpected: " + ", ".join(extra_dates))
        raise CurrentRuleCohortError(
            "date_evidence must exactly cover approved open dates: " + "; ".join(detail)
        )

    plan = {
        "plan_kind": "stock_analysis_current_rule_cohort_plan",
        "governed_run_id": provided_governed_run_id,
        "control_count": CONTROL_COUNT,
        "minimum_completed_dates": MIN_COMPLETED_DATES,
        "minimum_matched_entries": MIN_MATCHED_ENTRIES,
        "decision_metric_basis": ALLOWED_DECISION_METRIC_BASIS,
        "evaluation_as_of_date": evaluation,
        "calendar_receipt_sha256": calendar_sha,
        "source_availability_receipt_sha256s": list(source_receipt_sha256s),
    }
    plan_digest = _canonical_sha256(plan)
    cohort_identifier = _text(cohort_id, "cohort_id")
    run_identifier = _text(run_id, "run_id")

    facts: list[dict[str, Any]] = []
    certificates: list[dict[str, Any]] = []
    zero_signal_refs: list[dict[str, str]] = []
    zero_signal_dir = batch_dir / "zero-signal"

    for trade_date in open_dates:
        evidence = evidence_by_date[trade_date]
        runner_result = _mapping(
            evidence.get("runner_result"),
            f"date_evidence[{trade_date}].runner_result",
        )
        raw_signal_facts = _list(
            evidence.get("signal_facts", []),
            f"date_evidence[{trade_date}].signal_facts",
        )
        if raw_signal_facts:
            signal_facts, certificate = _build_signal_date_artifacts(
                trade_date=trade_date,
                runner_result=runner_result,
                raw_signal_facts=raw_signal_facts,
                evaluation=evaluation,
                version_tuple=version_tuple,
                source_receipt_sha256s=tuple(source_receipt_sha256s),
                source_index=source_index,
            )
            facts.extend(signal_facts)
            certificates.append(certificate)
            continue

        zero_signal_certificate = build_current_rule_zero_signal_certificate(
            cohort_id=cohort_identifier,
            trade_date=trade_date,
            runner_result=runner_result,
            calendar_receipt=calendar_payload,
            frozen_version_tuple=version_tuple,
            plan_digest_sha256=plan_digest,
            run_id=run_identifier,
            created_at=created_at_dt,
        )
        zero_signal_path = zero_signal_dir / f"{trade_date}.json"
        _write_new_or_identical_json(
            zero_signal_path,
            zero_signal_certificate,
            governed_root=batch_dir,
        )
        zero_signal_sha = _sha256_text(
            zero_signal_certificate.get("payload_sha256"),
            f"zero_signal_certificate[{trade_date}].payload_sha256",
        )
        zero_signal_refs.append(
            {
                "path": zero_signal_path.relative_to(batch_dir).as_posix(),
                "sha256": zero_signal_sha,
            }
        )
        certificates.append(
            _build_zero_signal_date_certificate(
                trade_date=trade_date,
                version_tuple=version_tuple,
                source_receipt_sha256s=tuple(source_receipt_sha256s),
            )
        )

    facts.sort(key=lambda row: (str(row["signal_date"]), str(row["stock_code"]), str(row["signal_kind"])))
    certificates.sort(key=lambda row: str(row["trade_date"]))

    summary = _build_summary(facts=facts, certificates=certificates)
    idempotency_key = _canonical_sha256(
        {
            "target_database_path": str(target.resolve()),
            "plan_digest_sha256": plan_digest,
            "version_tuple": version_tuple,
            "calendar_receipt_sha256": calendar_sha,
            "source_availability_receipt_sha256s": list(source_receipt_sha256s),
            "control_count": CONTROL_COUNT,
        }
    )
    bundle_payload = {
        "schema_version": 1,
        "bundle_kind": BUNDLE_KIND,
        "cohort_id": cohort_identifier,
        "page_id": PAGE_ID,
        "cohort_mode": COHORT_MODE,
        "run_id": run_identifier,
        "idempotency_key": idempotency_key,
        "plan": plan,
        "plan_digest_sha256": plan_digest,
        "evaluation_as_of_date": evaluation,
        "version_tuple": version_tuple,
        "date_bounds": {
            "requested_start_date": request_start,
            "requested_end_date": request_end,
            "observed_start_date": request_start,
            "observed_end_date": request_end,
            "certified_start_date": request_start,
            "certified_end_date": request_end,
            "governed_era_start": request_start,
            "governed_era_end": request_end,
        },
        "source_lineage": {"mode": "persisted_receipts_only"},
        "artifacts": {
            "calendar_receipt": {
                "path": copied_calendar_path.relative_to(batch_dir).as_posix(),
                "sha256": calendar_sha,
            },
            "source_availability_receipts": source_receipt_refs,
            "zero_signal_certificates": zero_signal_refs,
        },
        "facts": facts,
        "date_certificates": certificates,
        "summary": summary,
    }
    bundle = _seal(bundle_payload, hash_field="canonical_bundle_sha256")
    bundle_path = batch_dir / "bundle.json"
    _write_new_or_identical_json(
        bundle_path,
        bundle,
        governed_root=batch_dir,
    )

    dry_run_receipt_path = batch_dir / "dry-run-receipt.json"
    dry_run_receipt = build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle_path,
        receipt_path=dry_run_receipt_path,
        created_at=created_at_text,
    )
    return {
        "bundle_path": str(bundle_path),
        "bundle_sha256": str(bundle["canonical_bundle_sha256"]),
        "dry_run_receipt_path": str(dry_run_receipt_path),
        "dry_run_receipt_sha256": str(dry_run_receipt["canonical_receipt_sha256"]),
        "governed_run_id": provided_governed_run_id,
        "calendar_receipt_sha256": calendar_sha,
        "source_availability_receipt_sha256s": list(source_receipt_sha256s),
        "zero_signal_certificate_paths": [
            str((batch_dir / ref["path"]).resolve()) for ref in zero_signal_refs
        ],
        "summary": summary,
    }


def _build_signal_date_artifacts(
    *,
    trade_date: str,
    runner_result: Mapping[str, Any],
    raw_signal_facts: Sequence[Any],
    evaluation: str,
    version_tuple: dict[str, Any],
    source_receipt_sha256s: tuple[str, ...],
    source_index: dict[tuple[str, str, str, str, str], str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _validate_signal_runner_result(
        trade_date=trade_date,
        runner_result=runner_result,
        version_tuple=version_tuple,
    )
    signal_rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for index, raw_fact in enumerate(raw_signal_facts):
        fact = _mapping(raw_fact, f"signal_facts[{trade_date}][{index}]")
        stock_code = _text(
            fact.get("stock_code"),
            f"signal_facts[{trade_date}][{index}].stock_code",
        )
        if stock_code in seen_codes:
            raise CurrentRuleCohortError(
                f"signal_facts[{trade_date}] contains duplicate stock_code {stock_code}"
            )
        seen_codes.add(stock_code)
        signal_rows.append(
            _normalize_signal_fact(
                trade_date=trade_date,
                stock_code=stock_code,
                fact=fact,
                evaluation=evaluation,
                version_tuple=version_tuple,
                source_receipt_sha256s=source_receipt_sha256s,
                source_index=source_index,
            )
        )

    runner_codes = _runner_candidate_codes(trade_date=trade_date, runner_result=runner_result)
    fact_codes = sorted(row["stock_code"] for row in signal_rows)
    if runner_codes != fact_codes:
        raise CurrentRuleCohortError(
            f"runner candidate keys do not match persisted facts for {trade_date}"
        )
    candidate_key_rows = [
        {
            "signal_date": trade_date,
            "signal_kind": "stock_candidate",
            "stock_code": stock_code,
        }
        for stock_code in fact_codes
    ]
    candidate_key_sha = _canonical_sha256(candidate_key_rows)
    row_count = len(signal_rows)
    certificate = {
        "trade_date": trade_date,
        "certificate_status": "completed_with_signals",
        "reason_code": "current_rule_fully_proven",
        "affects_completed_stats": True,
        "candidate_count": row_count,
        "executable_candidate_count": row_count,
        "t5_usable_count": row_count,
        "t20_usable_count": row_count,
        "matched_entry_count": row_count,
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
        "unsupported_source_count": 0,
        "proxy_only_evidence_count": 0,
        "blocking_gap_count": 0,
        "control_entry_proven_count": row_count * CONTROL_COUNT,
        "control_exit_proven_5d_count": row_count * CONTROL_COUNT,
        "control_exit_proven_20d_count": row_count * CONTROL_COUNT,
        "control_eval_proof": {
            "source_availability_receipt_sha256s": list(source_receipt_sha256s)
        },
        "source_coverage": {"strict": True, "fallback": False},
        "blocker_detail": {
            "runner_candidate_key_proof": {
                "candidate_keys": candidate_key_rows,
                "candidate_key_sha256": candidate_key_sha,
                "runner_candidate_count": len(runner_codes),
            }
        },
        **{field: version_tuple[field] for field in ROW_VERSION_FIELDS},
    }
    return signal_rows, certificate


def _normalize_signal_fact(
    *,
    trade_date: str,
    stock_code: str,
    fact: Mapping[str, Any],
    evaluation: str,
    version_tuple: dict[str, Any],
    source_receipt_sha256s: tuple[str, ...],
    source_index: dict[tuple[str, str, str, str, str], str],
) -> dict[str, Any]:
    signal_date = _date_text(fact.get("signal_date"), "signal_fact.signal_date")
    if signal_date != trade_date:
        raise CurrentRuleCohortError("signal_fact.signal_date must match trade_date")
    if _text(fact.get("signal_kind"), "signal_fact.signal_kind") != "stock_candidate":
        raise CurrentRuleCohortError("signal_fact.signal_kind must equal stock_candidate")
    if _text(fact.get("market_state"), "signal_fact.market_state") not in stock_candidate_policy_active_market_states(
        EXP3B_STOCK_CANDIDATE_POLICY
    ):
        raise CurrentRuleCohortError("signal_fact.market_state must remain policy-active")
    entry_date = _date_text(fact.get("entry_date"), "signal_fact.entry_date")
    exit_date_5d = _date_text(fact.get("exit_date_5d"), "signal_fact.exit_date_5d")
    exit_date_20d = _date_text(fact.get("exit_date_20d"), "signal_fact.exit_date_20d")
    if not (trade_date < entry_date <= exit_date_5d <= exit_date_20d <= evaluation):
        raise CurrentRuleCohortError("signal_fact dates violate PIT order")
    if fact.get("entry_executable") is not True:
        raise CurrentRuleCohortError("signal_fact.entry_executable must be true")
    if _text(fact.get("entry_price_kind"), "signal_fact.entry_price_kind") != "next_open":
        raise CurrentRuleCohortError("signal_fact.entry_price_kind must equal next_open")
    if _text(fact.get("price_adjustment_mode"), "signal_fact.price_adjustment_mode") != "adj_factor_ratio":
        raise CurrentRuleCohortError("signal_fact.price_adjustment_mode must equal adj_factor_ratio")
    if _text(fact.get("candidate_data_status"), "signal_fact.candidate_data_status") != "usable":
        raise CurrentRuleCohortError("signal_fact.candidate_data_status must equal usable")
    if _text(fact.get("execution_data_status"), "signal_fact.execution_data_status") != "usable":
        raise CurrentRuleCohortError("signal_fact.execution_data_status must equal usable")
    if _text(fact.get("matched_baseline_status"), "signal_fact.matched_baseline_status") != "usable":
        raise CurrentRuleCohortError("signal_fact.matched_baseline_status must equal usable")
    if fact.get("matched_baseline_control_count") not in (None, CONTROL_COUNT):
        raise CurrentRuleCohortError(
            "signal_fact.matched_baseline_control_count must equal 20 when present"
        )
    candidate_source_evidence = _mapping(
        fact.get("candidate_source_evidence"),
        "signal_fact.candidate_source_evidence",
    )
    _validate_exact_candidate_source_evidence(
        candidate_source_evidence,
        source_index=source_index,
        evaluation=evaluation,
        entry_date=entry_date,
        exit_date_5d=exit_date_5d,
        exit_date_20d=exit_date_20d,
    )

    control_pit_proof = _mapping(
        fact.get("control_pit_proof"),
        "signal_fact.control_pit_proof",
    )
    controls = _list(control_pit_proof.get("controls"), "signal_fact.controls")
    if len(controls) != CONTROL_COUNT:
        raise CurrentRuleCohortError("signal_fact must contain exactly 20 controls")

    normalized_controls: list[dict[str, Any]] = []
    control_return_5d_total = 0.0
    control_return_20d_total = 0.0
    seen_controls: set[str] = set()
    for index, raw_control in enumerate(controls):
        control = _mapping(raw_control, f"signal_fact.controls[{index}]")
        control_code = _text(
            control.get("control_stock_code"),
            f"signal_fact.controls[{index}].control_stock_code",
        )
        if control_code == stock_code or control_code in seen_controls:
            raise CurrentRuleCohortError(
                "control_stock_code values must be unique and distinct from candidate"
            )
        seen_controls.add(control_code)
        if control.get("control_entry_executable") is not True:
            raise CurrentRuleCohortError("control entry must be executable")
        if control.get("control_entry_usable") is not True:
            raise CurrentRuleCohortError("control entry must be usable")
        if control.get("control_return_5d_usable") is not True:
            raise CurrentRuleCohortError("control return 5d must be usable")
        if control.get("control_return_20d_usable") is not True:
            raise CurrentRuleCohortError("control return 20d must be usable")
        if any(
            control.get(field)
            for field in (
                "control_entry_failure_reason",
                "control_failure_reason_5d",
                "control_failure_reason_20d",
                "control_failure_reason",
            )
        ):
            raise CurrentRuleCohortError(
                "usable controls cannot carry failure reasons"
            )
        if _text(control.get("signal_date"), "control.signal_date") != trade_date:
            raise CurrentRuleCohortError("control.signal_date must match trade_date")
        if _text(control.get("signal_kind"), "control.signal_kind") != "stock_candidate":
            raise CurrentRuleCohortError("control.signal_kind must equal stock_candidate")
        if _text(control.get("candidate_stock_code"), "control.candidate_stock_code") != stock_code:
            raise CurrentRuleCohortError("control.candidate_stock_code mismatch")
        if _text(control.get("control_entry_price_kind"), "control.control_entry_price_kind") != "open":
            raise CurrentRuleCohortError("control entry price kind must equal open")
        if _text(control.get("formula_version"), "control.formula_version") != version_tuple["matched_baseline_formula_version"]:
            raise CurrentRuleCohortError("control formula_version must match frozen tuple")
        if _text(control.get("metric_basis"), "control.metric_basis") != ALLOWED_DECISION_METRIC_BASIS:
            raise CurrentRuleCohortError("control metric_basis mismatch")
        if _text(control.get("price_adjustment_mode"), "control.price_adjustment_mode") != "adj_factor_ratio":
            raise CurrentRuleCohortError("control price_adjustment_mode mismatch")
        if _date_text(control.get("evaluation_as_of_date"), "control.evaluation_as_of_date") != evaluation:
            raise CurrentRuleCohortError("control evaluation_as_of_date mismatch")
        control_entry_date = _date_text(
            control.get("control_entry_date"),
            "control.control_entry_date",
        )
        control_exit_date_5d = _date_text(
            control.get("control_exit_date_5d"),
            "control.control_exit_date_5d",
        )
        control_exit_date_20d = _date_text(
            control.get("control_exit_date_20d"),
            "control.control_exit_date_20d",
        )
        if not (
            trade_date
            < control_entry_date
            <= control_exit_date_5d
            <= control_exit_date_20d
            <= evaluation
        ):
            raise CurrentRuleCohortError("control dates violate PIT order")
        _validate_exact_control_source_evidence(
            control.get("source_evidence"),
            source_index=source_index,
            evaluation=evaluation,
            entry_date=control_entry_date,
            exit_date_5d=control_exit_date_5d,
            exit_date_20d=control_exit_date_20d,
        )
        control_return_5d = _finite_number(
            control.get("control_return_5d_net_adj"),
            "control.control_return_5d_net_adj",
        )
        control_return_20d = _finite_number(
            control.get("control_return_20d_net_adj"),
            "control.control_return_20d_net_adj",
        )
        control_return_5d_total += control_return_5d
        control_return_20d_total += control_return_20d
        normalized_control = dict(control)
        normalized_controls.append(normalized_control)

    candidate_return_5d = _finite_number(
        fact.get("return_5d_net_adj"),
        "signal_fact.return_5d_net_adj",
    )
    candidate_return_20d = _finite_number(
        fact.get("return_20d_net_adj"),
        "signal_fact.return_20d_net_adj",
    )
    mean_return_5d = control_return_5d_total / CONTROL_COUNT
    mean_return_20d = control_return_20d_total / CONTROL_COUNT
    matched_alpha_5d = candidate_return_5d - mean_return_5d
    matched_alpha_20d = candidate_return_20d - mean_return_20d

    normalized = {
        "signal_date": trade_date,
        "stock_code": stock_code,
        "stock_name": _text(fact.get("stock_name"), "signal_fact.stock_name"),
        "signal_kind": "stock_candidate",
        "candidate_rank": _positive_int(fact.get("candidate_rank"), "signal_fact.candidate_rank"),
        "market_state": _text(fact.get("market_state"), "signal_fact.market_state"),
        "entry_date": entry_date,
        "entry_price": _positive_number(fact.get("entry_price"), "signal_fact.entry_price"),
        "entry_price_kind": "next_open",
        "entry_executable": True,
        "exit_date_5d": exit_date_5d,
        "exit_price_5d": _positive_number(
            fact.get("exit_price_5d"),
            "signal_fact.exit_price_5d",
        ),
        "return_5d_net_adj": candidate_return_5d,
        "exit_date_20d": exit_date_20d,
        "exit_price_20d": _positive_number(
            fact.get("exit_price_20d"),
            "signal_fact.exit_price_20d",
        ),
        "return_20d_net_adj": candidate_return_20d,
        "price_adjustment_mode": "adj_factor_ratio",
        "candidate_data_status": "usable",
        "execution_data_status": "usable",
        "matched_baseline_status": "usable",
        "matched_baseline_control_count": CONTROL_COUNT,
        "matched_alpha_5d": matched_alpha_5d,
        "matched_alpha_20d": matched_alpha_20d,
        "control_eval_basis": ALLOWED_DECISION_METRIC_BASIS,
        "control_pit_proof": {
            "source_availability_receipt_sha256s": list(source_receipt_sha256s),
            "controls": normalized_controls,
        },
        "evidence": {
            **_mapping_or_empty(fact.get("evidence")),
            "candidate_source_evidence": candidate_source_evidence,
            "candidate_source_proven": True,
            "current_rule_certified": True,
            "matched_alpha_recomputed": True,
        },
        **{field: version_tuple[field] for field in ROW_VERSION_FIELDS},
    }
    return normalized


def _build_zero_signal_date_certificate(
    *,
    trade_date: str,
    version_tuple: dict[str, Any],
    source_receipt_sha256s: tuple[str, ...],
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
            "source_availability_receipt_sha256s": list(source_receipt_sha256s)
        },
        "source_coverage": {"strict": True, "fallback": False},
        "blocker_detail": {},
        **{field: version_tuple[field] for field in ROW_VERSION_FIELDS},
    }


def _build_summary(
    *,
    facts: Sequence[Mapping[str, Any]],
    certificates: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    completed_dates = len(certificates)
    completed_with_signals_dates = sum(
        1
        for row in certificates
        if row.get("certificate_status") == "completed_with_signals"
    )
    completed_no_signal_dates = sum(
        1
        for row in certificates
        if row.get("certificate_status") == CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS
    )
    matched_entry_count = len(facts)
    return {
        "completed_dates": completed_dates,
        "completed_with_signals_dates": completed_with_signals_dates,
        "completed_no_signal_dates": completed_no_signal_dates,
        "pending_tail_dates": 0,
        "blocking_pending_dates": 0,
        "unsupported_dates": 0,
        "proxy_only_dates": 0,
        "matched_entry_count": matched_entry_count,
        "t5_usable_count": matched_entry_count,
        "t20_usable_count": matched_entry_count,
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
    }


def _validate_signal_runner_result(
    *,
    trade_date: str,
    runner_result: Mapping[str, Any],
    version_tuple: Mapping[str, Any],
) -> None:
    status = _text(runner_result.get("status"), "runner_result.status")
    if status != "selection_completed_with_signals":
        raise CurrentRuleCohortError(
            "signal dates require runner_result.status=selection_completed_with_signals"
        )
    if (
        _date_text(
            runner_result.get("requested_as_of_date"),
            "runner_result.requested_as_of_date",
        )
        != trade_date
    ):
        raise CurrentRuleCohortError(
            "runner_result.requested_as_of_date must match trade_date"
        )
    if (
        _date_text(
            runner_result.get("resolved_as_of_date"),
            "runner_result.resolved_as_of_date",
        )
        != trade_date
    ):
        raise CurrentRuleCohortError(
            "runner_result.resolved_as_of_date must match trade_date"
        )
    if runner_result.get("requested_matches_resolved") is not True:
        raise CurrentRuleCohortError(
            "runner_result.requested_matches_resolved must be true"
        )
    if _text(runner_result.get("selection_policy"), "runner_result.selection_policy") != EXP3B_STOCK_CANDIDATE_POLICY:
        raise CurrentRuleCohortError(
            "runner_result.selection_policy must equal exp3b"
        )
    if (
        _text(
            runner_result.get("stock_candidate_formula_version"),
            "runner_result.stock_candidate_formula_version",
        )
        != version_tuple["stock_candidate_selection_formula_version"]
    ):
        raise CurrentRuleCohortError(
            "runner_result stock candidate formula version mismatch"
        )
    if runner_result.get("rule_tuple_matches") is not True:
        raise CurrentRuleCohortError("runner_result.rule_tuple_matches must be true")
    market_state = _text(runner_result.get("market_state"), "runner_result.market_state")
    if market_state not in stock_candidate_policy_active_market_states(
        EXP3B_STOCK_CANDIDATE_POLICY
    ):
        raise CurrentRuleCohortError(
            "runner_result.market_state must remain policy-active"
        )
    if _list_length(runner_result.get("future_business_date_violations")) != 0:
        raise CurrentRuleCohortError(
            "future business-date violations block certification"
        )
    if _list_length(runner_result.get("future_availability_violations")) != 0:
        raise CurrentRuleCohortError(
            "future availability violations block certification"
        )
    if _string_list(runner_result.get("blockers")):
        raise CurrentRuleCohortError("runner_result blockers prevent certification")
    if _optional_text(runner_result.get("stock_candidate_block_reason")) is not None:
        raise CurrentRuleCohortError(
            "runner_result.stock_candidate_block_reason must be empty"
        )
    candidate_codes = _runner_candidate_codes(
        trade_date=trade_date,
        runner_result=runner_result,
    )
    candidate_count = _non_negative_int(
        runner_result.get("candidate_count"),
        "runner_result.candidate_count",
    )
    candidate_item_count = _non_negative_int(
        runner_result.get("candidate_item_count"),
        "runner_result.candidate_item_count",
    )
    accepted_candidate_count = _non_negative_int(
        runner_result.get("accepted_candidate_count"),
        "runner_result.accepted_candidate_count",
    )
    expected_count = len(candidate_codes)
    if candidate_count != expected_count or candidate_item_count != expected_count:
        raise CurrentRuleCohortError(
            "runner_result candidate counts must equal the candidate key set"
        )
    if accepted_candidate_count != expected_count:
        raise CurrentRuleCohortError(
            "runner_result.accepted_candidate_count must equal the candidate key set"
        )
    if runner_result.get("candidate_count_matches_items") is not True:
        raise CurrentRuleCohortError(
            "runner_result.candidate_count_matches_items must be true"
        )


def _runner_candidate_codes(
    *,
    trade_date: str,
    runner_result: Mapping[str, Any],
) -> list[str]:
    accepted_codes = _string_list(runner_result.get("accepted_candidate_codes"))
    candidate_codes = _string_list(runner_result.get("candidate_codes"))
    duplicate_codes = _string_list(runner_result.get("duplicate_candidate_codes"))
    if duplicate_codes:
        raise CurrentRuleCohortError(
            f"runner_result duplicate candidate codes are not certifiable for {trade_date}"
        )
    full_set = accepted_codes or candidate_codes
    if not full_set:
        raise CurrentRuleCohortError(
            f"signal date runner_result lacks accepted candidate codes for {trade_date}"
        )
    unique_codes = sorted(set(full_set))
    if len(unique_codes) != len(full_set):
        raise CurrentRuleCohortError(
            f"runner_result candidate code set is not unique for {trade_date}"
        )
    if candidate_codes and sorted(candidate_codes) != unique_codes:
        raise CurrentRuleCohortError(
            f"runner_result.candidate_codes must equal the unique candidate key set for {trade_date}"
        )
    if accepted_codes and sorted(accepted_codes) != unique_codes:
        raise CurrentRuleCohortError(
            f"runner_result.accepted_candidate_codes must equal the unique candidate key set for {trade_date}"
        )
    unique_from_payload = sorted(set(_string_list(runner_result.get("unique_candidate_codes"))))
    if unique_from_payload and unique_from_payload != unique_codes:
        raise CurrentRuleCohortError(
            f"runner_result.unique_candidate_codes mismatch for {trade_date}"
        )
    return unique_codes


def _normalize_date_evidence(
    date_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    mapping: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(date_evidence):
        evidence = _mapping(raw, f"date_evidence[{index}]")
        trade_date = _date_text(
            evidence.get("trade_date"),
            f"date_evidence[{index}].trade_date",
        )
        if trade_date in mapping:
            raise CurrentRuleCohortError(
                f"duplicate date_evidence trade_date {trade_date}"
            )
        if evidence.get("status") != "ready":
            raise CurrentRuleCohortError(
                f"date_evidence[{trade_date}].status must equal ready"
            )
        blockers = evidence.get("blockers")
        if not isinstance(blockers, list):
            raise CurrentRuleCohortError(
                f"date_evidence[{trade_date}].blockers must be an explicit array"
            )
        if blockers:
            raise CurrentRuleCohortError(
                f"date_evidence[{trade_date}].blockers must be empty"
            )
        mapping[trade_date] = evidence
    return mapping


def _open_calendar_dates(calendar_receipt: Mapping[str, Any]) -> list[str]:
    calendar_rows = _list(calendar_receipt.get("calendar_rows"), "calendar_rows")
    open_dates = [
        _date_text(row.get("cal_date"), "calendar_rows.cal_date")
        for raw in calendar_rows
        for row in [_mapping(raw, "calendar_row")]
        if row.get("is_open") == 1
    ]
    return sorted(open_dates)


def _validate_exact_candidate_source_evidence(
    value: Any,
    *,
    source_index: dict[tuple[str, str, str, str, str], str],
    evaluation: str,
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
) -> None:
    _validate_exact_pit_source_evidence(
        value,
        source_index=source_index,
        evaluation=evaluation,
        field_label="candidate source evidence",
        entry_date=entry_date,
        exit_date_5d=exit_date_5d,
        exit_date_20d=exit_date_20d,
    )


def _validate_exact_control_source_evidence(
    value: Any,
    *,
    source_index: dict[tuple[str, str, str, str, str], str],
    evaluation: str,
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
) -> None:
    _validate_exact_pit_source_evidence(
        value,
        source_index=source_index,
        evaluation=evaluation,
        field_label="control source evidence",
        entry_date=entry_date,
        exit_date_5d=exit_date_5d,
        exit_date_20d=exit_date_20d,
    )


def _validate_exact_pit_source_evidence(
    value: Any,
    *,
    source_index: dict[tuple[str, str, str, str, str], str],
    evaluation: str,
    field_label: str,
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
) -> None:
    evidence = _mapping(value, field_label)
    if set(evidence) != {"observation", "adjustment_factor", "limit_price"}:
        raise CurrentRuleCohortError(
            f"{field_label} must contain observation, adjustment_factor and limit_price"
        )
    for group_name in ("observation", "adjustment_factor"):
        group = _mapping(evidence.get(group_name), f"{field_label}.{group_name}")
        _text(group.get("table"), f"{field_label}.{group_name}.table")
        for point in ("entry", "exit_5d", "exit_20d"):
            leaf = _mapping(
                group.get(point),
                f"{field_label}.{group_name}.{point}",
            )
            proven = _validate_pit_source_evidence(
                leaf,
                source_index=source_index,
                evaluation=evaluation,
                inherited_table=str(group["table"]),
                field_label=field_label,
            )
            if proven != 1:
                raise CurrentRuleCohortError(
                    f"each {field_label} leaf must contain exactly one availability record"
                )
        group_proven = _validate_pit_source_evidence(
            group,
            source_index=source_index,
            evaluation=evaluation,
            field_label=field_label,
        )
        if group_proven != 3:
            raise CurrentRuleCohortError(
                f"{field_label} must contain exactly entry/T5/T20 availability"
            )
    _validate_v4_limit_price_evidence(
        evidence["limit_price"],
        observation=_mapping(evidence["observation"], f"{field_label}.observation"),
        source_index=source_index,
        evaluation=evaluation,
        entry_date=entry_date,
        exit_date_5d=exit_date_5d,
        exit_date_20d=exit_date_20d,
        field_label=field_label,
    )


def _validate_pit_source_evidence(
    value: Any,
    *,
    source_index: dict[tuple[str, str, str, str, str], str],
    evaluation: str,
    field_label: str,
    inherited_table: str | None = None,
) -> int:
    proven = 0
    if isinstance(value, dict):
        table = str(value.get("table") or inherited_table or "").strip() or None
        if "availability_status" in value:
            if value.get("availability_status") != "available":
                raise CurrentRuleCohortError(
                    f"{field_label} availability is not available"
                )
            if table is None:
                raise CurrentRuleCohortError(f"{field_label} table is missing")
            key = (
                table,
                _text(value.get("source_version"), f"{field_label} source_version"),
                str(value.get("vendor_version") or ""),
                str(value.get("rule_version") or ""),
                _text(value.get("run_id"), f"{field_label} run_id"),
            )
            available_at = _date_text(
                value.get("available_at"),
                f"{field_label} available_at",
            )
            if available_at > evaluation or source_index.get(key) != available_at:
                raise CurrentRuleCohortError(
                    f"{field_label} is not attested by persisted availability receipt"
                )
            proven += 1
        for nested in value.values():
            proven += _validate_pit_source_evidence(
                nested,
                source_index=source_index,
                evaluation=evaluation,
                field_label=field_label,
                inherited_table=table,
            )
    elif isinstance(value, list):
        for nested in value:
            proven += _validate_pit_source_evidence(
                nested,
                source_index=source_index,
                evaluation=evaluation,
                field_label=field_label,
                inherited_table=inherited_table,
            )
    return proven


def _prepare_output_directory(output_root: Path, *, batch_name: str) -> Path:
    normalized_batch_name = _text(batch_name, "batch_name")
    candidate = _assert_governed_output_path(
        governed_root=output_root,
        candidate=output_root / normalized_batch_name,
        field_name="batch_name",
    )
    candidate.mkdir(parents=True, exist_ok=True)
    candidate = _assert_governed_output_path(
        governed_root=output_root,
        candidate=candidate,
        field_name="batch_name",
    )
    return candidate


def _trusted_existing_file(
    *,
    trusted_root: Path,
    raw_path: str | Path,
    field_name: str,
) -> Path:
    candidate = Path(raw_path)
    joined = candidate if candidate.is_absolute() else trusted_root / candidate
    normalized = _absolute_without_resolve(joined)
    _assert_within_root(root=trusted_root, candidate=normalized, field_name=field_name)
    _assert_no_symlink_in_raw_path(normalized, field_name=field_name)
    if not normalized.is_file():
        raise CurrentRuleCohortError(f"{field_name} must be an existing file")
    return normalized


def _existing_directory(path: str | Path, *, field_name: str) -> Path:
    normalized = _absolute_without_resolve(path)
    _assert_no_symlink_in_raw_path(normalized, field_name=field_name)
    if not normalized.is_dir():
        raise CurrentRuleCohortError(f"{field_name} must be an existing directory")
    return normalized


def _existing_file(path: str | Path, *, field_name: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise CurrentRuleCohortError(f"{field_name} must be an existing file")
    return resolved


def _load_json_object(path: Path, *, field_name: str) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CurrentRuleCohortError(f"{field_name} could not be inspected") from exc
    if size > MAX_JSON_INPUT_BYTES:
        raise CurrentRuleCohortError(
            f"{field_name} exceeds max JSON input size of {MAX_JSON_INPUT_BYTES} bytes"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentRuleCohortError(f"{field_name} must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise CurrentRuleCohortError(f"{field_name} must contain a JSON object")
    return payload


def _freeze_version_tuple(
    frozen_version_tuple: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _mapping(frozen_version_tuple, "frozen_version_tuple")
    normalized: dict[str, Any] = {}
    missing = [field for field in REQUIRED_VERSION_TUPLE_FIELDS if field not in payload]
    if missing:
        raise CurrentRuleCohortError(
            "frozen_version_tuple missing required fields: " + ", ".join(missing)
        )
    for field in REQUIRED_VERSION_TUPLE_FIELDS:
        value = payload[field]
        if field in {"strict_coverage", "fallback_covered"}:
            if not isinstance(value, bool):
                raise CurrentRuleCohortError(
                    f"frozen_version_tuple.{field} must be a boolean"
                )
            normalized[field] = value
        else:
            normalized[field] = _text(
                value,
                f"frozen_version_tuple.{field}",
            )
    if normalized["stock_candidate_selection_policy"] != EXP3B_STOCK_CANDIDATE_POLICY:
        raise CurrentRuleCohortError(
            "frozen_version_tuple.stock_candidate_selection_policy must equal exp3b"
        )
    if normalized["decision_metric_basis"] != ALLOWED_DECISION_METRIC_BASIS:
        raise CurrentRuleCohortError(
            "frozen_version_tuple.decision_metric_basis must equal net_next_open_adj"
        )
    if normalized["coverage_authority_mode"] != CURRENT_RULE_COVERAGE_AUTHORITY_MODE:
        raise CurrentRuleCohortError(
            "frozen_version_tuple.coverage_authority_mode mismatch"
        )
    if normalized["strict_coverage"] is not True:
        raise CurrentRuleCohortError(
            "frozen_version_tuple.strict_coverage must be true"
        )
    if normalized["fallback_covered"] is not False:
        raise CurrentRuleCohortError(
            "frozen_version_tuple.fallback_covered must be false"
        )
    return normalized


def _write_new_or_identical_json(
    path: Path,
    payload: Mapping[str, Any],
    *,
    governed_root: Path,
) -> None:
    normalized_path = _assert_governed_output_path(
        governed_root=governed_root,
        candidate=path,
        field_name="output_path",
    )
    normalized_parent = _assert_governed_output_path(
        governed_root=governed_root,
        candidate=normalized_path.parent,
        field_name="output_path.parent",
    )
    normalized_parent.mkdir(parents=True, exist_ok=True)
    normalized_parent = _assert_governed_output_path(
        governed_root=governed_root,
        candidate=normalized_parent,
        field_name="output_path.parent",
    )
    content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if normalized_path.exists():
        normalized_path = _assert_governed_output_path(
            governed_root=governed_root,
            candidate=normalized_path,
            field_name="output_path",
        )
        if normalized_path.read_text(encoding="utf-8") != content:
            raise CurrentRuleCohortError(
                f"output path already exists with different content: {normalized_path}"
            )
        return
    temporary = _assert_governed_output_path(
        governed_root=governed_root,
        candidate=normalized_path.with_name(f".{normalized_path.name}.{uuid.uuid4().hex}.tmp"),
        field_name="output_path.temporary",
    )
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        normalized_parent = _assert_governed_output_path(
            governed_root=governed_root,
            candidate=normalized_parent,
            field_name="output_path.parent",
        )
        normalized_path = _assert_governed_output_path(
            governed_root=governed_root,
            candidate=normalized_path,
            field_name="output_path",
        )
        temporary = _assert_governed_output_path(
            governed_root=governed_root,
            candidate=temporary,
            field_name="output_path.temporary",
        )
        try:
            os.link(temporary, normalized_path)
        except FileExistsError:
            normalized_path = _assert_governed_output_path(
                governed_root=governed_root,
                candidate=normalized_path,
                field_name="output_path",
            )
            if normalized_path.read_text(encoding="utf-8") != content:
                raise CurrentRuleCohortError(
                    f"output path already exists with different content: {normalized_path}"
                )
    finally:
        temporary = _assert_governed_output_path(
            governed_root=governed_root,
            candidate=temporary,
            field_name="output_path.temporary",
        )
        if temporary.exists():
            temporary = _assert_governed_output_path(
                governed_root=governed_root,
                candidate=temporary,
                field_name="output_path.temporary",
            )
            temporary.unlink()


def _seal(payload: Mapping[str, Any], *, hash_field: str) -> dict[str, Any]:
    sealed = dict(payload)
    sealed[hash_field] = _canonical_sha256(sealed)
    return sealed


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest().upper()


def _assert_within_root(*, root: Path, candidate: Path, field_name: str) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CurrentRuleCohortError(
            f"{field_name} must stay within its governed root"
        ) from exc


def _absolute_without_resolve(path: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(path))))


def _assert_governed_output_path(
    *,
    governed_root: Path,
    candidate: str | Path,
    field_name: str,
) -> Path:
    normalized_root = _absolute_without_resolve(governed_root)
    normalized_candidate = _absolute_without_resolve(candidate)
    _assert_within_root(
        root=normalized_root,
        candidate=normalized_candidate,
        field_name=field_name,
    )
    _assert_no_symlink_in_raw_path(normalized_candidate, field_name=field_name)
    return normalized_candidate


def _assert_no_symlink_in_raw_path(path: Path, *, field_name: str) -> None:
    current: Path | None = None
    for part in path.parts:
        current = Path(part) if current is None else current / part
        if current.exists() and _is_forbidden_link_component(current):
            raise CurrentRuleCohortError(
                f"{field_name} contains forbidden symlink/junction component: {current}"
            )


def _is_forbidden_link_component(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            return bool(is_junction())
        except OSError:
            return False
    return False


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CurrentRuleCohortError(f"{field_name} must be an object")
    return dict(value)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    raise CurrentRuleCohortError("evidence must be an object when present")


def _list(value: Any, field_name: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    raise CurrentRuleCohortError(f"{field_name} must be an array")


def _text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CurrentRuleCohortError(f"{field_name} is required")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _date_text(value: Any, field_name: str) -> str:
    text = _text(value, field_name)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise CurrentRuleCohortError(f"{field_name} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise CurrentRuleCohortError(f"{field_name} must be strict YYYY-MM-DD")
    return text


def _datetime_text(value: Any, *, field_name: str) -> str:
    text = _text(value, field_name)
    _parse_datetime(text, field_name=field_name)
    return text


def _parse_datetime(value: str, *, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CurrentRuleCohortError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CurrentRuleCohortError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _sha256_text(value: Any, field_name: str) -> str:
    text = _text(value, field_name).upper()
    if len(text) != 64 or any(ch not in "0123456789ABCDEF" for ch in text):
        raise CurrentRuleCohortError(f"{field_name} must be an uppercase SHA256")
    return text


def _list_length(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value)
    raise CurrentRuleCohortError("list-like evidence must be an array when present")


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CurrentRuleCohortError("expected an array of strings")
    result = [str(item).strip() for item in value if str(item).strip()]
    return result


def _non_negative_int(value: Any, field_name: str) -> int:
    if value is None or isinstance(value, bool):
        raise CurrentRuleCohortError(f"{field_name} must be a non-negative integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise CurrentRuleCohortError(
            f"{field_name} must be a non-negative integer"
        ) from exc
    if number < 0:
        raise CurrentRuleCohortError(f"{field_name} must be a non-negative integer")
    return number


def _positive_int(value: Any, field_name: str) -> int:
    number = _non_negative_int(value, field_name)
    if number <= 0:
        raise CurrentRuleCohortError(f"{field_name} must be positive")
    return number


def _finite_number(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CurrentRuleCohortError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number):
        raise CurrentRuleCohortError(f"{field_name} must be finite")
    return number


def _positive_number(value: Any, field_name: str) -> float:
    number = _finite_number(value, field_name)
    if number <= 0:
        raise CurrentRuleCohortError(f"{field_name} must be positive")
    return number
