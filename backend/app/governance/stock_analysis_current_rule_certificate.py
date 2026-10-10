from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any

from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
    stock_candidate_policy_active_market_states,
)
from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    APPROVED_AUTHORITY_STATUS,
    validate_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    EXCHANGE as CALENDAR_EXCHANGE,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    SEMANTICS as CALENDAR_SEMANTICS,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    SOURCE_ID as CALENDAR_SOURCE_ID,
)

CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_SCHEMA_VERSION = (
    "stock-analysis-current-rule-zero-signal-certificate-v1"
)
CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS = "completed_no_strategy_signals"
CURRENT_RULE_RUNNER_ZERO_SIGNAL_STATUS = "selection_completed_no_signals"
CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_REASON = "policy_active_zero_signal"
CURRENT_RULE_COVERAGE_AUTHORITY_MODE = (
    f"{CALENDAR_SOURCE_ID}|{CALENDAR_SEMANTICS}"
)
ALLOWED_DECISION_METRIC_BASIS = "net_next_open_adj"
REQUIRED_VERSION_TUPLE_FIELDS = (
    "candidate_rule_version",
    "stock_candidate_selection_formula_version",
    "candidate_outcome_formula_version",
    "execution_formula_version",
    "matched_baseline_formula_version",
    "market_gate_rule_version",
    "signal_confluence_rule_version",
    "macro_formula_version",
    "candidate_source_version",
    "execution_source_version",
    "matched_baseline_source_version",
    "macro_source_version",
    "theme_overlay_fingerprint",
    "choice_catalog_fingerprint",
    "stock_candidate_selection_policy",
    "decision_metric_basis",
    "coverage_authority_mode",
    "strict_coverage",
    "fallback_covered",
)
SELF_HASH_FIELDS = frozenset({"payload_sha256"})


class CurrentRuleCertificateError(ValueError):
    """Raised when a zero-signal date certificate cannot be certified."""


def build_current_rule_zero_signal_certificate(
    *,
    cohort_id: str,
    trade_date: str,
    runner_result: Mapping[str, Any],
    calendar_receipt: Mapping[str, Any],
    frozen_version_tuple: Mapping[str, Any],
    plan_digest_sha256: str,
    run_id: str,
    created_at: datetime,
) -> dict[str, Any]:
    certificate_trade_date = _required_date_text("trade_date", trade_date)
    certificate_created_at = _utc_datetime_text("created_at", created_at)
    certificate_cohort_id = _required_text("cohort_id", cohort_id)
    certificate_run_id = _required_text("run_id", run_id)
    normalized_plan_digest = _normalized_sha256(
        "plan_digest_sha256",
        plan_digest_sha256,
    )
    version_tuple = _freeze_version_tuple(frozen_version_tuple)
    runner_summary = _validate_runner_result(
        runner_result=runner_result,
        trade_date=certificate_trade_date,
        version_tuple=version_tuple,
    )
    calendar_summary, calendar_receipt_sha256 = _validate_calendar_receipt(
        calendar_receipt=calendar_receipt,
        trade_date=certificate_trade_date,
        expected_coverage_authority_mode=str(version_tuple["coverage_authority_mode"]),
    )

    content = {
        "schema_version": CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_SCHEMA_VERSION,
        "cohort_id": certificate_cohort_id,
        "trade_date": certificate_trade_date,
        "status": CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS,
        "reason_code": CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_REASON,
        "candidate_count": 0,
        "run_id": certificate_run_id,
        "plan_digest_sha256": normalized_plan_digest,
        "calendar_receipt_sha256": calendar_receipt_sha256,
        "version_tuple": version_tuple,
        "source_evidence": {
            "runner": runner_summary,
            "calendar": calendar_summary,
        },
        "created_at": certificate_created_at,
    }
    certificate = {
        **content,
        "payload_sha256": _canonical_hash(content),
    }
    validate_current_rule_zero_signal_certificate(certificate)
    return certificate


