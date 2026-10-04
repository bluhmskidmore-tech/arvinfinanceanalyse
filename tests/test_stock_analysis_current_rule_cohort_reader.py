from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.repositories import stock_analysis_current_rule_cohort_reader as reader

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

SCHEMA_PATH = Path(
    "backend/app/schema_registry/duckdb/controlled/45_stock_analysis_current_rule_cohort.sql"
)
VERSION_VALUES = {
    "candidate_rule_version": "rv_candidate_v1",
    "stock_candidate_selection_formula_version": "fv_selection_v1",
    "candidate_outcome_formula_version": "fv_outcome_v1",
    "execution_formula_version": "fv_execution_v1",
    "matched_baseline_formula_version": "fv_matched_v1",
    "market_gate_rule_version": "rv_market_gate_v1",
    "signal_confluence_rule_version": "rv_confluence_v1",
    "macro_formula_version": "fv_macro_v1",
    "candidate_source_version": "sv_candidate_v1",
    "execution_source_version": "sv_execution_v1",
    "matched_baseline_source_version": "sv_matched_v1",
    "macro_source_version": "sv_macro_v1",
    "theme_overlay_fingerprint": "theme-fingerprint-v1",
    "choice_catalog_fingerprint": "choice-fingerprint-v1",
    "stock_candidate_selection_policy": "exp3b",
    "decision_metric_basis": "net_next_open_adj",
    "coverage_authority_mode": "tushare.trade_cal:SSE|open_days",
    "strict_coverage": True,
    "fallback_covered": False,
}
ROW_VERSION_VALUES = {
    field: VERSION_VALUES[field] for field in reader.ROW_VERSION_FIELDS
}
RECEIPT_SHA = "A" * 64
CALENDAR_SHA = "B" * 64


def _insert(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    row: dict[str, object],
) -> None:
    columns = list(row)
    connection.execute(
        f"insert into {table} ({', '.join(columns)}) values "
        f"({', '.join('?' for _ in columns)})",
        [row[column] for column in columns],
    )


def _create_schema(connection: duckdb.DuckDBPyConnection) -> None:
    for statement in SCHEMA_PATH.read_text(encoding="utf-8").split("-- MOSS:STMT"):
        if statement.strip():
            connection.execute(statement)


def _manifest_row(
    cohort_id: str,
    *,
    active: bool = True,
    status: str = "certified",
) -> dict[str, object]:
    return {
        "cohort_id": cohort_id,
        "page_id": reader.PAGE_ID,
        "cohort_mode": reader.COHORT_MODE,
        "cohort_status": status,
        "is_active": active,
        "requested_start_date": "2026-06-01",
        "requested_end_date": "2026-06-20",
        "observed_start_date": "2026-06-01",
        "observed_end_date": "2026-06-20",
        "certified_start_date": "2026-06-01",
        "certified_end_date": "2026-06-20",
        "evaluation_as_of_date": "2026-06-30",
        "governed_era_start": "2026-01-01",
        "governed_era_end": "2026-06-30",
        **VERSION_VALUES,
        "calendar_source_id": "tushare.trade_cal:SSE",
        "calendar_source_version": CALENDAR_SHA,
        "receipt_path": f"C:/evidence/{cohort_id}-dry-run.json",
        "receipt_sha256": RECEIPT_SHA,
        "calendar_receipt_path": "C:/evidence/calendar.json",
        "calendar_receipt_sha256": CALENDAR_SHA,
        "run_id": f"run-{cohort_id}",
        "idempotency_key": f"idempotency-{cohort_id}",
        "promoted_by_run_id": f"promotion-{cohort_id}",
        "completed_dates": 20,
        "completed_with_signals_dates": 20,
        "completed_no_signal_dates": 0,
        "pending_tail_dates": 0,
        "blocking_pending_dates": 0,
        "unsupported_dates": 0,
        "proxy_only_dates": 0,
        "matched_entry_count": 100,
        "t5_usable_count": 100,
        "t20_usable_count": 100,
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
    }


