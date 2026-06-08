from __future__ import annotations

from pathlib import Path

import duckdb

from scripts.data_readiness_report import (
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