def validate_current_rule_zero_signal_certificate(
    certificate: Mapping[str, Any],
) -> None:
    payload = dict(_mapping("certificate", certificate))
    observed_hash = _normalized_sha256("payload_sha256", payload.get("payload_sha256"))
    content = {
        key: value
        for key, value in payload.items()
        if key not in SELF_HASH_FIELDS
    }
    expected_hash = _canonical_hash(content)
    if observed_hash != expected_hash:
        raise CurrentRuleCertificateError("certificate payload_sha256 mismatch")
    if (
        _required_text("schema_version", payload.get("schema_version"))
        != CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_SCHEMA_VERSION
    ):
        raise CurrentRuleCertificateError(
            "certificate schema_version must match the current zero-signal certificate schema"
        )
    certificate_cohort_id = _required_text("cohort_id", payload.get("cohort_id"))
    certificate_trade_date = _required_date_text("trade_date", payload.get("trade_date"))
    certificate_run_id = _required_text("run_id", payload.get("run_id"))
    _required_datetime_text("created_at", payload.get("created_at"))
    _normalized_sha256("plan_digest_sha256", payload.get("plan_digest_sha256"))
    _normalized_sha256(
        "calendar_receipt_sha256",
        payload.get("calendar_receipt_sha256"),
    )
    if _required_text("status", payload.get("status")) != CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS:
        raise CurrentRuleCertificateError("certificate status must be completed_no_strategy_signals")
    if (
        _required_text("reason_code", payload.get("reason_code"))
        != CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_REASON
    ):
        raise CurrentRuleCertificateError("certificate reason_code must be policy_active_zero_signal")
    if _required_non_negative_int("candidate_count", payload.get("candidate_count")) != 0:
        raise CurrentRuleCertificateError("certificate candidate_count must equal 0")
    version_tuple = _freeze_version_tuple(
        _mapping("version_tuple", payload.get("version_tuple"))
    )
    source_evidence = _mapping("source_evidence", payload.get("source_evidence"))
    runner_summary = _validate_runner_summary(
        runner_summary=_mapping("source_evidence.runner", source_evidence.get("runner")),
        trade_date=certificate_trade_date,
        version_tuple=version_tuple,
    )
    calendar_summary = _validate_calendar_summary(
        calendar_summary=_mapping(
            "source_evidence.calendar",
            source_evidence.get("calendar"),
        ),
        trade_date=certificate_trade_date,
        version_tuple=version_tuple,
    )
    if runner_summary["trade_date"] != calendar_summary["trade_date"]:
        raise CurrentRuleCertificateError(
            "runner and calendar source evidence must agree on trade_date"
        )
    if not certificate_cohort_id or not certificate_run_id:
        raise CurrentRuleCertificateError("certificate cohort_id and run_id must be non-empty")


def canonical_current_rule_zero_signal_certificate_bytes(
    certificate: Mapping[str, Any],
) -> bytes:
    validate_current_rule_zero_signal_certificate(certificate)
    return _canonical_json_bytes(certificate)