def _add_valid_cohort(
    connection: duckdb.DuckDBPyConnection,
    cohort_id: str,
    *,
    active: bool = True,
    status: str = "certified",
) -> None:
    manifest = _manifest_row(cohort_id, active=active, status=status)
    _insert(connection, reader.MANIFEST_TABLE, manifest)
    start = date(2026, 6, 1)
    for day_offset in range(20):
        signal_date = (start + timedelta(days=day_offset)).isoformat()
        for candidate_index in range(5):
            _insert(
                connection,
                reader.FACT_TABLE,
                {
                    "cohort_id": cohort_id,
                    "signal_date": signal_date,
                    "stock_code": f"{candidate_index + 1:06d}.SZ",
                    "signal_kind": "stock_candidate",
                    "entry_executable": True,
                    "candidate_data_status": "usable",
                    "execution_data_status": "usable",
                    "matched_baseline_status": "usable",
                    "matched_baseline_control_count": 20,
                    **ROW_VERSION_VALUES,
                    "run_id": manifest["run_id"],
                },
            )
        _insert(
            connection,
            reader.CERTIFICATE_TABLE,
            {
                "cohort_id": cohort_id,
                "trade_date": signal_date,
                "certificate_status": "completed_with_signals",
                "affects_completed_stats": True,
                "candidate_count": 5,
                "executable_candidate_count": 5,
                "t5_usable_count": 5,
                "t20_usable_count": 5,
                "matched_entry_count": 5,
                "stale_execution_row_count": 0,
                "stale_matched_baseline_row_count": 0,
                "unsupported_source_count": 0,
                "proxy_only_evidence_count": 0,
                "blocking_gap_count": 0,
                "control_entry_proven_count": 100,
                "control_exit_proven_5d_count": 100,
                "control_exit_proven_20d_count": 100,
                "calendar_receipt_path": manifest["calendar_receipt_path"],
                "calendar_receipt_sha256": manifest["calendar_receipt_sha256"],
                "calendar_source_id": manifest["calendar_source_id"],
                "calendar_source_version": manifest["calendar_source_version"],
                **ROW_VERSION_VALUES,
                "run_id": manifest["run_id"],
            },
        )


def _database(tmp_path: Path, *, cohort_id: str | None = None) -> Path:
    target = tmp_path / "cohort-reader.duckdb"
    connection = duckdb.connect(str(target))
    try:
        _create_schema(connection)
        if cohort_id is not None:
            _add_valid_cohort(connection, cohort_id)
    finally:
        connection.close()
    return target


def test_reader_returns_explicit_schema_unavailable_without_creating_tables(
    tmp_path: Path,
) -> None:
    target = tmp_path / "ordinary-v45.duckdb"
    connection = duckdb.connect(str(target))
    connection.execute("create table ordinary_table(value integer)")
    connection.close()
    before = hashlib.sha256(target.read_bytes()).hexdigest()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "schema_unavailable"
    assert closure["data_availability"] == "unsupported"
    assert closure["status"] == "insufficient"
    assert closure["active_cohort_count"] == 0
    assert closure["cohort_id"] is None
    assert closure["counts"] == {field: 0 for field in reader.COUNT_FIELDS}
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before


def test_reader_returns_no_active_without_selecting_an_inactive_cohort(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path)
    connection = duckdb.connect(str(target))
    _add_valid_cohort(connection, "inactive", active=False, status="certified")
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "no_active_certified"
    assert closure["data_availability"] == "no_data"
    assert closure["status"] == "insufficient"
    assert closure["cohort_id"] is None


