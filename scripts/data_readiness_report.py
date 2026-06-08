from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUCKDB_PATH = ROOT / "data" / "moss.duckdb"
DEFAULT_TARGET_LATEST_DATE = "2026-05-31"
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_ISSUE_SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class TableSpec:
    label: str
    table: str
    date_column: str
    scope: str = "formal"
    required_meta_columns: tuple[str, ...] = ("source_version", "rule_version")
    target_latest_date: str | None = None
    target_max_lag_days: int | None = None
    latest_min_rows: int | None = None
    allow_empty: bool = False


DEFAULT_TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        label="formal balance zqtz",
        table="fact_formal_zqtz_balance_daily",
        date_column="report_date",
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="formal balance tyw",
        table="fact_formal_tyw_balance_daily",
        date_column="report_date",
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="formal bond analytics",
        table="fact_formal_bond_analytics_daily",
        date_column="report_date",
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="formal risk tensor",
        table="fact_formal_risk_tensor_daily",
        date_column="report_date",
        required_meta_columns=("source_version", "rule_version", "cache_version", "quality_flag"),
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="formal PnL FI",
        table="fact_formal_pnl_fi",
        date_column="report_date",
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="PnL bridge non-standard",
        table="fact_nonstd_pnl_bridge",
        date_column="report_date",
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="product category canonical",
        table="product_category_pnl_canonical_fact",
        date_column="report_date",
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="product category formal read",
        table="product_category_pnl_formal_read_model",
        date_column="report_date",
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="product category scenario read",
        table="product_category_pnl_scenario_read_model",
        date_column="report_date",
        scope="scenario",
        allow_empty=True,
    ),
    TableSpec(
        label="formal yield curve",
        table="fact_formal_yield_curve_daily",
        date_column="trade_date",
        required_meta_columns=("source_version", "rule_version", "vendor_version"),
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
        target_max_lag_days=3,
    ),
    TableSpec(
        label="formal FX mid",
        table="fx_daily_mid",
        date_column="trade_date",
        scope="formal",
        required_meta_columns=("source_version", "vendor_version"),
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="accounting asset movement",
        table="fact_accounting_asset_movement_monthly",
        date_column="report_date",
        target_latest_date=DEFAULT_TARGET_LATEST_DATE,
    ),
    TableSpec(
        label="ledger position snapshot",
        table="position_snapshot",
        date_column="as_of_date",
        scope="candidate",
    ),
    TableSpec(
        label="ledger position aggregate",
        table="position_snapshot_agg",
        date_column="as_of_date",
        scope="candidate",
    ),
    TableSpec(
        label="choice stock daily observation",
        table="choice_stock_daily_observation",
        date_column="trade_date",
        scope="analytical",
        required_meta_columns=("source_version", "rule_version", "vendor_version"),
    ),
    TableSpec(
        label="choice macro daily",
        table="fact_choice_macro_daily",
        date_column="trade_date",
        scope="analytical",
        required_meta_columns=("source_version", "rule_version", "vendor_version", "quality_flag"),
    ),
    TableSpec(
        label="choice news events",
        table="choice_news_event",
        date_column="received_at",
        scope="analytical",
        required_meta_columns=(),
    ),
    TableSpec(
        label="news warehouse",
        table="fact_news_event",
        date_column="pub_time",
        scope="analytical",
        required_meta_columns=(),
    ),
    TableSpec(
        label="commodity futures daily",
        table="fact_commodity_futures_daily",
        date_column="trade_date",
        scope="analytical",
        required_meta_columns=("source_version", "rule_version", "vendor_version"),
    ),
    TableSpec(
        label="source preview summary",
        table="phase1_source_preview_summary",
        date_column="report_date",
        scope="preview",
    ),
)