def _validate_runner_result(
    *,
    runner_result: Mapping[str, Any],
    trade_date: str,
    version_tuple: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _mapping("runner_result", runner_result)
    status = _required_text("runner_result.status", payload.get("status"))
    if status == "selection_policy_inactive":
        raise CurrentRuleCertificateError("policy-inactive dates cannot certify as zero-signal")
    if status == "selection_completed_with_signals":
        raise CurrentRuleCertificateError(
            "signal dates require execution and matched-baseline proof before certification"
        )
    if status != "selection_completed_no_signals":
        raise CurrentRuleCertificateError(
            "runner_result.status must equal selection_completed_no_signals"
        )

    status_reason = _required_text("runner_result.status_reason", payload.get("status_reason"))
    if status_reason != CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_REASON:
        raise CurrentRuleCertificateError(
            "runner_result.status_reason must equal policy_active_zero_signal"
        )

    requested_as_of_date = _required_date_text(
        "runner_result.requested_as_of_date",
        payload.get("requested_as_of_date"),
    )
    resolved_as_of_date = _required_date_text(
        "runner_result.resolved_as_of_date",
        payload.get("resolved_as_of_date"),
    )
    if requested_as_of_date != trade_date or resolved_as_of_date != trade_date:
        raise CurrentRuleCertificateError(
            "runner_result requested/resolved date must exactly match certificate trade_date"
        )
    if payload.get("requested_matches_resolved") is not True:
        raise CurrentRuleCertificateError("runner_result.requested_matches_resolved must be true")

    market_state = _required_text("runner_result.market_state", payload.get("market_state"))
    active_states = stock_candidate_policy_active_market_states(EXP3B_STOCK_CANDIDATE_POLICY)
    if market_state not in active_states:
        raise CurrentRuleCertificateError("runner_result market_state is policy-inactive for exp3b")

    selection_policy = _required_text(
        "runner_result.selection_policy",
        payload.get("selection_policy"),
    )
    if selection_policy != EXP3B_STOCK_CANDIDATE_POLICY:
        raise CurrentRuleCertificateError("runner_result.selection_policy must equal exp3b")
    if str(version_tuple["stock_candidate_selection_policy"]) != selection_policy:
        raise CurrentRuleCertificateError(
            "runner_result.selection_policy must match frozen version tuple"
        )

    stock_candidate_formula_version = _required_text(
        "runner_result.stock_candidate_formula_version",
        payload.get("stock_candidate_formula_version"),
    )
    if stock_candidate_formula_version != STOCK_CANDIDATE_FORMULA_VERSION:
        raise CurrentRuleCertificateError(
            "runner_result.stock_candidate_formula_version must equal the v7 current-rule bundle"
        )
    if (
        str(version_tuple["stock_candidate_selection_formula_version"])
        != stock_candidate_formula_version
    ):
        raise CurrentRuleCertificateError(
            "runner_result stock candidate formula version must match frozen version tuple"
        )

    if payload.get("rule_tuple_matches") is not True:
        raise CurrentRuleCertificateError("runner_result.rule_tuple_matches must be true")

    candidate_count = _required_non_negative_int(
        "runner_result.candidate_count",
        payload.get("candidate_count"),
    )
    candidate_item_count = _required_non_negative_int(
        "runner_result.candidate_item_count",
        payload.get("candidate_item_count"),
    )
    accepted_candidate_count = _required_non_negative_int(
        "runner_result.accepted_candidate_count",
        payload.get("accepted_candidate_count"),
    )
    if candidate_count != 0 or candidate_item_count != 0 or accepted_candidate_count != 0:
        raise CurrentRuleCertificateError(
            "zero-signal certification requires zero candidate_count, candidate_item_count, and accepted_candidate_count"
        )
    if payload.get("candidate_count_matches_items") is not True:
        raise CurrentRuleCertificateError("runner_result.candidate_count_matches_items must be true")

    for field_name in (
        "candidate_codes",
        "accepted_candidate_codes",
        "unique_candidate_codes",
        "duplicate_candidate_codes",
    ):
        if _string_list(payload.get(field_name)):
            raise CurrentRuleCertificateError(f"runner_result.{field_name} must be empty")

    if _optional_text(payload.get("stock_candidate_block_reason")) is not None:
        raise CurrentRuleCertificateError("runner_result stock_candidate_block_reason must be empty")
    future_business_date_violations = _list_length(
        "runner_result.future_business_date_violations",
        payload.get("future_business_date_violations"),
    )
    future_availability_violations = _list_length(
        "runner_result.future_availability_violations",
        payload.get("future_availability_violations"),
    )
    if future_business_date_violations or future_availability_violations:
        raise CurrentRuleCertificateError(
            "future-dated inputs block zero-signal certification"
        )
    blockers = _string_list(payload.get("blockers"))
    if blockers:
        raise CurrentRuleCertificateError(
            "runner_result blockers prevent zero-signal certification"
        )

    return {
        "trade_date": trade_date,
        "status": status,
        "status_reason": status_reason,
        "requested_as_of_date": requested_as_of_date,
        "resolved_as_of_date": resolved_as_of_date,
        "market_state": market_state,
        "selection_policy": selection_policy,
        "stock_candidate_formula_version": stock_candidate_formula_version,
        "candidate_count": candidate_count,
        "candidate_item_count": candidate_item_count,
        "accepted_candidate_count": accepted_candidate_count,
        "future_business_date_violation_count": future_business_date_violations,
        "future_availability_violation_count": future_availability_violations,
    }


def _validate_runner_summary(
    *,
    runner_summary: Mapping[str, Any],
    trade_date: str,
    version_tuple: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _mapping("source_evidence.runner", runner_summary)
    if _required_date_text("source_evidence.runner.trade_date", payload.get("trade_date")) != trade_date:
        raise CurrentRuleCertificateError(
            "runner source evidence trade_date must match certificate trade_date"
        )
    if (
        _required_date_text(
            "source_evidence.runner.requested_as_of_date",
            payload.get("requested_as_of_date"),
        )
        != trade_date
    ):
        raise CurrentRuleCertificateError(
            "runner source evidence requested_as_of_date must match certificate trade_date"
        )
    if (
        _required_date_text(
            "source_evidence.runner.resolved_as_of_date",
            payload.get("resolved_as_of_date"),
        )
        != trade_date
    ):
        raise CurrentRuleCertificateError(
            "runner source evidence resolved_as_of_date must match certificate trade_date"
        )
    if (
        _required_text("source_evidence.runner.status", payload.get("status"))
        != CURRENT_RULE_RUNNER_ZERO_SIGNAL_STATUS
    ):
        raise CurrentRuleCertificateError(
            "runner source evidence status must be selection_completed_no_signals"
        )
    if (
        _required_text("source_evidence.runner.status_reason", payload.get("status_reason"))
        != CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_REASON
    ):
        raise CurrentRuleCertificateError(
            "runner source evidence status_reason must be policy_active_zero_signal"
        )
    if (
        _required_text("source_evidence.runner.selection_policy", payload.get("selection_policy"))
        != str(version_tuple["stock_candidate_selection_policy"])
    ):
        raise CurrentRuleCertificateError(
            "runner source evidence selection_policy must match version tuple"
        )
    if (
        _required_text(
            "source_evidence.runner.stock_candidate_formula_version",
            payload.get("stock_candidate_formula_version"),
        )
        != str(version_tuple["stock_candidate_selection_formula_version"])
    ):
        raise CurrentRuleCertificateError(
            "runner source evidence stock_candidate_formula_version must match version tuple"
        )
    if _required_non_negative_int("source_evidence.runner.candidate_count", payload.get("candidate_count")) != 0:
        raise CurrentRuleCertificateError("runner source evidence candidate_count must equal 0")
    if _required_non_negative_int("source_evidence.runner.candidate_item_count", payload.get("candidate_item_count")) != 0:
        raise CurrentRuleCertificateError("runner source evidence candidate_item_count must equal 0")
    if _required_non_negative_int("source_evidence.runner.accepted_candidate_count", payload.get("accepted_candidate_count")) != 0:
        raise CurrentRuleCertificateError("runner source evidence accepted_candidate_count must equal 0")
    if _required_non_negative_int(
        "source_evidence.runner.future_business_date_violation_count",
        payload.get("future_business_date_violation_count"),
    ) != 0:
        raise CurrentRuleCertificateError(
            "runner source evidence future_business_date_violation_count must equal 0"
        )
    if _required_non_negative_int(
        "source_evidence.runner.future_availability_violation_count",
        payload.get("future_availability_violation_count"),
    ) != 0:
        raise CurrentRuleCertificateError(
            "runner source evidence future_availability_violation_count must equal 0"
        )
    market_state = _required_text(
        "source_evidence.runner.market_state",
        payload.get("market_state"),
    )
    if market_state not in stock_candidate_policy_active_market_states(EXP3B_STOCK_CANDIDATE_POLICY):
        raise CurrentRuleCertificateError(
            "runner source evidence market_state must remain policy-active for exp3b"
        )
    return {
        "trade_date": trade_date,
        "market_state": market_state,
    }


def _validate_calendar_summary(
    *,
    calendar_summary: Mapping[str, Any],
    trade_date: str,
    version_tuple: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _mapping("source_evidence.calendar", calendar_summary)
    if _required_text("source_evidence.calendar.source_id", payload.get("source_id")) != CALENDAR_SOURCE_ID:
        raise CurrentRuleCertificateError(
            "calendar source evidence source_id must match the approved calendar authority"
        )
    if _required_text("source_evidence.calendar.semantics", payload.get("semantics")) != CALENDAR_SEMANTICS:
        raise CurrentRuleCertificateError(
            "calendar source evidence semantics must match the approved calendar authority"
        )
    if _required_text("source_evidence.calendar.exchange", payload.get("exchange")) != CALENDAR_EXCHANGE:
        raise CurrentRuleCertificateError(
            "calendar source evidence exchange must match the approved calendar authority"
        )
    if (
        _required_text(
            "source_evidence.calendar.coverage_authority_mode",
            payload.get("coverage_authority_mode"),
        )
        != str(version_tuple["coverage_authority_mode"])
    ):
        raise CurrentRuleCertificateError(
            "calendar source evidence coverage_authority_mode must match version tuple"
        )
    if payload.get("certification_allowed") is not True:
        raise CurrentRuleCertificateError(
            "calendar source evidence certification_allowed must be true"
        )
    if _required_text("source_evidence.calendar.authority_status", payload.get("authority_status")) != APPROVED_AUTHORITY_STATUS:
        raise CurrentRuleCertificateError(
            "calendar source evidence authority_status must be approved"
        )
    request_start_date = _required_date_text(
        "source_evidence.calendar.request_start_date",
        payload.get("request_start_date"),
    )
    request_end_date = _required_date_text(
        "source_evidence.calendar.request_end_date",
        payload.get("request_end_date"),
    )
    if not (request_start_date <= trade_date <= request_end_date):
        raise CurrentRuleCertificateError(
            "calendar source evidence request range must include certificate trade_date"
        )
    if _required_date_text("source_evidence.calendar.trade_date", payload.get("trade_date")) != trade_date:
        raise CurrentRuleCertificateError(
            "calendar source evidence trade_date must match certificate trade_date"
        )
    _required_datetime_text("source_evidence.calendar.fetched_at", payload.get("fetched_at"))
    return {
        "trade_date": trade_date,
        "request_start_date": request_start_date,
        "request_end_date": request_end_date,
    }


def _validate_calendar_receipt(
    *,
    calendar_receipt: Mapping[str, Any],
    trade_date: str,
    expected_coverage_authority_mode: str,
) -> tuple[dict[str, Any], str]:
    payload = _mapping("calendar_receipt", calendar_receipt)
    ok, errors = validate_stock_analysis_calendar_receipt(payload)
    if not ok:
        raise CurrentRuleCertificateError(
            f"calendar receipt validation failed: {'; '.join(errors)}"
        )
    calendar_receipt_sha256 = _normalized_sha256(
        "calendar_receipt.canonical_receipt_sha256",
        payload.get("canonical_receipt_sha256"),
    )
    request = _mapping("calendar_receipt.request", payload.get("request"))
    request_start_date = _required_date_text(
        "calendar_receipt.request.start_date",
        request.get("start_date"),
    )
    request_end_date = _required_date_text(
        "calendar_receipt.request.end_date",
        request.get("end_date"),
    )
    if not (request_start_date <= trade_date <= request_end_date):
        raise CurrentRuleCertificateError(
            "calendar receipt trade_date must fall within the requested calendar range"
        )
    if payload.get("authority_status") != APPROVED_AUTHORITY_STATUS:
        raise CurrentRuleCertificateError("calendar receipt authority_status must be approved")
    if payload.get("certification_allowed") is not True:
        raise CurrentRuleCertificateError(
            "calendar receipt must set certification_allowed=true"
        )
    if payload.get("source_id") != CALENDAR_SOURCE_ID:
        raise CurrentRuleCertificateError(
            f"calendar receipt source_id must equal {CALENDAR_SOURCE_ID}"
        )
    if payload.get("semantics") != CALENDAR_SEMANTICS:
        raise CurrentRuleCertificateError(
            f"calendar receipt semantics must equal {CALENDAR_SEMANTICS}"
        )
    if payload.get("exchange") != CALENDAR_EXCHANGE:
        raise CurrentRuleCertificateError(
            f"calendar receipt exchange must equal {CALENDAR_EXCHANGE}"
        )
    if expected_coverage_authority_mode != CURRENT_RULE_COVERAGE_AUTHORITY_MODE:
        raise CurrentRuleCertificateError(
            "frozen version tuple coverage_authority_mode does not match the approved calendar authority constant"
        )
    rows = payload.get("calendar_rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise CurrentRuleCertificateError(
            "calendar_receipt.calendar_rows must be a sequence"
        )
    matching_rows = [
        row for row in rows if isinstance(row, Mapping) and str(row.get("cal_date")) == trade_date
    ]
    if len(matching_rows) != 1:
        raise CurrentRuleCertificateError(
            "calendar receipt must contain exactly one row for certificate trade_date"
        )
    trade_date_row = matching_rows[0]
    if _required_non_negative_int("calendar_receipt.trade_date_row.is_open", trade_date_row.get("is_open")) != 1:
        raise CurrentRuleCertificateError(
            "calendar receipt trade_date row must be open for certification"
        )
    fetched_at = _required_datetime_text(
        "calendar_receipt.fetched_at",
        payload.get("fetched_at"),
    )
    return (
        {
            "source_id": CALENDAR_SOURCE_ID,
            "semantics": CALENDAR_SEMANTICS,
            "exchange": CALENDAR_EXCHANGE,
            "coverage_authority_mode": CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
            "trade_date": trade_date,
            "certification_allowed": True,
            "authority_status": APPROVED_AUTHORITY_STATUS,
            "request_start_date": request_start_date,
            "request_end_date": request_end_date,
            "fetched_at": fetched_at,
        },
        calendar_receipt_sha256,
    )


def _freeze_version_tuple(
    frozen_version_tuple: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _mapping("frozen_version_tuple", frozen_version_tuple)
    frozen = {
        field_name: payload[field_name]
        for field_name in REQUIRED_VERSION_TUPLE_FIELDS
        if field_name in payload
    }
    missing = [field for field in REQUIRED_VERSION_TUPLE_FIELDS if field not in frozen]
    if missing:
        raise CurrentRuleCertificateError(
            f"frozen_version_tuple missing required fields: {', '.join(missing)}"
        )

    normalized: dict[str, Any] = {}
    for field_name, value in frozen.items():
        if field_name in {"strict_coverage", "fallback_covered"}:
            normalized[field_name] = _required_bool(
                f"frozen_version_tuple.{field_name}",
                value,
            )
        else:
            normalized[field_name] = _required_text(
                f"frozen_version_tuple.{field_name}",
                value,
            )

    if normalized["stock_candidate_selection_policy"] != EXP3B_STOCK_CANDIDATE_POLICY:
        raise CurrentRuleCertificateError(
            "frozen_version_tuple.stock_candidate_selection_policy must equal exp3b"
        )
    if (
        normalized["stock_candidate_selection_formula_version"]
        != STOCK_CANDIDATE_FORMULA_VERSION
    ):
        raise CurrentRuleCertificateError(
            "frozen_version_tuple.stock_candidate_selection_formula_version must equal the v7 current-rule bundle"
        )
    if normalized["decision_metric_basis"] != ALLOWED_DECISION_METRIC_BASIS:
        raise CurrentRuleCertificateError(
            "frozen_version_tuple.decision_metric_basis must equal net_next_open_adj"
        )
    if normalized["coverage_authority_mode"] != CURRENT_RULE_COVERAGE_AUTHORITY_MODE:
        raise CurrentRuleCertificateError(
            "frozen_version_tuple.coverage_authority_mode must match the approved calendar authority constant"
        )
    if normalized["strict_coverage"] is not True:
        raise CurrentRuleCertificateError(
            "frozen_version_tuple.strict_coverage must be true"
        )
    if normalized["fallback_covered"] is not False:
        raise CurrentRuleCertificateError(
            "frozen_version_tuple.fallback_covered must be false"
        )
    return normalized


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().upper()


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        _canonical_jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_jsonable(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, datetime):
        return _utc_datetime_text("datetime", value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical_jsonable(item) for item in value]
    return value


def _required_text(name: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise CurrentRuleCertificateError(f"{name} must be a non-empty string")
    return text


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CurrentRuleCertificateError(f"{name} must be a mapping")
    return value


def _required_date_text(name: str, value: object) -> str:
    text = _required_text(name, value)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise CurrentRuleCertificateError(f"{name} must be an ISO date") from exc


def _required_datetime_text(name: str, value: object) -> str:
    if isinstance(value, datetime):
        return _utc_datetime_text(name, value)
    text = _required_text(name, value)
    parsed = text.replace("Z", "+00:00")
    try:
        return _utc_datetime_text(name, datetime.fromisoformat(parsed))
    except ValueError as exc:
        raise CurrentRuleCertificateError(f"{name} must be an ISO datetime") from exc


def _utc_datetime_text(name: str, value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CurrentRuleCertificateError(f"{name} must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _required_non_negative_int(name: str, value: object) -> int:
    if value is None or isinstance(value, bool):
        raise CurrentRuleCertificateError(f"{name} must be a non-negative integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = int(value)
        except ValueError as exc:
            raise CurrentRuleCertificateError(f"{name} must be a non-negative integer") from exc
    else:
        raise CurrentRuleCertificateError(f"{name} must be a non-negative integer")
    if result < 0:
        raise CurrentRuleCertificateError(f"{name} must be a non-negative integer")
    return result


def _required_bool(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise CurrentRuleCertificateError(f"{name} must be a boolean")
    return value


def _normalized_sha256(name: str, value: object) -> str:
    text = _required_text(name, value).upper()
    if len(text) != 64 or any(ch not in "0123456789ABCDEF" for ch in text):
        raise CurrentRuleCertificateError(f"{name} must be a 64-character SHA-256 hex digest")
    return text


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise CurrentRuleCertificateError("expected a sequence of strings")


def _list_length(name: str, value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value)
    raise CurrentRuleCertificateError(f"{name} must be a sequence when present")
