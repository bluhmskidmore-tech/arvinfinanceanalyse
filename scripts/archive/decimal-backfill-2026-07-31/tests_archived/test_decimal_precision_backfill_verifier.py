# ARCHIVED 2026-08-12（C5 脚本盘点批次 1 归档）：随 ../verify_decimal_precision_backfill.py 一并移出 tests/。
# pytest 不再收集（pytest.ini testpaths 仅 tests/、backend/tests/）；归档件冻结、不保证可运行，仅作追溯。
from __future__ import annotations

import json
import hashlib
from decimal import Decimal
from pathlib import Path

import duckdb
import scripts.verify_decimal_precision_backfill as verifier_module

from scripts.verify_decimal_precision_backfill import (
    TARGET_DATE_TABLES,
    canonical_serialize,
    main,
    verify_databases,
)


FROZEN_TABLES = ("fx_daily_mid", "fact_formal_yield_curve_daily")
TARGET_TABLES = tuple(sorted(TARGET_DATE_TABLES))


def _create_fixture(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        for table in TARGET_TABLES:
            conn.execute(
                f"create table {table} (report_date varchar, row_key varchar, amount decimal(12,4))"
            )
            conn.execute(
                f"insert into {table} values (?, ?, ?), (?, ?, ?)",
                [
                    "2026-07-30",
                    "outside",
                    Decimal("1.2000"),
                    "2026-07-31",
                    "target",
                    Decimal("2.5000"),
                ],
            )
        conn.execute(
            "create table fx_daily_mid (trade_date varchar, row_key varchar, amount decimal(12,4))"
        )
        conn.execute("insert into fx_daily_mid values ('2026-07-31', 'fx', 1.2000)")
        conn.execute(
            "create table fact_formal_yield_curve_daily (trade_date varchar, row_key varchar, amount decimal(12,4))"
        )
        conn.execute(
            "insert into fact_formal_yield_curve_daily values ('2026-06-30', 'curve', 2.5000)"
        )
        conn.execute("create table other_table (row_key integer, amount decimal(12,4))")
        conn.execute("insert into other_table values (1, 9.0000)")
    finally:
        conn.close()


def _mutate(path: Path, sql: str) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(sql)
    finally:
        conn.close()


def _add_alt_schema_duplicate(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute("create schema alt")
        conn.execute(
            "create table alt.zqtz_bond_daily_snapshot (report_date varchar, row_key varchar, amount decimal(12,4))"
        )
        conn.execute(
            "insert into alt.zqtz_bond_daily_snapshot values ('2026-07-31', 'alt-target', 1.0000)"
        )
    finally:
        conn.close()


def test_target_date_delta_passes_and_writes_machine_receipt(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    _mutate(
        current,
        "update fact_formal_bond_analytics_daily set amount = 3.7500 where report_date = '2026-07-31'",
    )
    _mutate(
        current,
        "insert into fact_formal_bond_analytics_daily values ('2026-07-31', 'new-target', 4.0000)",
    )

    receipt_path = tmp_path / "receipt.json"
    receipt = verify_databases(
        baseline,
        current,
        receipt_path=receipt_path,
        temp_dir=tmp_path / "sort-work",
    )

    assert receipt["status"] == "pass"
    assert receipt["verdict"] == "PASS"
    assert receipt["errors"] == []
    assert receipt_path.is_file()
    persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "pass"
    check = receipt["checks"]["tables"]["main.fact_formal_bond_analytics_daily"]
    assert check["delta_policy"] == "target_date_only"
    assert check["allowed"] is True
    assert check["full_changed"] is True


def test_non_target_date_delta_fails_closed(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    _mutate(
        current,
        "update fact_formal_tyw_balance_daily set amount = 99.0000 where report_date = '2026-07-30'",
    )

    receipt = verify_databases(baseline, current, temp_dir=tmp_path / "sort-work")

    assert receipt["status"] == "fail"
    assert any("non-target-date rows changed" in error for error in receipt["errors"])


def test_out_of_scope_table_delta_fails(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    _mutate(current, "update other_table set amount = 10.0000 where row_key = 1")

    receipt = verify_databases(baseline, current, temp_dir=tmp_path / "sort-work")

    assert receipt["status"] == "fail"
    assert any(
        "unexpected table change in main.other_table" in error
        for error in receipt["errors"]
    )


def test_same_name_in_non_main_schema_is_frozen(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    _add_alt_schema_duplicate(baseline)
    _add_alt_schema_duplicate(current)
    _mutate(current, "update alt.zqtz_bond_daily_snapshot set amount = 2.0000")

    receipt = verify_databases(baseline, current, temp_dir=tmp_path / "sort-work")

    assert receipt["status"] == "fail"
    assert any(
        "unexpected table change in alt.zqtz_bond_daily_snapshot" in error
        for error in receipt["errors"]
    )
    comparison = receipt["checks"]["tables"]["alt.zqtz_bond_daily_snapshot"]
    assert comparison["delta_policy"] == "table_unchanged"


def test_fingerprint_change_during_scan_fails_closed(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    calls: dict[str, int] = {}

    def changing_fingerprint(path: Path) -> dict[str, object]:
        key = str(path)
        calls[key] = calls.get(key, 0) + 1
        value = calls[key]
        return {
            "path": key,
            "bytes": value,
            "mtime_ns": value,
            "sha256": ("a" if value == 1 else "b") * 64,
        }

    receipt = verify_databases(
        baseline,
        current,
        temp_dir=tmp_path / "sort-work",
        fingerprint_fn=changing_fingerprint,
    )

    assert receipt["status"] == "fail"
    assert receipt["checks"]["fingerprint"]["status"] == "fail"
    assert any(
        "fingerprint changed during read-only scan" in error
        for error in receipt["errors"]
    )


def test_decimal_scale_is_preserved_without_float_conversion() -> None:
    one_scale = canonical_serialize(Decimal("1.20"))
    two_scales = canonical_serialize(Decimal("1.200"))

    assert one_scale != two_scales
    assert b"1.2" not in one_scale
    assert b"1.2" not in two_scales


def test_spool_sorter_uses_fixed_width_binary_chunks_and_cleans_up(
    tmp_path: Path,
) -> None:
    sorter = verifier_module._SpoolSorter(tmp_path, "demo-table")
    first = bytes.fromhex("00" * 32)
    second = bytes.fromhex("ff" * 32)

    sorter.add(second)
    sorter.add(first)
    sorter._flush()

    chunks = sorted(tmp_path.glob("*.bin"))
    assert len(chunks) == 1
    assert chunks[0].stat().st_size == 64

    summary = sorter.finish()

    assert summary.row_count == 2
    assert summary.table_sha256 == hashlib.sha256(first + second).hexdigest()
    assert list(tmp_path.glob("*.bin")) == []


def test_schema_drift_fails_before_row_delta_is_allowed(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    _mutate(
        current, "alter table zqtz_bond_daily_snapshot add column schema_drift integer"
    )

    receipt = verify_databases(baseline, current, temp_dir=tmp_path / "sort-work")

    assert receipt["status"] == "fail"
    assert receipt["checks"]["inventory"]["status"] == "fail"
    assert any(
        "schema drift in main.zqtz_bond_daily_snapshot" in error
        for error in receipt["errors"]
    )


def test_time_bearing_report_date_type_fails_closed(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    for path in (baseline, current):
        _mutate(
            path,
            """
            alter table fact_formal_risk_tensor_daily
            alter column report_date set data type timestamp
            using report_date::timestamp
            """,
        )
    _mutate(
        current,
        """
        update fact_formal_risk_tensor_daily
        set amount = 3.7500
        where report_date = timestamp '2026-07-31 00:00:00'
        """,
    )

    receipt = verify_databases(baseline, current, temp_dir=tmp_path / "sort-work")

    assert receipt["status"] == "fail"
    assert any(
        "report_date has unsupported type 'TIMESTAMP'" in error
        for error in receipt["errors"]
    )


def test_time_bearing_report_date_string_fails_closed(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    _mutate(
        current,
        """
        update fact_formal_risk_tensor_daily
        set report_date = '2026-07-31T00:00:00'
        where row_key = 'target'
        """,
    )

    receipt = verify_databases(baseline, current, temp_dir=tmp_path / "sort-work")

    assert receipt["status"] == "fail"
    assert any(
        "main.fact_formal_risk_tensor_daily.report_date must not contain a time component"
        in error
        for error in receipt["errors"]
    )


def test_spool_chunks_are_cleaned_after_each_table(tmp_path: Path, monkeypatch) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    _mutate(
        current,
        "update fact_formal_bond_analytics_daily set amount = 3.7500 where report_date = '2026-07-31'",
    )
    after_table_chunk_counts: list[int] = []
    original = verifier_module._summarize_table

    def wrapped_summarize_table(*args, **kwargs):
        result = original(*args, **kwargs)
        temp_root = kwargs["temp_root"]
        after_table_chunk_counts.append(len(list(temp_root.iterdir())))
        return result

    monkeypatch.setattr(verifier_module, "_CHUNK_SIZE", 1)
    monkeypatch.setattr(verifier_module, "_summarize_table", wrapped_summarize_table)

    receipt = verify_databases(baseline, current, temp_dir=tmp_path / "sort-work")

    assert receipt["status"] == "pass"
    assert after_table_chunk_counts
    assert max(after_table_chunk_counts) == 0


def test_cli_returns_nonzero_on_failure_and_emits_json(capsys, tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    current = tmp_path / "current.duckdb"
    _create_fixture(baseline)
    _create_fixture(current)
    _mutate(current, "update other_table set amount = 10.0000 where row_key = 1")

    code = main(["--baseline", str(baseline), "--current", str(current)])
    output = json.loads(capsys.readouterr().out)

    assert code == 1
    assert output["status"] == "fail"
