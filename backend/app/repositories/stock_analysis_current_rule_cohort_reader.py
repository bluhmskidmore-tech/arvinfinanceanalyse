from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import duckdb
from backend.app.repositories.duckdb_repo import read_only_connection

logger = logging.getLogger(__name__)

PAGE_ID = "GAP-STOCK-ANALYSIS-PAGE"
COHORT_MODE = "current_rule_certified"
CERTIFIED_STATUS = "certified"
DECISION_METRIC_BASIS = "net_next_open_adj"
MIN_COMPLETED_DATES = 20
MIN_MATCHED_ENTRIES = 100
CONTROL_COUNT = 20

MANIFEST_TABLE = "stock_analysis_current_rule_cohort_manifest"
FACT_TABLE = "stock_analysis_current_rule_replay_fact"
CERTIFICATE_TABLE = "stock_analysis_current_rule_date_certificate"
COHORT_TABLES = (MANIFEST_TABLE, FACT_TABLE, CERTIFICATE_TABLE)

VERSION_FIELDS = (
    "candidate_rule_version",
    "stock_candidate_selection_formula_version",
    "candidate_outcome_formula_version",
    "execution_formula_version",
    "matched_baseline_formula_version",
    "market_gate_rule_version",
    "signal_confluence_rule_version",
    "macro_formula_version",
)
SOURCE_FIELDS = (
    "candidate_source_version",
    "execution_source_version",
    "matched_baseline_source_version",
    "macro_source_version",
    "calendar_source_id",
    "calendar_source_version",
    "theme_overlay_fingerprint",
    "choice_catalog_fingerprint",
)
ROW_VERSION_FIELDS = (
    "candidate_rule_version",
    "stock_candidate_selection_formula_version",
    "candidate_outcome_formula_version",
    "execution_formula_version",
    "matched_baseline_formula_version",
    "stock_candidate_selection_policy",
    "decision_metric_basis",
    "coverage_authority_mode",
    "strict_coverage",
    "fallback_covered",
    "candidate_source_version",
    "execution_source_version",
    "matched_baseline_source_version",
)
COUNT_FIELDS = (
    "completed_dates",
    "completed_with_signals_dates",
    "completed_no_signal_dates",
    "pending_tail_dates",
    "blocking_pending_dates",
    "unsupported_dates",
    "proxy_only_dates",
    "matched_entry_count",
    "t5_usable_count",
    "t20_usable_count",
    "stale_execution_row_count",
    "stale_matched_baseline_row_count",
)
DATE_FIELDS = (
    "requested_start_date",
    "requested_end_date",
    "observed_start_date",
    "observed_end_date",
    "certified_start_date",
    "certified_end_date",
    "evaluation_as_of_date",
    "governed_era_start",
    "governed_era_end",
)