def build_data_readiness_report(
    duckdb_path: str | Path,
    *,
    specs: tuple[TableSpec, ...] | list[TableSpec] = DEFAULT_TABLE_SPECS,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    path = Path(duckdb_path)
    report_as_of = as_of_date or date.today().isoformat()
    if not path.is_file():
        issue = _issue(
            "duckdb_unavailable",
            "block",
            "DuckDB file does not exist.",
            table=None,
            details={"duckdb_path": str(path)},
        )
        return _report(path, report_as_of, [], [issue])

    try:
        import duckdb

        conn = duckdb.connect(str(path), read_only=True)
    except Exception as exc:  # pragma: no cover - exact driver failure varies by platform.
        issue = _issue(
            "duckdb_unavailable",
            "block",
            "Could not open DuckDB read-only.",
            table=None,
            details={"duckdb_path": str(path), "error": f"{type(exc).__name__}: {exc}"},
        )
        return _report(path, report_as_of, [], [issue])

    try:
        table_reports = [_inspect_table(conn, spec, report_as_of) for spec in specs]
    finally:
        conn.close()

    issues = [issue for table in table_reports for issue in table["issues"] if issue["severity"] == "block"]
    return _report(path, report_as_of, table_reports, issues)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MOSS Data Readiness Report",
        "",
        f"- Status: {report['status']}",
        f"- DuckDB: `{report['duckdb_path']}`",
        f"- As of: {report['as_of_date']}",
        f"- Blocking issues: {report['summary']['blocking_issue_count']}",
        "",
        "| Scope | Table | Rows | Latest | Status | Issues |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for table in report["tables"]:
        issue_codes = "<br>".join(_issue_markdown_summary(issue) for issue in table["issues"]) or "-"
        latest = table.get("date_coverage", {}).get("max") or "-"
        lines.append(
            f"| {table['scope']} | `{table['table']}` | {table['row_count']} | {latest} | "
            f"{table['status']} | {issue_codes} |"
        )

    if report["issues"]:
        lines.extend(["", "## Blocking Issues", ""])
        for issue in report["issues"]:
            table = issue.get("table") or "global"
            lines.append(f"- `{issue['code']}` on `{table}`: {issue['message']}")

    return "\n".join(lines) + "\n"


def _inspect_table(conn: Any, spec: TableSpec, as_of_date: str) -> dict[str, Any]:
    if not _table_exists(conn, spec.table):
        issue = _issue(
            "table_missing",
            "block",
            "Configured readiness table is missing.",
            table=spec.table,
            details={"label": spec.label},
        )
        return _table_report(spec, row_count=0, date_coverage={}, latest_row_count=None, issues=[issue])

    columns = _columns(conn, spec.table)
    issues: list[dict[str, Any]] = []
    row_count = _row_count(conn, spec.table)
    if row_count == 0:
        severity = "observe" if spec.allow_empty else "block"
        issues.append(
            _issue(
                "allowed_empty_table" if spec.allow_empty else "table_empty",
                severity,
                "Table is empty.",
                table=spec.table,
                details={"scope": spec.scope},
            )
        )

    date_coverage: dict[str, Any] = {}
    latest_row_count: int | None = None
    if spec.date_column not in columns:
        issues.append(
            _issue(
                "date_column_missing",
                "block",
                "Configured date column is missing.",
                table=spec.table,
                details={"date_column": spec.date_column},
            )
        )
    elif row_count > 0:
        date_coverage = _date_coverage(conn, spec.table, spec.date_column)
        latest_value = date_coverage.get("max")
        latest_row_count = _latest_row_count(conn, spec.table, spec.date_column, latest_value)
        target_latest = spec.target_latest_date
        if target_latest and latest_value and _compare_date_strings(latest_value, target_latest) < 0:
            lag_days = _date_lag_days(latest_value, target_latest)
            if spec.target_max_lag_days is not None and lag_days is not None and lag_days <= spec.target_max_lag_days:
                issues.append(
                    _issue(
                        "latest_date_within_allowed_lag",
                        "observe",
                        "Latest available date is before target but within the configured lag allowance.",
                        table=spec.table,
                        details=_allowed_lag_details(latest_value, target_latest, lag_days, spec.target_max_lag_days),
                    )
                )
            else:
                issues.append(
                    _issue(
                        "latest_date_before_target",
                        "block",
                        "Latest available date is before the target latest date.",
                        table=spec.table,
                        details={"latest": latest_value, "target": target_latest},
                    )
                )
        if spec.latest_min_rows is not None and latest_row_count < spec.latest_min_rows:
            issues.append(
                _issue(
                    "latest_rows_below_min",
                    "block",
                    "Latest date row count is below the configured minimum.",
                    table=spec.table,
                    details={"latest_rows": latest_row_count, "minimum": spec.latest_min_rows},
                )
            )
        issues.extend(_date_value_issues(conn, spec, as_of_date))

    for column in spec.required_meta_columns:
        if column not in columns:
            issues.append(
                _issue(
                    "metadata_column_missing",
                    "block",
                    "Required metadata column is missing.",
                    table=spec.table,
                    details={"column": column},
                )
            )
            continue
        missing_count = _missing_value_count(conn, spec.table, column)
        if missing_count:
            issues.append(
                _issue(
                    "metadata_value_missing",
                    "block",
                    "Required metadata column has blank or null values.",
                    table=spec.table,
                    details={"column": column, "missing_count": missing_count},
                )
            )

    return _table_report(
        spec,
        row_count=row_count,
        date_coverage=date_coverage,
        latest_row_count=latest_row_count,
        issues=issues,
    )


def _date_value_issues(conn: Any, spec: TableSpec, as_of_date: str) -> list[dict[str, Any]]:
    values = _distinct_date_values(conn, spec.table, spec.date_column)
    as_of = _parse_date(as_of_date)
    non_iso_values: list[str] = []
    future_values: list[str] = []
    for value in values:
        parsed = _parse_date(value)
        if parsed is None:
            non_iso_values.append(value)
            continue
        if as_of is not None and parsed > as_of:
            future_values.append(value)

    issues: list[dict[str, Any]] = []
    if non_iso_values:
        issues.append(
            _issue(
                "non_iso_date_values",
                "block",
                "Date column contains values that cannot be interpreted as ISO dates.",
                table=spec.table,
                details={
                    "date_column": spec.date_column,
                    "count": len(non_iso_values),
                    "sample_values": non_iso_values[:DATE_ISSUE_SAMPLE_LIMIT],
                },
            )
        )
    if future_values:
        issues.append(
            _issue(
                "future_date_values",
                "block",
                "Date column contains values later than the report as-of date.",
                table=spec.table,
                details={
                    "date_column": spec.date_column,
                    "as_of_date": as_of_date,
                    "count": len(future_values),
                    "min_value": future_values[0],
                    "max_value": future_values[-1],
                    "sample_values": future_values[:DATE_ISSUE_SAMPLE_LIMIT],
                },
            )
        )
    return issues


def _report(
    duckdb_path: Path,
    as_of_date: str,
    table_reports: list[dict[str, Any]],
    blocking_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "block" if blocking_issues else "pass",
        "duckdb_path": str(duckdb_path),
        "as_of_date": as_of_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "table_count": len(table_reports),
            "blocking_issue_count": len(blocking_issues),
        },
        "tables": table_reports,
        "issues": blocking_issues,
    }