def test_reader_primary_selector_ignores_active_noncertified_manifest(tmp_path: Path) -> None:
    target = _database(tmp_path)
    connection = duckdb.connect(str(target))
    _add_valid_cohort(
        connection,
        "active-unpromoted",
        active=True,
        status="materialized_unpromoted",
    )
    connection.close()

    without_certified = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert without_certified["selection_status"] == "no_active_certified"
    assert without_certified["data_availability"] == "no_data"
    assert without_certified["status"] == "insufficient"
    assert without_certified["active_cohort_count"] == 0

    connection = duckdb.connect(str(target))
    _add_valid_cohort(connection, "active-certified")
    connection.close()
    with_certified = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert with_certified["selection_status"] == "unique_active_certified"
    assert with_certified["status"] == "ready"
    assert with_certified["active_cohort_count"] == 1
    assert with_certified["cohort_id"] == "active-certified"


def test_reader_returns_ready_only_for_one_fully_tied_out_active_cohort(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="ready-cohort")
    before = hashlib.sha256(target.read_bytes()).hexdigest()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert set(closure) == {
        "cohort_mode",
        "selection_status",
        "data_availability",
        "status",
        "active_cohort_count",
        "cohort_id",
        *reader.DATE_FIELDS,
        "stock_candidate_selection_policy",
        "decision_metric_basis",
        "coverage_authority_mode",
        "strict_coverage",
        "fallback_covered",
        "versions",
        "sources",
        "counts",
        "thresholds",
        "primary_blocker_code",
        "reason_codes",
        "run_id",
        "promotion_run_id",
        "receipt",
        "tables_used",
    }
    assert closure["selection_status"] == "unique_active_certified"
    assert closure["data_availability"] == "fresh"
    assert closure["status"] == "ready"
    assert closure["cohort_id"] == "ready-cohort"
    assert closure["decision_metric_basis"] == "net_next_open_adj"
    assert closure["counts"] == {
        "completed_dates": 20,
        "completed_with_signals_dates": 20,
        "completed_no_signal_dates": 0,
        "pending_tail_dates": 0,
        "blocking_pending_dates": 0,
        "unsupported_dates": 0,
        "proxy_only_dates": 0,
        "matched_entry_count": 100,
        "t5_usable_count": 100,
        "t20_usable_count": 100,
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
    }
    assert closure["thresholds"] == {
        "completed_dates": 20,
        "matched_entry_count": 100,
    }
    assert closure["receipt"] == {
        "path": "C:/evidence/ready-cohort-dry-run.json",
        "sha256": RECEIPT_SHA,
        "calendar_path": "C:/evidence/calendar.json",
        "calendar_sha256": CALENDAR_SHA,
    }
    assert set(closure["versions"]) == set(reader.VERSION_FIELDS)
    assert set(closure["sources"]) == set(reader.SOURCE_FIELDS)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before


def test_reader_accepts_independent_requested_observed_and_certified_ranges(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="independent-ranges")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"""
        update {reader.MANIFEST_TABLE}
        set requested_start_date = '2026-06-10', requested_end_date = '2026-06-25',
            observed_start_date = '2026-05-01', observed_end_date = '2026-06-10',
            governed_era_start = '2026-05-15', governed_era_end = '2026-06-29'
        where cohort_id = 'independent-ranges'
        """
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "unique_active_certified"
    assert closure["status"] == "ready"
    assert closure["requested_start_date"] == "2026-06-10"
    assert closure["observed_end_date"] == "2026-06-10"
    assert closure["certified_start_date"] == "2026-06-01"


@pytest.mark.parametrize(
    ("start_field", "end_field"),
    [
        ("requested_start_date", "requested_end_date"),
        ("observed_start_date", "observed_end_date"),
        ("certified_start_date", "certified_end_date"),
        ("governed_era_start", "governed_era_end"),
    ],
)
def test_reader_rejects_reversed_manifest_date_ranges(
    tmp_path: Path,
    start_field: str,
    end_field: str,
) -> None:
    target = _database(tmp_path, cohort_id="reversed-range")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.MANIFEST_TABLE} set {start_field} = '2026-06-21', "
        f"{end_field} = '2026-06-20' where cohort_id = 'reversed-range'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_date_order_invalid",
    ]


