from __future__ import annotations

from pathlib import Path

import duckdb

from scripts.data_readiness_report import (
    DEFAULT_TABLE_SPECS,
    NumericRangeCheck,
    TableSpec,
    build_data_readiness_report,
    render_markdown,
)


def _connect(path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(path))


def test_missing_duckdb_fails_closed(tmp_path: Path) -> None:
    report = build_data_readiness_report(
        tmp_path / "missing.duckdb",
        specs=[],
        as_of_date="2026-06-06",
    )

    assert report["status"] == "block"
    assert report["summary"]["blocking_issue_count"] == 1
    assert report["issues"][0]["code"] == "duckdb_unavailable"


def test_report_flags_core_data_quality_blockers(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table stale_formal (
                report_date varchar,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into stale_formal values (?, ?, ?)",
            [
                ("2026-05-30", "sv", "rv"),
                ("2026-05-30", "sv", "rv"),
            ],
        )
        conn.execute(
            """
            create table empty_formal (
                report_date varchar,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table future_news (
                received_at varchar
            )
            """
        )
        conn.executemany(
            "insert into future_news values (?)",
            [("2026-06-05T10:00:00+08:00",), ("2026-09-01T00:00:00+08:00",)],
        )
        conn.execute(
            """
            create table commodity_daily (
                trade_date varchar,
                source_version varchar,
                rule_version varchar,
                vendor_version varchar
            )
            """
        )
        conn.executemany(
            "insert into commodity_daily values (?, ?, ?, ?)",
            [("2026-05-20", "sv", "rv", "vv"), ("20260521", "sv", "rv", "vv")],
        )
        conn.execute(
            """
            create table meta_missing (
                report_date varchar,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into meta_missing values (?, ?, ?)",
            [("2026-05-31", "", "rv"), ("2026-05-31", "sv", None)],
        )
        conn.execute(
            """
            create table latest_sparse (
                report_date varchar,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into latest_sparse values (?, ?, ?)",
            [
                ("2026-05-30", "sv", "rv"),
                ("2026-05-30", "sv", "rv"),
                ("2026-05-31", "sv", "rv"),
            ],
        )
        conn.execute(
            """
            create table scenario_empty (
                report_date varchar,
                source_version varchar,
                rule_version varchar
            )
            """
        )
    finally:
        conn.close()

    specs = [
        TableSpec(
            label="stale formal",
            table="stale_formal",
            date_column="report_date",
            target_latest_date="2026-05-31",
            required_meta_columns=("source_version", "rule_version"),
        ),
        TableSpec(
            label="empty formal",
            table="empty_formal",
            date_column="report_date",
            required_meta_columns=("source_version", "rule_version"),
        ),
        TableSpec(
            label="future news",
            table="future_news",
            date_column="received_at",
            scope="analytical",
            required_meta_columns=(),
        ),
        TableSpec(
            label="commodity",
            table="commodity_daily",
            date_column="trade_date",
            scope="analytical",
            required_meta_columns=("source_version", "rule_version", "vendor_version"),
        ),
        TableSpec(
            label="missing metadata",
            table="meta_missing",
            date_column="report_date",
            required_meta_columns=("source_version", "rule_version", "cache_version"),
        ),
        TableSpec(
            label="latest sparse",
            table="latest_sparse",
            date_column="report_date",
            required_meta_columns=("source_version", "rule_version"),
            latest_min_rows=2,
        ),
        TableSpec(
            label="scenario empty",
            table="scenario_empty",
            date_column="report_date",
            scope="scenario",
            allow_empty=True,
            required_meta_columns=("source_version", "rule_version"),
        ),
    ]

    report = build_data_readiness_report(
        duckdb_path,
        specs=specs,
        as_of_date="2026-06-06",
    )

    assert report["status"] == "block"
    issue_codes = {issue["code"] for issue in report["issues"]}
    assert {
        "latest_date_before_target",
        "table_empty",
        "future_date_values",
        "non_iso_date_values",
        "metadata_column_missing",
        "metadata_value_missing",
        "latest_rows_below_min",
    }.issubset(issue_codes)

    scenario = next(item for item in report["tables"] if item["table"] == "scenario_empty")
    assert scenario["status"] == "observe"
    assert scenario["issues"][0]["code"] == "allowed_empty_table"

    markdown = render_markdown(report)
    assert "Status: block" in markdown
    assert "latest_date_before_target" in markdown
    assert "scenario_empty" in markdown


def test_report_groups_repeated_date_value_issues(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table noisy_dates (
                trade_date varchar
            )
            """
        )
        conn.executemany(
            "insert into noisy_dates values (?)",
            [
                ("20260520",),
                ("20260521",),
                ("20260522",),
                ("2026-06-07",),
                ("2026-06-08T00:00:00+08:00",),
            ],
        )
    finally:
        conn.close()

    report = build_data_readiness_report(
        duckdb_path,
        specs=[
            TableSpec(
                label="noisy dates",
                table="noisy_dates",
                date_column="trade_date",
                required_meta_columns=(),
            )
        ],
        as_of_date="2026-06-06",
    )

    assert report["status"] == "block"
    table = report["tables"][0]
    assert [issue["code"] for issue in table["issues"]] == [
        "non_iso_date_values",
        "future_date_values",
    ]
    assert table["issues"][0]["details"] == {
        "date_column": "trade_date",
        "count": 3,
        "sample_values": ["20260520", "20260521", "20260522"],
    }
    assert table["issues"][1]["details"] == {
        "date_column": "trade_date",
        "as_of_date": "2026-06-06",
        "count": 2,
        "min_value": "2026-06-07",
        "max_value": "2026-06-08T00:00:00+08:00",
        "sample_values": ["2026-06-07", "2026-06-08T00:00:00+08:00"],
    }
    assert report["summary"]["blocking_issue_count"] == 2


def test_report_allows_configured_latest_date_lag_with_observation(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table formal_curve (
                trade_date varchar,
                source_version varchar,
                rule_version varchar,
                vendor_version varchar
            )
            """
        )
        conn.execute(
            "insert into formal_curve values (?, ?, ?, ?)",
            ["2026-05-29", "sv", "rv", "vv"],
        )
    finally:
        conn.close()

    report = build_data_readiness_report(
        duckdb_path,
        specs=[
            TableSpec(
                label="formal curve",
                table="formal_curve",
                date_column="trade_date",
                required_meta_columns=("source_version", "rule_version", "vendor_version"),
                target_latest_date="2026-05-31",
                target_max_lag_days=3,
            )
        ],
        as_of_date="2026-06-06",
    )

    assert report["status"] == "pass"
    assert report["summary"]["blocking_issue_count"] == 0
    table = report["tables"][0]
    assert table["status"] == "observe"
    assert table["issues"][0]["code"] == "latest_date_within_allowed_lag"
    assert table["issues"][0]["details"] == {
        "latest": "2026-05-29",
        "target": "2026-05-31",
        "lag_days": 2,
        "max_lag_days": 3,
        "calendar_gap_reason": "target_window_non_business_days",
        "gap_dates": ["2026-05-30", "2026-05-31"],
        "non_business_dates": ["2026-05-30", "2026-05-31"],
        "latest_business_date": "2026-05-29",
    }

    markdown = render_markdown(report)
    assert "target_window_non_business_days" in markdown
    assert "previous business day: 2026-05-29" in markdown


def test_report_flags_stock_and_bond_specific_data_quality_blockers(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table stock_observation (
                trade_date varchar,
                stock_code varchar,
                close_value double,
                volume double,
                source_version varchar,
                rule_version varchar,
                vendor_version varchar
            )
            """
        )
        conn.executemany(
            "insert into stock_observation values (?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-29", "000001.SZ", 10.0, 100.0, "sv", "rv", "vv"),
                ("2026-05-29", "000001.SZ", 10.1, 110.0, "sv", "rv", "vv"),
                ("2026-05-29", "000002.SZ", -1.0, -5.0, "sv", "rv", "vv"),
                ("2026-05-29", "", 9.0, 90.0, "sv", "rv", "vv"),
            ],
        )
        conn.execute(
            """
            create table bond_analytics (
                report_date varchar,
                instrument_code varchar,
                portfolio_name varchar,
                accounting_class varchar,
                market_value double,
                ytm double,
                dv01 double,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into bond_analytics values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-31", "BOND-1", "Book A", "AC", 1000.0, 0.03, 20.0, "sv", "rv"),
                ("2026-05-31", "BOND-1", "Book A", "AC", 1000.0, 0.04, 25.0, "sv", "rv"),
                ("2026-05-31", "", "Book A", "AC", -1.0, 3.5, 0.0, "sv", "rv"),
            ],
        )
    finally:
        conn.close()

    report = build_data_readiness_report(
        duckdb_path,
        specs=[
            TableSpec(
                label="stock observation",
                table="stock_observation",
                date_column="trade_date",
                scope="analytical",
                required_meta_columns=("source_version", "rule_version", "vendor_version"),
                unique_key_columns=("trade_date", "stock_code"),
                required_data_columns=("stock_code", "close_value"),
                numeric_range_checks=(
                    NumericRangeCheck("close_value", min_value=0, allow_null=False),
                    NumericRangeCheck("volume", min_value=0, allow_null=False),
                ),
            ),
            TableSpec(
                label="bond analytics",
                table="bond_analytics",
                date_column="report_date",
                required_meta_columns=("source_version", "rule_version"),
                unique_key_columns=("report_date", "instrument_code", "portfolio_name", "accounting_class"),
                required_data_columns=("instrument_code", "portfolio_name", "accounting_class"),
                numeric_range_checks=(
                    NumericRangeCheck("market_value", min_value=0, allow_null=False),
                    NumericRangeCheck("ytm", min_value=-1, max_value=1, allow_null=True),
                    NumericRangeCheck("dv01", min_value=0, allow_null=True),
                ),
            ),
        ],
        as_of_date="2026-06-08",
    )

    assert report["status"] == "block"
    issue_codes = {issue["code"] for issue in report["issues"]}
    assert {
        "duplicate_key_values",
        "required_data_value_missing",
        "numeric_value_below_min",
        "numeric_value_above_max",
    }.issubset(issue_codes)

    stock = next(item for item in report["tables"] if item["table"] == "stock_observation")
    assert stock["unique_key_columns"] == ["trade_date", "stock_code"]
    assert stock["required_data_columns"] == ["stock_code", "close_value"]
    assert stock["numeric_range_checks"][0]["column"] == "close_value"
    assert any(issue["details"].get("duplicate_count") == 1 for issue in stock["issues"])

    bond = next(item for item in report["tables"] if item["table"] == "bond_analytics")
    assert bond["unique_key_columns"] == [
        "report_date",
        "instrument_code",
        "portfolio_name",
        "accounting_class",
    ]
    assert any(issue["code"] == "numeric_value_above_max" for issue in bond["issues"])

    markdown = render_markdown(report)
    assert "duplicate_key_values" in markdown
    assert "numeric_value_above_max" in markdown


def test_report_flags_configured_quality_check_schema_gaps(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table quality_edge (
                report_date varchar,
                natural_key varchar,
                metric_text varchar,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into quality_edge values (?, ?, ?, ?, ?)",
            [
                ("2026-05-31", "row-1", "", "sv", "rv"),
                ("2026-05-31", "row-2", "not-a-number", "sv", "rv"),
            ],
        )
    finally:
        conn.close()

    report = build_data_readiness_report(
        duckdb_path,
        specs=[
            TableSpec(
                label="quality edge",
                table="quality_edge",
                date_column="report_date",
                unique_key_columns=("report_date", "missing_key"),
                required_data_columns=("missing_required",),
                numeric_range_checks=(
                    NumericRangeCheck("missing_numeric", min_value=0, allow_null=False),
                    NumericRangeCheck("metric_text", min_value=0, allow_null=False),
                ),
            )
        ],
        as_of_date="2026-06-08",
    )

    assert report["status"] == "block"
    issue_codes = {issue["code"] for issue in report["issues"]}
    assert {
        "unique_key_column_missing",
        "required_data_column_missing",
        "numeric_column_missing",
        "numeric_value_missing",
        "numeric_value_not_parseable",
    }.issubset(issue_codes)


def test_default_specs_include_stock_and_bond_specialized_quality_dimensions() -> None:
    specs_by_table = {spec.table: spec for spec in DEFAULT_TABLE_SPECS}

    stock = specs_by_table["choice_stock_daily_observation"]
    assert stock.scope == "analytical"
    assert stock.unique_key_columns == ("trade_date", "stock_code")
    assert "stock_code" in stock.required_data_columns
    assert any(check.column == "close_value" for check in stock.numeric_range_checks)

    gate = specs_by_table["fact_livermore_gate_supplement_daily"]
    assert gate.unique_key_columns == ("trade_date",)
    assert any(check.column == "breadth_5d" for check in gate.numeric_range_checks)

    positions = specs_by_table["livermore_position_snapshot"]
    assert positions.scope == "observational"
    assert positions.unique_key_columns == ("as_of_date", "stock_code", "position_status")
    assert "position_status" in positions.required_data_columns

    candidates = specs_by_table["livermore_candidate_history"]
    assert candidates.scope == "observational"
    assert candidates.unique_key_columns == ("snapshot_as_of_date", "stock_code", "signal_kind")
    assert "data_status" in candidates.required_data_columns

    bonds = specs_by_table["fact_formal_bond_analytics_daily"]
    assert bonds.unique_key_columns == (
        "report_date",
        "instrument_code",
        "portfolio_name",
        "accounting_class",
        "trace_id",
    )
    assert bonds.required_data_columns == ("instrument_code", "accounting_class", "currency_code")
    assert any(check.column == "ytm" for check in bonds.numeric_range_checks)

    curves = specs_by_table["fact_formal_yield_curve_daily"]
    assert curves.unique_key_columns == ("trade_date", "curve_type", "tenor")
    assert any(check.column == "rate_pct" for check in curves.numeric_range_checks)