def _table_report(
    spec: TableSpec,
    *,
    row_count: int,
    date_coverage: dict[str, Any],
    latest_row_count: int | None,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    blocking = any(issue["severity"] == "block" for issue in issues)
    observing = any(issue["severity"] == "observe" for issue in issues)
    status = "block" if blocking else "observe" if observing else "pass"
    return {
        "label": spec.label,
        "table": spec.table,
        "scope": spec.scope,
        "status": status,
        "row_count": row_count,
        "date_column": spec.date_column,
        "date_coverage": date_coverage,
        "latest_row_count": latest_row_count,
        "required_meta_columns": list(spec.required_meta_columns),
        "allow_empty": spec.allow_empty,
        "issues": issues,
    }


def _issue(
    code: str,
    severity: str,
    message: str,
    *,
    table: str | None,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "table": table,
        "message": message,
        "details": details,
    }


def _issue_markdown_summary(issue: dict[str, Any]) -> str:
    details = issue.get("details", {})
    if details.get("calendar_gap_reason") == "target_window_non_business_days":
        gap_dates = ", ".join(details.get("gap_dates", []))
        previous_business_day = details.get("latest_business_date", "-")
        return (
            f"{issue['code']} ({details['calendar_gap_reason']}; "
            f"gap dates: {gap_dates}; previous business day: {previous_business_day})"
        )
    return issue["code"]


def _table_exists(conn: Any, table: str) -> bool:
    schema, bare = _split_table_name(table)
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = ? and table_name = ?
        limit 1
        """,
        [schema, bare],
    ).fetchone()
    return row is not None


def _columns(conn: Any, table: str) -> set[str]:
    schema, bare = _split_table_name(table)
    rows = conn.execute(
        """
        select column_name
        from information_schema.columns
        where table_schema = ? and table_name = ?
        """,
        [schema, bare],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _row_count(conn: Any, table: str) -> int:
    return int(conn.execute(f"select count(*) from {_quote_table(table)}").fetchone()[0])


def _date_coverage(conn: Any, table: str, column: str) -> dict[str, Any]:
    quoted_column = _quote_identifier(column)
    row = conn.execute(
        f"""
        select
            cast(min({quoted_column}) as varchar),
            cast(max({quoted_column}) as varchar),
            count(distinct {quoted_column}) filter (where {quoted_column} is not null),
            sum(case when {quoted_column} is null then 1 else 0 end)
        from {_quote_table(table)}
        """
    ).fetchone()
    return {
        "min": row[0],
        "max": row[1],
        "distinct_non_null_count": int(row[2] or 0),
        "null_count": int(row[3] or 0),
    }


def _latest_row_count(conn: Any, table: str, column: str, latest_value: Any) -> int | None:
    if latest_value is None:
        return None
    return int(
        conn.execute(
            f"select count(*) from {_quote_table(table)} where {_quote_identifier(column)} = ?",
            [latest_value],
        ).fetchone()[0]
    )


def _distinct_date_values(conn: Any, table: str, column: str) -> list[str]:
    rows = conn.execute(
        f"""
        select distinct cast({_quote_identifier(column)} as varchar) as value
        from {_quote_table(table)}
        where {_quote_identifier(column)} is not null
        order by value
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def _missing_value_count(conn: Any, table: str, column: str) -> int:
    return int(
        conn.execute(
            f"""
            select sum(
                case
                    when {_quote_identifier(column)} is null
                      or trim(cast({_quote_identifier(column)} as varchar)) = ''
                    then 1
                    else 0
                end
            )
            from {_quote_table(table)}
            """
        ).fetchone()[0]
        or 0
    )


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    candidate = text[:10]
    if not ISO_DATE_RE.match(candidate):
        return None
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        return None


def _compare_date_strings(left: str, right: str) -> int:
    left_date = _parse_date(left)
    right_date = _parse_date(right)
    if left_date is None or right_date is None:
        return 0
    return (left_date > right_date) - (left_date < right_date)


def _date_lag_days(left: str, right: str) -> int | None:
    left_date = _parse_date(left)
    right_date = _parse_date(right)
    if left_date is None or right_date is None:
        return None
    return (right_date - left_date).days


def _allowed_lag_details(latest: str, target: str, lag_days: int, max_lag_days: int) -> dict[str, Any]:
    details: dict[str, Any] = {
        "latest": latest,
        "target": target,
        "lag_days": lag_days,
        "max_lag_days": max_lag_days,
    }
    gap_dates = _date_gap_dates(latest, target)
    non_business_dates = [day for day in gap_dates if _is_weekend(day)]
    if gap_dates and len(non_business_dates) == len(gap_dates):
        details.update(
            {
                "calendar_gap_reason": "target_window_non_business_days",
                "gap_dates": [day.isoformat() for day in gap_dates],
                "non_business_dates": [day.isoformat() for day in non_business_dates],
                "latest_business_date": latest,
            }
        )
    return details


def _date_gap_dates(left: str, right: str) -> list[date]:
    left_date = _parse_date(left)
    right_date = _parse_date(right)
    if left_date is None or right_date is None or left_date >= right_date:
        return []
    days = (right_date - left_date).days
    return [left_date + timedelta(days=offset) for offset in range(1, days + 1)]


def _is_weekend(value: date) -> bool:
    return value.weekday() >= 5


def _split_table_name(table: str) -> tuple[str, str]:
    parts = table.split(".")
    if len(parts) == 1:
        return "main", parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    raise ValueError(f"Unsupported table name: {table}")


def _quote_table(table: str) -> str:
    return ".".join(_quote_identifier(part) for part in _split_table_name(table))


def _quote_identifier(value: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        raise ValueError(f"Unsafe identifier: {value}")
    return f'"{value}"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only MOSS DuckDB data readiness report.")
    parser.add_argument("--duckdb-path", default=str(DEFAULT_DUCKDB_PATH))
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--json-output", default="")
    parser.add_argument("--markdown-output", default="")
    args = parser.parse_args(argv)

    report = build_data_readiness_report(args.duckdb_path, as_of_date=args.as_of_date)
    json_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    markdown_text = render_markdown(report)

    if args.json_output:
        Path(args.json_output).write_text(json_text, encoding="utf-8")
    if args.markdown_output:
        Path(args.markdown_output).write_text(markdown_text, encoding="utf-8")

    sys.stdout.write(json_text if args.format == "json" else markdown_text)
    return 1 if report["status"] == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