@pytest.mark.parametrize("end_field", ["requested_end_date", "observed_end_date"])
def test_reader_rejects_requested_or_observed_range_after_evaluation(
    tmp_path: Path,
    end_field: str,
) -> None:
    target = _database(tmp_path, cohort_id="range-lookahead")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.MANIFEST_TABLE} set {end_field} = '2026-07-01' "
        "where cohort_id = 'range-lookahead'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_date_order_invalid",
    ]


def test_reader_rejects_certified_range_outside_governed_era(tmp_path: Path) -> None:
    target = _database(tmp_path, cohort_id="outside-governed-era")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.MANIFEST_TABLE} set governed_era_start = '2026-06-02' "
        "where cohort_id = 'outside-governed-era'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_date_order_invalid",
    ]


def test_reader_rejects_certificate_date_outside_certified_range(tmp_path: Path) -> None:
    target = _database(tmp_path, cohort_id="outside-certified-range")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.CERTIFICATE_TABLE} set trade_date = '2026-06-21' "
        "where cohort_id = 'outside-certified-range' and trade_date = '2026-06-20'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_certificate_date_outside_certified_range",
    ]


def test_reader_requires_strict_iso_certificate_trade_date(tmp_path: Path) -> None:
    target = _database(tmp_path, cohort_id="non-iso-certificate")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.CERTIFICATE_TABLE} set trade_date = '20260601' "
        "where cohort_id = 'non-iso-certificate' and trade_date = '2026-06-01'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_trade_date_invalid",
    ]


def test_reader_requires_certificate_min_max_to_match_certified_bounds(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="certificate-bounds")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.MANIFEST_TABLE} set certified_start_date = '2026-05-31' "
        "where cohort_id = 'certificate-bounds'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_certificate_bounds_mismatch",
    ]


def test_reader_blocks_multiple_active_cohorts_instead_of_choosing_latest(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path)
    connection = duckdb.connect(str(target))
    _add_valid_cohort(connection, "older-active")
    _add_valid_cohort(connection, "newer-active")
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_conflict"
    assert closure["data_availability"] == "unsupported"
    assert closure["status"] == "blocked"
    assert closure["active_cohort_count"] == 2
    assert closure["cohort_id"] is None
    assert closure["reason_codes"] == ["multiple_active_certified_cohorts"]


def test_reader_blocks_manifest_certificate_fact_count_mismatch(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="mismatch")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.MANIFEST_TABLE} set matched_entry_count = 99 "
        "where cohort_id = 'mismatch'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["data_availability"] == "unsupported"
    assert closure["status"] == "blocked"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_manifest_count_mismatch",
    ]


def test_reader_blocks_active_cohort_evaluated_after_page_as_of(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="lookahead")

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-29",
    )

    assert closure["selection_status"] == "as_of_mismatch"
    assert closure["data_availability"] == "unsupported"
    assert closure["status"] == "blocked"
    assert closure["reason_codes"] == ["as_of_mismatch", "active_cohort_lookahead"]


def test_reader_keeps_certificate_ready_while_disclosing_stale_availability(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="stale-but-certified")

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-07-01",
    )

    assert closure["selection_status"] == "unique_active_certified"
    assert closure["data_availability"] == "stale"
    assert closure["status"] == "ready"


