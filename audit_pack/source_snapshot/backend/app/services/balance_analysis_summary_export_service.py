from __future__ import annotations

import csv
from decimal import Decimal
from io import StringIO
from typing import Any, Literal

from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.schemas.balance_analysis import BalanceAnalysisTableRow


def export_balance_analysis_summary_csv(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"],
    currency_basis: Literal["native", "CNY"],
    cache_key: str,
    job_name: str,
    validate_filters_fn: Any,
    require_lineage_value_fn: Any,
    resolve_completed_formal_build_lineage_fn: Any,
    repo_cls: type[Any] = BalanceAnalysisRepository,
) -> tuple[str, str]:
    validate_filters_fn(
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    repo = repo_cls(duckdb_path)
    if report_date not in repo.list_report_dates():
        raise ValueError(f"No balance-analysis data found for report_date={report_date}.")

    table = repo.fetch_formal_summary_table(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
        limit=None,
        offset=0,
    )
    build_lineage = resolve_completed_formal_build_lineage_fn(
        governance_dir=governance_dir,
        cache_key=cache_key,
        job_name=job_name,
        report_date=report_date,
    )
    source_version = require_lineage_value_fn(
        build_lineage["source_version"] if build_lineage is not None else None,
        report_date=report_date,
        field_name="source_version",
    )
    rule_version = require_lineage_value_fn(
        build_lineage["rule_version"] if build_lineage is not None else None,
        report_date=report_date,
        field_name="rule_version",
    )
    rows = [_to_summary_table_row(row) for row in table["rows"]]
    filename = f"balance-analysis-summary-{report_date}-{position_scope}-{currency_basis}.csv"
    return filename, _build_balance_summary_csv(
        rows,
        report_date=report_date,
        source_version=source_version,
        rule_version=rule_version,
    )


def _to_summary_table_row(row: dict[str, object]) -> BalanceAnalysisTableRow:
    return BalanceAnalysisTableRow(
        row_key=str(row["row_key"]),
        source_family=str(row["source_family"]),
        display_name=str(row["display_name"]),
        owner_name=str(row["owner_name"]),
        category_name=str(row["category_name"]),
        position_scope=str(row["position_scope"]),
        currency_basis=str(row["currency_basis"]),
        invest_type_std=str(row["invest_type_std"]),
        accounting_basis=str(row["accounting_basis"]),
        detail_row_count=int(str(row["detail_row_count"])),
        market_value_amount=_as_decimal(row["market_value_amount"]),
        amortized_cost_amount=_as_decimal(row["amortized_cost_amount"]),
        accrued_interest_amount=_as_decimal(row["accrued_interest_amount"]),
    )


def _build_balance_summary_csv(
    rows: list[BalanceAnalysisTableRow],
    *,
    report_date: str,
    source_version: str,
    rule_version: str,
) -> str:
    output = StringIO()
    fieldnames = [
        "row_key",
        "source_family",
        "display_name",
        "owner_name",
        "category_name",
        "position_scope",
        "currency_basis",
        "invest_type_std",
        "accounting_basis",
        "detail_row_count",
        "market_value_amount",
        "amortized_cost_amount",
        "accrued_interest_amount",
        "report_date",
        "source_version",
        "rule_version",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                **row.model_dump(mode="json"),
                "report_date": report_date,
                "source_version": source_version,
                "rule_version": rule_version,
            }
        )
    return output.getvalue()


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