class _GovernanceError(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def empty_current_rule_replay_closure(
    *,
    selection_status: str = "schema_unavailable",
    data_availability: str = "unsupported",
    status: str = "insufficient",
    active_cohort_count: int = 0,
    primary_blocker_code: str = "controlled_schema_unavailable",
    reason_codes: list[str] | None = None,
    tables_used: list[str] | None = None,
) -> dict[str, object]:
    return {
        "cohort_mode": COHORT_MODE,
        "selection_status": selection_status,
        "data_availability": data_availability,
        "status": status,
        "active_cohort_count": active_cohort_count,
        "cohort_id": None,
        **{field: None for field in DATE_FIELDS},
        "stock_candidate_selection_policy": None,
        "decision_metric_basis": None,
        "coverage_authority_mode": None,
        "strict_coverage": None,
        "fallback_covered": None,
        "versions": {field: None for field in VERSION_FIELDS},
        "sources": {field: None for field in SOURCE_FIELDS},
        "counts": {field: 0 for field in COUNT_FIELDS},
        "thresholds": {
            "completed_dates": MIN_COMPLETED_DATES,
            "matched_entry_count": MIN_MATCHED_ENTRIES,
        },
        "primary_blocker_code": primary_blocker_code,
        "reason_codes": list(reason_codes or ["controlled_schema_unavailable"]),
        "run_id": None,
        "promotion_run_id": None,
        "receipt": {
            "path": None,
            "sha256": None,
            "calendar_path": None,
            "calendar_sha256": None,
        },
        "tables_used": list(tables_used or []),
    }


def read_current_rule_replay_closure(
    *,
    duckdb_path: str | Path,
    page_as_of_date: str | None,
) -> dict[str, object]:
    """Select and validate the unique active certified replay cohort without writes."""
    target = Path(duckdb_path)
    if not target.is_file():
        return empty_current_rule_replay_closure(
            reason_codes=[
                "controlled_schema_unavailable",
                "current_rule_cohort_database_unavailable",
            ]
        )

    schema_ready = False
    active_count = 0
    try:
        with read_only_connection(
            str(target), retries=5, retry_delay_seconds=0.1
        ) as connection:
            existing_tables = _existing_tables(connection)
            if not existing_tables:
                return empty_current_rule_replay_closure()
            if existing_tables != set(COHORT_TABLES):
                raise _GovernanceError("current_rule_cohort_schema_partial")
            schema_ready = True

            active_rows = _query_mappings(
                connection,
                f"""
                select *
                from {MANIFEST_TABLE}
                where page_id = ? and cohort_mode = ? and cohort_status = ?
                  and is_active = true
                """,
                [PAGE_ID, COHORT_MODE, CERTIFIED_STATUS],
            )
            active_count = len(active_rows)
            if active_count == 0:
                return empty_current_rule_replay_closure(
                    selection_status="no_active_certified",
                    data_availability="no_data",
                    status="insufficient",
                    primary_blocker_code="no_active_certified_cohort",
                    reason_codes=["no_active_certified_cohort"],
                    tables_used=list(COHORT_TABLES),
                )
            if active_count > 1:
                return empty_current_rule_replay_closure(
                    selection_status="governance_conflict",
                    data_availability="unsupported",
                    status="blocked",
                    active_cohort_count=active_count,
                    primary_blocker_code="multiple_active_certified_cohorts",
                    reason_codes=["multiple_active_certified_cohorts"],
                    tables_used=list(COHORT_TABLES),
                )
            return _validated_closure(
                connection,
                manifest=active_rows[0],
                page_as_of_date=page_as_of_date,
            )
    except _GovernanceError as exc:
        return empty_current_rule_replay_closure(
            selection_status=(
                "as_of_mismatch"
                if exc.reason_code
                in {
                    "active_cohort_lookahead",
                    "page_as_of_date_unresolved",
                    "page_as_of_date_invalid",
                }
                else "governance_error"
            ),
            data_availability="unsupported",
            status="blocked",
            active_cohort_count=active_count,
            primary_blocker_code=(
                "as_of_mismatch"
                if exc.reason_code
                in {
                    "active_cohort_lookahead",
                    "page_as_of_date_unresolved",
                    "page_as_of_date_invalid",
                }
                else "governance_error"
            ),
            reason_codes=[
                (
                    "as_of_mismatch"
                    if exc.reason_code
                    in {
                        "active_cohort_lookahead",
                        "page_as_of_date_unresolved",
                        "page_as_of_date_invalid",
                    }
                    else "governance_error"
                ),
                exc.reason_code,
            ],
            tables_used=list(COHORT_TABLES) if schema_ready else [],
        )
    except Exception:
        logger.exception("Current-rule replay closure read failed closed")
        return empty_current_rule_replay_closure(
            selection_status="governance_error",
            data_availability="unsupported",
            status="blocked",
            active_cohort_count=active_count,
            primary_blocker_code="governance_error",
            reason_codes=["governance_error", "current_rule_cohort_read_failed"],
            tables_used=list(COHORT_TABLES) if schema_ready else [],
        )


def _validated_closure(
    connection: duckdb.DuckDBPyConnection,
    *,
    manifest: dict[str, object],
    page_as_of_date: str | None,
) -> dict[str, object]:
    cohort_id = _required_text(manifest, "cohort_id")
    if _required_text(manifest, "page_id") != PAGE_ID:
        raise _GovernanceError("active_cohort_page_id_mismatch")
    if _required_text(manifest, "cohort_mode") != COHORT_MODE:
        raise _GovernanceError("active_cohort_mode_mismatch")

    parsed_dates = {field: _required_date(manifest, field) for field in DATE_FIELDS}
    range_pairs = (
        ("requested_start_date", "requested_end_date"),
        ("observed_start_date", "observed_end_date"),
        ("certified_start_date", "certified_end_date"),
        ("governed_era_start", "governed_era_end"),
    )
    if any(parsed_dates[start] > parsed_dates[end] for start, end in range_pairs):
        raise _GovernanceError("active_cohort_date_order_invalid")
    evaluation_as_of = parsed_dates["evaluation_as_of_date"]
    if (
        parsed_dates["requested_end_date"] > evaluation_as_of
        or parsed_dates["observed_end_date"] > evaluation_as_of
    ):
        raise _GovernanceError("active_cohort_date_order_invalid")
    if not (
        parsed_dates["governed_era_start"]
        <= parsed_dates["certified_start_date"]
        <= parsed_dates["certified_end_date"]
        <= parsed_dates["governed_era_end"]
        <= evaluation_as_of
    ):
        raise _GovernanceError("active_cohort_date_order_invalid")
    if not page_as_of_date:
        raise _GovernanceError("page_as_of_date_unresolved")
    try:
        parsed_page_as_of = date.fromisoformat(page_as_of_date)
    except ValueError as exc:
        raise _GovernanceError("page_as_of_date_invalid") from exc
    if parsed_dates["evaluation_as_of_date"] > parsed_page_as_of:
        raise _GovernanceError("active_cohort_lookahead")

    versions = {field: _required_text(manifest, field) for field in VERSION_FIELDS}
    sources = {field: _required_text(manifest, field) for field in SOURCE_FIELDS}
    policy = _required_text(manifest, "stock_candidate_selection_policy")
    metric_basis = _required_text(manifest, "decision_metric_basis")
    coverage_mode = _required_text(manifest, "coverage_authority_mode")
    strict_coverage = _required_bool(manifest, "strict_coverage")
    fallback_covered = _required_bool(manifest, "fallback_covered")
    run_id = _required_text(manifest, "run_id")
    promotion_run_id = _required_text(manifest, "promoted_by_run_id")
    receipt_path = _required_text(manifest, "receipt_path")
    receipt_sha256 = _required_sha256(manifest, "receipt_sha256")
    calendar_receipt_path = _required_text(manifest, "calendar_receipt_path")
    calendar_receipt_sha256 = _required_sha256(manifest, "calendar_receipt_sha256")

    facts = _query_mappings(
        connection,
        f"""
        select cohort_id, signal_date, stock_code, signal_kind,
               entry_executable, candidate_data_status, execution_data_status,
               matched_baseline_status, matched_baseline_control_count,
               {", ".join(ROW_VERSION_FIELDS)}, run_id
        from {FACT_TABLE}
        where cohort_id = ?
        """,
        [cohort_id],
    )
    certificates = _query_mappings(
        connection,
        f"""
        select cohort_id, trade_date, certificate_status, affects_completed_stats,
               candidate_count, executable_candidate_count, t5_usable_count,
               t20_usable_count, matched_entry_count, stale_execution_row_count,
               stale_matched_baseline_row_count, unsupported_source_count,
               proxy_only_evidence_count, blocking_gap_count,
               control_entry_proven_count, control_exit_proven_5d_count,
               control_exit_proven_20d_count, calendar_receipt_path,
               calendar_receipt_sha256, calendar_source_id, calendar_source_version,
               {", ".join(ROW_VERSION_FIELDS)}, run_id
        from {CERTIFICATE_TABLE}
        where cohort_id = ?
        """,
        [cohort_id],
    )
    _validate_natural_keys(facts=facts, certificates=certificates)

    common_tuple = {
        **{field: manifest.get(field) for field in ROW_VERSION_FIELDS},
        "run_id": run_id,
    }
    for row in [*facts, *certificates]:
        if any(row.get(field) != value for field, value in common_tuple.items()):
            raise _GovernanceError("active_cohort_version_tuple_mismatch")

    facts_by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    for fact in facts:
        facts_by_date[str(fact["signal_date"])].append(fact)
    certificate_dates: set[str] = set()
    certificate_trade_dates: list[date] = []
    completed_facts: list[dict[str, object]] = []
    completed_stale_counts = {
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
    }
    derived_counts = {field: 0 for field in COUNT_FIELDS}
    allowed_statuses = {
        "completed_with_signals",
        "completed_no_strategy_signals",
        "pending_tail",
        "blocking_pending",
        "unsupported",
        "proxy_only",
    }
    for certificate in certificates:
        parsed_trade_date = _required_date(certificate, "trade_date")
        trade_date = parsed_trade_date.isoformat()
        if not (
            parsed_dates["certified_start_date"]
            <= parsed_trade_date
            <= parsed_dates["certified_end_date"]
        ):
            raise _GovernanceError(
                "active_cohort_certificate_date_outside_certified_range"
            )
        certificate_dates.add(trade_date)
        certificate_trade_dates.append(parsed_trade_date)
        certificate_status = str(certificate.get("certificate_status") or "")
        if certificate_status not in allowed_statuses:
            raise _GovernanceError("active_cohort_certificate_status_invalid")
        date_facts = facts_by_date.get(trade_date, [])
        fact_count = len(date_facts)
        if certificate_status == "completed_with_signals":
            if not fact_count or certificate.get("affects_completed_stats") is not True:
                raise _GovernanceError("active_cohort_signal_certificate_mismatch")
            _validate_completed_with_signals_certificate(
                certificate,
                fact_count=fact_count,
            )
            completed_facts.extend(date_facts)
            derived_counts["completed_with_signals_dates"] += 1
            derived_counts["completed_dates"] += 1
        elif certificate_status == "completed_no_strategy_signals":
            if fact_count or certificate.get("affects_completed_stats") is not True:
                raise _GovernanceError("active_cohort_zero_signal_certificate_mismatch")
            _validate_completed_no_signal_certificate(certificate)
            derived_counts["completed_no_signal_dates"] += 1
            derived_counts["completed_dates"] += 1
        else:
            if certificate.get("affects_completed_stats") is not False:
                raise _GovernanceError("active_cohort_pending_certificate_affects_completed")
            _validate_noncompleted_certificate(
                certificate,
                certificate_status=certificate_status,
                fact_count=fact_count,
            )
            derived_counts[f"{certificate_status}_dates"] += 1

        if certificate_status in {
            "completed_with_signals",
            "completed_no_strategy_signals",
        }:
            for field in (
                "matched_entry_count",
                "t5_usable_count",
                "t20_usable_count",
            ):
                derived_counts[field] += _nonnegative_int(certificate, field)
            for field in completed_stale_counts:
                completed_stale_counts[field] += _nonnegative_int(certificate, field)
        derived_counts["stale_execution_row_count"] += _nonnegative_int(
            certificate, "stale_execution_row_count"
        )
        derived_counts["stale_matched_baseline_row_count"] += _nonnegative_int(
            certificate, "stale_matched_baseline_row_count"
        )
        if certificate.get("calendar_receipt_path") != calendar_receipt_path or str(
            certificate.get("calendar_receipt_sha256") or ""
        ).upper() != calendar_receipt_sha256:
            raise _GovernanceError("active_cohort_calendar_receipt_mismatch")
        if (
            certificate.get("calendar_source_id") != sources["calendar_source_id"]
            or certificate.get("calendar_source_version")
            != sources["calendar_source_version"]
        ):
            raise _GovernanceError("active_cohort_calendar_source_mismatch")

    if set(facts_by_date) - certificate_dates:
        raise _GovernanceError("active_cohort_fact_without_certificate")
    if (
        not certificate_trade_dates
        or min(certificate_trade_dates) != parsed_dates["certified_start_date"]
        or max(certificate_trade_dates) != parsed_dates["certified_end_date"]
    ):
        raise _GovernanceError("active_cohort_certificate_bounds_mismatch")
    stale_fact_counts = _validate_fact_rows(completed_facts)
    if len(completed_facts) != derived_counts["matched_entry_count"]:
        raise _GovernanceError("active_cohort_fact_count_mismatch")
    if (
        stale_fact_counts["stale_execution_row_count"]
        != completed_stale_counts["stale_execution_row_count"]
        or stale_fact_counts["stale_matched_baseline_row_count"]
        != completed_stale_counts["stale_matched_baseline_row_count"]
    ):
        raise _GovernanceError("active_cohort_stale_fact_count_mismatch")

    manifest_counts = {field: _nonnegative_int(manifest, field) for field in COUNT_FIELDS}
    if manifest_counts != derived_counts:
        raise _GovernanceError("active_cohort_manifest_count_mismatch")

    hard_blocker_reasons: list[str] = []
    shortage_reasons: list[str] = []
    if metric_basis != DECISION_METRIC_BASIS:
        hard_blocker_reasons.append("decision_metric_basis_not_net_next_open_adj")
    if strict_coverage is not True:
        hard_blocker_reasons.append("strict_coverage_not_proven")
    if fallback_covered is not False:
        hard_blocker_reasons.append("fallback_coverage_present")
    if manifest_counts["completed_dates"] < MIN_COMPLETED_DATES:
        shortage_reasons.append("completed_dates_below_threshold")
    if manifest_counts["matched_entry_count"] < MIN_MATCHED_ENTRIES:
        shortage_reasons.append("matched_entry_count_below_threshold")
    blocker_count_codes = {
        "blocking_pending_dates": "blocking_pending_dates",
        "unsupported_dates": "unsupported_dates",
        "proxy_only_dates": "proxy_only_dates",
        "stale_execution_row_count": "stale_execution_rows",
        "stale_matched_baseline_row_count": "stale_matched_baseline_rows",
    }
    for field, code in blocker_count_codes.items():
        if manifest_counts[field] != 0:
            hard_blocker_reasons.append(code)

    reason_codes = hard_blocker_reasons + shortage_reasons
    closure_status = (
        "blocked"
        if hard_blocker_reasons
        else "insufficient"
        if shortage_reasons
        else "ready"
    )
    if fallback_covered or manifest_counts["proxy_only_dates"]:
        data_availability = "fallback"
    elif (
        parsed_dates["evaluation_as_of_date"] < parsed_page_as_of
        or manifest_counts["stale_execution_row_count"]
        or manifest_counts["stale_matched_baseline_row_count"]
    ):
        data_availability = "stale"
    elif manifest_counts["unsupported_dates"]:
        data_availability = "unsupported"
    else:
        data_availability = "fresh"
    return {
        "cohort_mode": COHORT_MODE,
        "selection_status": "unique_active_certified",
        "data_availability": data_availability,
        "status": closure_status,
        "active_cohort_count": 1,
        "cohort_id": cohort_id,
        **{field: str(manifest[field]) for field in DATE_FIELDS},
        "stock_candidate_selection_policy": policy,
        "decision_metric_basis": metric_basis,
        "coverage_authority_mode": coverage_mode,
        "strict_coverage": strict_coverage,
        "fallback_covered": fallback_covered,
        "versions": versions,
        "sources": sources,
        "counts": manifest_counts,
        "thresholds": {
            "completed_dates": MIN_COMPLETED_DATES,
            "matched_entry_count": MIN_MATCHED_ENTRIES,
        },
        "primary_blocker_code": (
            None if closure_status == "ready" else "current_rule_cohort_not_ready"
        ),
        "reason_codes": ["current_rule_cohort_ready"] if not reason_codes else reason_codes,
        "run_id": run_id,
        "promotion_run_id": promotion_run_id,
        "receipt": {
            "path": receipt_path,
            "sha256": receipt_sha256,
            "calendar_path": calendar_receipt_path,
            "calendar_sha256": calendar_receipt_sha256,
        },
        "tables_used": list(COHORT_TABLES),
    }


def _existing_tables(connection: duckdb.DuckDBPyConnection) -> set[str]:
    rows = connection.execute(
        """
        select table_name
        from information_schema.tables
        where table_schema = 'main' and table_name in (?, ?, ?)
        """,
        list(COHORT_TABLES),
    ).fetchall()
    return {str(row[0]) for row in rows}


def _query_mappings(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[object],
) -> list[dict[str, object]]:
    cursor = connection.execute(query, parameters)
    columns = [str(column[0]) for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _validate_natural_keys(
    *,
    facts: list[dict[str, object]],
    certificates: list[dict[str, object]],
) -> None:
    fact_keys = [
        (
            row.get("cohort_id"),
            row.get("signal_date"),
            row.get("stock_code"),
            row.get("signal_kind"),
        )
        for row in facts
    ]
    if len(fact_keys) != len(set(fact_keys)):
        raise _GovernanceError("active_cohort_duplicate_fact_natural_key")
    certificate_keys = [
        (row.get("cohort_id"), row.get("trade_date")) for row in certificates
    ]
    if len(certificate_keys) != len(set(certificate_keys)):
        raise _GovernanceError("active_cohort_duplicate_certificate_natural_key")


def _validate_completed_with_signals_certificate(
    certificate: Mapping[str, object], *, fact_count: int
) -> None:
    expected_fact_counts = (
        "candidate_count",
        "executable_candidate_count",
        "t5_usable_count",
        "t20_usable_count",
        "matched_entry_count",
    )
    if any(
        _nonnegative_int(certificate, field) != fact_count
        for field in expected_fact_counts
    ):
        raise _GovernanceError("active_cohort_certificate_fact_count_mismatch")
    expected_control_count = fact_count * CONTROL_COUNT
    if any(
        _nonnegative_int(certificate, field) != expected_control_count
        for field in (
            "control_entry_proven_count",
            "control_exit_proven_5d_count",
            "control_exit_proven_20d_count",
        )
    ):
        raise _GovernanceError("active_cohort_control_proof_count_mismatch")
    if any(
        _nonnegative_int(certificate, field) != 0
        for field in (
            "unsupported_source_count",
            "proxy_only_evidence_count",
            "blocking_gap_count",
        )
    ):
        raise _GovernanceError("active_cohort_completed_certificate_has_source_gap")


def _validate_completed_no_signal_certificate(
    certificate: Mapping[str, object],
) -> None:
    if any(
        _nonnegative_int(certificate, field) != 0
        for field in (
            "candidate_count",
            "executable_candidate_count",
            "t5_usable_count",
            "t20_usable_count",
            "matched_entry_count",
            "stale_execution_row_count",
            "stale_matched_baseline_row_count",
            "unsupported_source_count",
            "proxy_only_evidence_count",
            "blocking_gap_count",
            "control_entry_proven_count",
            "control_exit_proven_5d_count",
            "control_exit_proven_20d_count",
        )
    ):
        raise _GovernanceError("active_cohort_zero_signal_certificate_count_mismatch")


def _validate_noncompleted_certificate(
    certificate: Mapping[str, object],
    *,
    certificate_status: str,
    fact_count: int,
) -> None:
    fields = (
        "candidate_count",
        "executable_candidate_count",
        "t5_usable_count",
        "t20_usable_count",
        "matched_entry_count",
        "stale_execution_row_count",
        "stale_matched_baseline_row_count",
        "unsupported_source_count",
        "proxy_only_evidence_count",
        "blocking_gap_count",
        "control_entry_proven_count",
        "control_exit_proven_5d_count",
        "control_exit_proven_20d_count",
    )
    counts = {field: _nonnegative_int(certificate, field) for field in fields}
    if not (
        fact_count <= counts["candidate_count"]
        and counts["executable_candidate_count"] <= counts["candidate_count"]
        and counts["matched_entry_count"] <= counts["executable_candidate_count"]
        and counts["t20_usable_count"]
        <= counts["t5_usable_count"]
        <= counts["executable_candidate_count"]
        and counts["control_entry_proven_count"]
        <= counts["matched_entry_count"] * CONTROL_COUNT
        and counts["control_exit_proven_5d_count"]
        <= counts["t5_usable_count"] * CONTROL_COUNT
        and counts["control_exit_proven_20d_count"]
        <= counts["t20_usable_count"] * CONTROL_COUNT
    ):
        raise _GovernanceError("active_cohort_noncompleted_certificate_count_invalid")
    if certificate_status == "pending_tail" and any(
        counts[field] != 0
        for field in (
            "stale_execution_row_count",
            "stale_matched_baseline_row_count",
            "unsupported_source_count",
            "proxy_only_evidence_count",
            "blocking_gap_count",
        )
    ):
        raise _GovernanceError("active_cohort_pending_tail_has_non_maturity_gap")


def _validate_fact_rows(facts: list[dict[str, object]]) -> dict[str, int]:
    stale_execution_rows = 0
    stale_matched_baseline_rows = 0
    for row in facts:
        if (
            row.get("entry_executable") is not True
            or row.get("candidate_data_status") != "usable"
            or _nonnegative_int(row, "matched_baseline_control_count") != CONTROL_COUNT
        ):
            raise _GovernanceError("active_cohort_fact_not_strictly_usable")
        execution_status = row.get("execution_data_status")
        matched_status = row.get("matched_baseline_status")
        if execution_status not in {"usable", "stale"} or matched_status not in {
            "usable",
            "stale",
        }:
            raise _GovernanceError("active_cohort_fact_status_invalid")
        stale_execution_rows += int(execution_status == "stale")
        stale_matched_baseline_rows += int(matched_status == "stale")
    return {
        "stale_execution_row_count": stale_execution_rows,
        "stale_matched_baseline_row_count": stale_matched_baseline_rows,
    }


def _required_text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    text = str(value or "").strip()
    if not text:
        raise _GovernanceError(f"active_cohort_{field}_missing")
    return text


def _required_sha256(row: Mapping[str, object], field: str) -> str:
    value = _required_text(row, field).upper()
    if len(value) != 64 or any(character not in "0123456789ABCDEF" for character in value):
        raise _GovernanceError(f"active_cohort_{field}_invalid")
    return value


def _required_date(row: Mapping[str, object], field: str) -> date:
    value = _required_text(row, field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise _GovernanceError(f"active_cohort_{field}_invalid") from exc
    if parsed.isoformat() != value:
        raise _GovernanceError(f"active_cohort_{field}_invalid")
    return parsed


def _required_bool(row: Mapping[str, object], field: str) -> bool:
    value = row.get(field)
    if not isinstance(value, bool):
        raise _GovernanceError(f"active_cohort_{field}_invalid")
    return value


def _nonnegative_int(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _GovernanceError(f"active_cohort_{field}_invalid")
    return value