def test_reader_marks_nineteen_completed_dates_insufficient(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="nineteen-dates")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"delete from {reader.FACT_TABLE} where cohort_id = ? and signal_date = ?",
        ["nineteen-dates", "2026-06-20"],
    )
    connection.execute(
        f"delete from {reader.CERTIFICATE_TABLE} where cohort_id = ? and trade_date = ?",
        ["nineteen-dates", "2026-06-20"],
    )
    connection.execute(
        f"""
        update {reader.MANIFEST_TABLE}
        set requested_end_date = '2026-06-19', observed_end_date = '2026-06-19',
            certified_end_date = '2026-06-19', completed_dates = 19,
            completed_with_signals_dates = 19, matched_entry_count = 95,
            t5_usable_count = 95, t20_usable_count = 95
        where cohort_id = 'nineteen-dates'
        """
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "unique_active_certified"
    assert closure["status"] == "insufficient"
    assert closure["primary_blocker_code"] == "current_rule_cohort_not_ready"
    assert closure["reason_codes"] == [
        "completed_dates_below_threshold",
        "matched_entry_count_below_threshold",
    ]


def test_reader_marks_twenty_dates_with_ninety_nine_matches_insufficient(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="ninety-nine-matches")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"delete from {reader.FACT_TABLE} where cohort_id = ? and signal_date = ? "
        "and stock_code = ?",
        ["ninety-nine-matches", "2026-06-01", "000005.SZ"],
    )
    connection.execute(
        f"""
        update {reader.CERTIFICATE_TABLE}
        set candidate_count = 4, executable_candidate_count = 4,
            t5_usable_count = 4, t20_usable_count = 4, matched_entry_count = 4,
            control_entry_proven_count = 80, control_exit_proven_5d_count = 80,
            control_exit_proven_20d_count = 80
        where cohort_id = 'ninety-nine-matches' and trade_date = '2026-06-01'
        """
    )
    connection.execute(
        f"""
        update {reader.MANIFEST_TABLE}
        set matched_entry_count = 99, t5_usable_count = 99, t20_usable_count = 99
        where cohort_id = 'ninety-nine-matches'
        """
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "unique_active_certified"
    assert closure["status"] == "insufficient"
    assert closure["reason_codes"] == ["matched_entry_count_below_threshold"]


@pytest.mark.parametrize(
    ("certificate_field", "fact_field", "reason_code"),
    [
        ("stale_execution_row_count", "execution_data_status", "stale_execution_rows"),
        (
            "stale_matched_baseline_row_count",
            "matched_baseline_status",
            "stale_matched_baseline_rows",
        ),
    ],
)
def test_reader_hard_blocks_stale_certified_rows(
    tmp_path: Path,
    certificate_field: str,
    fact_field: str,
    reason_code: str,
) -> None:
    target = _database(tmp_path, cohort_id="stale-row")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.FACT_TABLE} set {fact_field} = 'stale' "
        "where cohort_id = 'stale-row' and signal_date = '2026-06-01' "
        "and stock_code = '000001.SZ'"
    )
    connection.execute(
        f"update {reader.CERTIFICATE_TABLE} set {certificate_field} = 1 "
        "where cohort_id = 'stale-row' and trade_date = '2026-06-01'"
    )
    connection.execute(
        f"update {reader.MANIFEST_TABLE} set {certificate_field} = 1 "
        "where cohort_id = 'stale-row'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "unique_active_certified"
    assert closure["data_availability"] == "stale"
    assert closure["status"] == "blocked"
    assert closure["primary_blocker_code"] == "current_rule_cohort_not_ready"
    assert closure["reason_codes"] == [reason_code]


def test_reader_fails_closed_on_row_version_mismatch(tmp_path: Path) -> None:
    target = _database(tmp_path, cohort_id="version-mismatch")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.FACT_TABLE} set candidate_rule_version = 'wrong' "
        "where cohort_id = 'version-mismatch' and signal_date = '2026-06-01' "
        "and stock_code = '000001.SZ'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["status"] == "blocked"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_version_tuple_mismatch",
    ]


