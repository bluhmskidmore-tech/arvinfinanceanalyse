from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.governance import stock_analysis_source_availability_receipt as module
from backend.app.tasks import (
    stock_analysis_current_rule_cohort_materialize as cohort_task,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

CAPTURED_AT = "2026-08-22T12:30:00Z"
CAPTURE_DATE = "2026-08-22"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _create_source_db(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date date,
              stock_code varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation values
              ('2026-08-18', '000001.SZ', 'obs-v1', 'choice-v1', 'obs-rule-v1', 'obs-run-1'),
              ('2026-08-19', '000002.SZ', 'obs-v1', 'choice-v1', 'obs-rule-v1', 'obs-run-1'),
              ('2026-08-20', '000003.SZ', 'obs-v2', null, null, 'obs-run-2')
            """
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              trade_date date,
              stock_code varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into stock_adjustment_factor values
              ('2026-08-18', '000001.SZ', 1.0, 'factor-v1', 'factor-run-1'),
              ('2026-08-21', '000002.SZ', 1.1, 'factor-v1', 'factor-run-1')
            """
        )
        conn.execute("create table unapproved_source (payload varchar)")
    finally:
        conn.close()


def _whitelist() -> dict[str, str]:
    return {
        "choice_stock_daily_observation": "trade_date",
        "stock_adjustment_factor": "trade_date",
    }


def test_build_receipt_is_deterministic_read_only_and_hash_preserving(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sources.duckdb"
    _create_source_db(db_path)
    database_hash = _file_sha256(db_path)
    original_connect = module.duckdb.connect
    connect_calls: list[dict[str, object]] = []

    def wrapped_connect(*args, **kwargs):
        connect_calls.append(dict(kwargs))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(module.duckdb, "connect", wrapped_connect)
    first = module.build_stock_analysis_source_availability_receipt(
        duckdb_path=db_path,
        table_whitelist=_whitelist(),
        captured_at=CAPTURED_AT,
    )
    second = module.build_stock_analysis_source_availability_receipt(
        duckdb_path=db_path,
        table_whitelist=dict(reversed(list(_whitelist().items()))),
        captured_at=CAPTURED_AT,
    )

    assert first == second
    assert connect_calls == [{"read_only": True}, {"read_only": True}]
    assert first["database"] == {
        "path": str(db_path.resolve()),
        "sha256_before": database_hash,
        "sha256_after": database_hash,
        "unchanged": True,
    }
    assert _file_sha256(db_path) == database_hash
    assert first["attestation"] == {
        "kind": module.ATTESTATION_KIND,
        "available_at_semantics": module.AVAILABLE_AT_SEMANTICS,
        "historical_ingestion_time_inferred": False,
    }
    assert {source["available_at"] for source in first["sources"]} == {CAPTURE_DATE}

    ok, errors = module.validate_stock_analysis_source_availability_receipt(first)
    assert ok is True
    assert errors == ()


def test_build_receipt_records_tuple_counts_ranges_and_optional_versions(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sources.duckdb"
    _create_source_db(db_path)

    receipt = module.build_stock_analysis_source_availability_receipt(
        duckdb_path=db_path,
        table_whitelist=_whitelist(),
        captured_at=CAPTURED_AT,
    )

    by_key = {
        (
            source["table"],
            source["source_version"],
            source["vendor_version"],
            source["rule_version"],
            source["run_id"],
        ): source
        for source in receipt["sources"]
    }
    factor = by_key[("stock_adjustment_factor", "factor-v1", "", "", "factor-run-1")]
    assert factor["row_count"] == 2
    assert factor["min_observed_date"] == "2026-08-18"
    assert factor["max_observed_date"] == "2026-08-21"
    assert "unapproved_source" not in {source["table"] for source in receipt["sources"]}

    downstream_index = cohort_task._validate_source_availability_receipt(
        receipt,
        evaluation=CAPTURE_DATE,
    )
    assert (
        downstream_index[
            ("stock_adjustment_factor", "factor-v1", "", "", "factor-run-1")
        ]
        == CAPTURE_DATE
    )
    with pytest.raises(
        cohort_task.CurrentRuleCohortError,
        match="source availability occurs after evaluation date",
    ):
        cohort_task._validate_source_availability_receipt(
            receipt,
            evaluation="2026-08-21",
        )


@pytest.mark.parametrize("missing_column", ["source_version", "run_id"])
def test_build_receipt_rejects_missing_required_source_columns(
    tmp_path: Path,
    missing_column: str,
) -> None:
    db_path = tmp_path / f"missing-{missing_column}.duckdb"
    columns = ["trade_date date", "source_version varchar", "run_id varchar"]
    columns = [value for value in columns if not value.startswith(missing_column)]
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(f"create table source_table ({', '.join(columns)})")
    finally:
        conn.close()

    with pytest.raises(ValueError, match=f"missing required columns: {missing_column}"):
        module.build_stock_analysis_source_availability_receipt(
            duckdb_path=db_path,
            table_whitelist={"source_table": "trade_date"},
            captured_at=CAPTURED_AT,
        )


def test_build_receipt_rejects_blank_required_source_values(tmp_path: Path) -> None:
    db_path = tmp_path / "blank-source.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table source_table (
              trade_date date,
              source_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute("insert into source_table values ('2026-08-20', '', 'run-1')")
    finally:
        conn.close()

    with pytest.raises(ValueError, match="blank source_version or run_id"):
        module.build_stock_analysis_source_availability_receipt(
            duckdb_path=db_path,
            table_whitelist={"source_table": "trade_date"},
            captured_at=CAPTURED_AT,
        )


def test_build_receipt_rejects_future_or_non_utc_capture(tmp_path: Path) -> None:
    db_path = tmp_path / "future.duckdb"
    _create_source_db(db_path)
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    with pytest.raises(ValueError, match="captured_at must not be in the future"):
        module.build_stock_analysis_source_availability_receipt(
            duckdb_path=db_path,
            table_whitelist=_whitelist(),
            captured_at=future,
        )
    with pytest.raises(ValueError, match="captured_at must use UTC"):
        module.build_stock_analysis_source_availability_receipt(
            duckdb_path=db_path,
            table_whitelist=_whitelist(),
            captured_at="2026-08-22T12:30:00+08:00",
        )


def test_validate_receipt_detects_tampering(tmp_path: Path) -> None:
    db_path = tmp_path / "tampered.duckdb"
    _create_source_db(db_path)
    receipt = module.build_stock_analysis_source_availability_receipt(
        duckdb_path=db_path,
        table_whitelist=_whitelist(),
        captured_at=CAPTURED_AT,
    )
    receipt["sources"][0]["row_count"] = 999

    ok, errors = module.validate_stock_analysis_source_availability_receipt(receipt)

    assert ok is False
    assert "canonical_receipt_sha256 mismatch" in errors