def test_reader_counts_completed_no_signal_certificate_without_fact_rows(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="zero-signal")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"delete from {reader.FACT_TABLE} where cohort_id = ? and signal_date = ?",
        ["zero-signal", "2026-06-20"],
    )
    connection.execute(
        f"""
        update {reader.CERTIFICATE_TABLE}
        set certificate_status = 'completed_no_strategy_signals', candidate_count = 0,
            executable_candidate_count = 0, t5_usable_count = 0, t20_usable_count = 0,
            matched_entry_count = 0, control_entry_proven_count = 0,
            control_exit_proven_5d_count = 0, control_exit_proven_20d_count = 0
        where cohort_id = 'zero-signal' and trade_date = '2026-06-20'
        """
    )
    connection.execute(
        f"""
        update {reader.MANIFEST_TABLE}
        set completed_with_signals_dates = 19, completed_no_signal_dates = 1,
            matched_entry_count = 95, t5_usable_count = 95, t20_usable_count = 95
        where cohort_id = 'zero-signal'
        """
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "unique_active_certified"
    assert closure["status"] == "insufficient"
    assert closure["counts"]["completed_dates"] == 20
    assert closure["counts"]["completed_with_signals_dates"] == 19
    assert closure["counts"]["completed_no_signal_dates"] == 1
    assert closure["reason_codes"] == ["matched_entry_count_below_threshold"]


def test_reader_keeps_completed_with_signals_fact_control_parity_strict(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="signal-parity")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"update {reader.CERTIFICATE_TABLE} set candidate_count = 4 "
        "where cohort_id = 'signal-parity' and trade_date = '2026-06-01'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_certificate_fact_count_mismatch",
    ]


def test_reader_requires_zero_counts_for_completed_no_signal_certificate(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="invalid-zero-signal")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"delete from {reader.FACT_TABLE} where cohort_id = ? and signal_date = ?",
        ["invalid-zero-signal", "2026-06-20"],
    )
    connection.execute(
        f"update {reader.CERTIFICATE_TABLE} "
        "set certificate_status = 'completed_no_strategy_signals' "
        "where cohort_id = 'invalid-zero-signal' and trade_date = '2026-06-20'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_zero_signal_certificate_count_mismatch",
    ]


def test_reader_keeps_ready_with_disclosed_nonblocking_pending_tail(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="pending-tail")
    connection = duckdb.connect(str(target))
    manifest = _manifest_row("pending-tail")
    _insert(
        connection,
        reader.CERTIFICATE_TABLE,
        {
            "cohort_id": "pending-tail",
            "trade_date": "2026-06-21",
            "certificate_status": "pending_tail",
            "affects_completed_stats": False,
            "candidate_count": 3,
            "executable_candidate_count": 2,
            "t5_usable_count": 2,
            "t20_usable_count": 0,
            "matched_entry_count": 2,
            "stale_execution_row_count": 0,
            "stale_matched_baseline_row_count": 0,
            "unsupported_source_count": 0,
            "proxy_only_evidence_count": 0,
            "blocking_gap_count": 0,
            "control_entry_proven_count": 40,
            "control_exit_proven_5d_count": 40,
            "control_exit_proven_20d_count": 0,
            "calendar_receipt_path": manifest["calendar_receipt_path"],
            "calendar_receipt_sha256": manifest["calendar_receipt_sha256"],
            "calendar_source_id": manifest["calendar_source_id"],
            "calendar_source_version": manifest["calendar_source_version"],
            **ROW_VERSION_VALUES,
            "run_id": manifest["run_id"],
        },
    )
    _insert(
        connection,
        reader.FACT_TABLE,
        {
            "cohort_id": "pending-tail",
            "signal_date": "2026-06-21",
            "stock_code": "999999.SZ",
            "signal_kind": "stock_candidate",
            "entry_executable": False,
            "candidate_data_status": "pending",
            "execution_data_status": "pending",
            "matched_baseline_status": "pending",
            "matched_baseline_control_count": 0,
            **ROW_VERSION_VALUES,
            "run_id": manifest["run_id"],
        },
    )
    connection.execute(
        f"update {reader.MANIFEST_TABLE} "
        "set pending_tail_dates = 1, certified_end_date = '2026-06-21' "
        "where cohort_id = 'pending-tail'"
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["status"] == "ready"
    assert closure["counts"]["pending_tail_dates"] == 1
    assert closure["counts"]["completed_dates"] == 20
    assert closure["counts"]["matched_entry_count"] == 100
    assert closure["counts"]["t5_usable_count"] == 100
    assert closure["counts"]["t20_usable_count"] == 100
    assert closure["primary_blocker_code"] is None


def test_reader_rejects_pending_tail_with_non_maturity_source_gap(
    tmp_path: Path,
) -> None:
    target = _database(tmp_path, cohort_id="invalid-pending-tail")
    connection = duckdb.connect(str(target))
    connection.execute(
        f"""
        update {reader.CERTIFICATE_TABLE}
        set certificate_status = 'pending_tail', affects_completed_stats = false,
            t20_usable_count = 0, control_exit_proven_20d_count = 0,
            unsupported_source_count = 1
        where cohort_id = 'invalid-pending-tail' and trade_date = '2026-06-20'
        """
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "governance_error"
    assert closure["reason_codes"] == [
        "governance_error",
        "active_cohort_pending_tail_has_non_maturity_gap",
    ]


@pytest.mark.parametrize(
    ("field", "value", "reason_code", "data_availability"),
    [
        (
            "decision_metric_basis",
            "gross_close_to_close",
            "decision_metric_basis_not_net_next_open_adj",
            "fresh",
        ),
        ("strict_coverage", False, "strict_coverage_not_proven", "fresh"),
        ("fallback_covered", True, "fallback_coverage_present", "fallback"),
    ],
)
def test_reader_hard_blocks_invalid_metric_and_coverage_contracts(
    tmp_path: Path,
    field: str,
    value: object,
    reason_code: str,
    data_availability: str,
) -> None:
    target = _database(tmp_path, cohort_id="contract-blocker")
    connection = duckdb.connect(str(target))
    for table in (
        reader.MANIFEST_TABLE,
        reader.FACT_TABLE,
        reader.CERTIFICATE_TABLE,
    ):
        connection.execute(
            f"update {table} set {field} = ? where cohort_id = 'contract-blocker'",
            [value],
        )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "unique_active_certified"
    assert closure["data_availability"] == data_availability
    assert closure["status"] == "blocked"
    assert closure["reason_codes"] == [reason_code]


@pytest.mark.parametrize(
    ("certificate_status", "manifest_field", "reason_code", "data_availability"),
    [
        ("blocking_pending", "blocking_pending_dates", "blocking_pending_dates", "fresh"),
        ("unsupported", "unsupported_dates", "unsupported_dates", "unsupported"),
        ("proxy_only", "proxy_only_dates", "proxy_only_dates", "fallback"),
    ],
)
def test_reader_hard_blocks_governed_date_blockers(
    tmp_path: Path,
    certificate_status: str,
    manifest_field: str,
    reason_code: str,
    data_availability: str,
) -> None:
    target = _database(tmp_path, cohort_id="date-blocker")
    connection = duckdb.connect(str(target))
    count_field = {
        "blocking_pending": "blocking_gap_count",
        "unsupported": "unsupported_source_count",
        "proxy_only": "proxy_only_evidence_count",
    }[certificate_status]
    connection.execute(
        f"""
        update {reader.CERTIFICATE_TABLE}
        set certificate_status = ?, affects_completed_stats = false,
            candidate_count = 5, executable_candidate_count = 2,
            t5_usable_count = 1, t20_usable_count = 0, matched_entry_count = 2,
            control_entry_proven_count = 40, control_exit_proven_5d_count = 20,
            control_exit_proven_20d_count = 0, {count_field} = 1
        where cohort_id = 'date-blocker' and trade_date = '2026-06-20'
        """,
        [certificate_status],
    )
    connection.execute(
        f"""
        update {reader.MANIFEST_TABLE}
        set completed_dates = 19, completed_with_signals_dates = 19,
            matched_entry_count = 95, t5_usable_count = 95, t20_usable_count = 95,
            {manifest_field} = 1
        where cohort_id = 'date-blocker'
        """
    )
    connection.close()

    closure = reader.read_current_rule_replay_closure(
        duckdb_path=target,
        page_as_of_date="2026-06-30",
    )

    assert closure["selection_status"] == "unique_active_certified"
    assert closure["data_availability"] == data_availability
    assert closure["status"] == "blocked"
    assert closure["reason_codes"] == [
        reason_code,
        "completed_dates_below_threshold",
        "matched_entry_count_below_threshold",
    ]
