from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from backend.app.governance.settings import Settings
from backend.app.repositories.accounting_asset_movement_repo import (
    AccountingAssetMovementRepository,
)
from backend.app.schemas.accounting_asset_movement import (
    AccountingBusinessMovementRowPayload,
    AccountingBusinessMovementTrendMonthPayload,
    AccountingAssetMovementDatesPayload,
    AccountingAssetMovementPayload,
    AccountingAssetMovementRefreshPayload,
    AccountingAssetMovementRowPayload,
    AccountingAssetMovementSummaryPayload,
    AccountingAssetMovementTrendMonthPayload,
)
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)
from backend.app.tasks.accounting_asset_movement import (
    RULE_VERSION,
    _materialize_accounting_asset_movement,
)

CACHE_VERSION = "cv_accounting_asset_movement_v1"
CONTROL_ACCOUNTS = ["141%", "142%", "143%", "1440101%"]
EXCLUDED_CONTROLS = ["144020%"]


class AccountingAssetMovementReadModelNotFoundError(LookupError):
    pass


def accounting_asset_movement_dates_envelope(
    duckdb_path: str,
    *,
    currency_basis: str = "CNX",
) -> dict[str, object]:
    repo = AccountingAssetMovementRepository(duckdb_path)
    payload = AccountingAssetMovementDatesPayload(
        report_dates=repo.list_report_dates(currency_basis=currency_basis),
        currency_basis=currency_basis,
    )
    meta = build_formal_result_meta(
        trace_id="tr_balance_movement_dates",
        result_kind="balance-analysis.movement.dates",
        source_version=repo.latest_source_version(currency_basis=currency_basis),
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        filters_applied={"currency_basis": currency_basis},
        tables_used=["fact_accounting_asset_movement_monthly"],
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )


def accounting_asset_movement_envelope(
    duckdb_path: str,
    *,
    report_date: str,
    currency_basis: str = "CNX",
) -> dict[str, object]:
    repo = AccountingAssetMovementRepository(duckdb_path)
    rows_without_pct = [
        AccountingAssetMovementRowPayload.model_validate(row)
        for row in repo.fetch_rows(report_date=report_date, currency_basis=currency_basis)
    ]
    if not rows_without_pct:
        raise AccountingAssetMovementReadModelNotFoundError(
            f"No balance movement rows for report_date={report_date}, currency_basis={currency_basis}."
        )
    rows = _with_balance_percentages(rows_without_pct)
    trend_months = _build_trend_months(
        repo.fetch_recent_rows(
            report_date=report_date,
            currency_basis=currency_basis,
            month_count=6,
        )
    )
    business_trend_months = _build_business_trend_months(
        repo.fetch_recent_business_rows(
            report_date=report_date,
            currency_basis=currency_basis,
            month_count=6,
        )
    )
    evidence_rows = [row for month in trend_months for row in month.rows] or rows
    business_evidence_rows = [
        row for month in business_trend_months for row in month.rows
    ]

    payload = AccountingAssetMovementPayload(
        report_date=report_date,
        currency_basis=currency_basis,
        rows=rows,
        summary=_build_summary(rows),
        trend_months=trend_months,
        business_trend_months=business_trend_months,
        accounting_controls=CONTROL_ACCOUNTS,
        excluded_controls=EXCLUDED_CONTROLS,
    )
    meta = build_formal_result_meta(
        trace_id=f"tr_balance_movement_{report_date}_{currency_basis}",
        result_kind="balance-analysis.movement.detail",
        source_version=_joined_latest(
            row.source_version for row in [*evidence_rows, *business_evidence_rows]
        ),
        rule_version=_joined_latest(
            row.rule_version for row in [*evidence_rows, *business_evidence_rows]
        )
        or RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="ok",
        filters_applied={"report_date": report_date, "currency_basis": currency_basis},
        tables_used=[
            "fact_accounting_asset_movement_monthly",
            "product_category_pnl_canonical_fact",
            "fact_formal_zqtz_balance_daily",
        ],
        evidence_rows=len(evidence_rows)
        + sum(len(month.rows) for month in business_trend_months),
        next_drill=[
            "product_category_pnl_canonical_fact: CNX 141/142/143/1440101 control accounts",
            "product_category_pnl_canonical_fact: CNX ZQTZ diagnostic bucket comparison; not a CNY fallback",
            "product_category_pnl_canonical_fact: interbank asset/liability business rows from ledger balances",
            "fact_formal_zqtz_balance_daily: asset-side NCD from ZQTZSHOW business type 1",
        ],
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )


def refresh_accounting_asset_movement(
    settings: Settings,
    *,
    report_date: str,
    currency_basis: str = "CNX",
) -> dict[str, object]:
    payload = _materialize_accounting_asset_movement(
        report_date=report_date,
        duckdb_path=str(settings.duckdb_path),
        currency_basis=currency_basis,
    )
    return AccountingAssetMovementRefreshPayload.model_validate(payload).model_dump(mode="json")


def _build_summary(
    rows: list[AccountingAssetMovementRowPayload],
) -> AccountingAssetMovementSummaryPayload:
    return AccountingAssetMovementSummaryPayload(
        previous_balance_total=sum((row.previous_balance for row in rows), Decimal("0")),
        current_balance_total=sum((row.current_balance for row in rows), Decimal("0")),
        balance_change_total=sum((row.balance_change for row in rows), Decimal("0")),
        zqtz_amount_total=sum((row.zqtz_amount for row in rows), Decimal("0")),
        reconciliation_diff_total=sum(
            (row.reconciliation_diff for row in rows),
            Decimal("0"),
        ),
        matched_bucket_count=sum(1 for row in rows if row.reconciliation_status == "matched"),
        bucket_count=len(rows),
    )


def _with_balance_percentages(
    rows: list[AccountingAssetMovementRowPayload],
) -> list[AccountingAssetMovementRowPayload]:
    previous_total = sum((row.previous_balance for row in rows), Decimal("0"))
    current_total = sum((row.current_balance for row in rows), Decimal("0"))
    return [
        row.model_copy(
            update={
                "previous_balance_pct": _pct(row.previous_balance, previous_total),
                "current_balance_pct": _pct(row.current_balance, current_total),
            },
        )
        for row in rows
    ]


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == Decimal("0"):
        return None
    return numerator / denominator * Decimal("100")


def _build_trend_months(
    raw_rows: list[dict[str, object]],
) -> list[AccountingAssetMovementTrendMonthPayload]:
    grouped: dict[str, list[AccountingAssetMovementRowPayload]] = {}
    for raw_row in raw_rows:
        row = AccountingAssetMovementRowPayload.model_validate(raw_row)
        grouped.setdefault(row.report_date, []).append(row)

    trend_months: list[AccountingAssetMovementTrendMonthPayload] = []
    for report_date in sorted(grouped.keys(), reverse=True):
        rows = _with_balance_percentages(
            sorted(grouped[report_date], key=lambda row: row.sort_order)
        )
        trend_months.append(
            AccountingAssetMovementTrendMonthPayload(
                report_date=report_date,
                report_month=rows[0].report_month,
                current_balance_total=sum(
                    (row.current_balance for row in rows),
                    Decimal("0"),
                ),
                balance_change_total=sum(
                    (row.balance_change for row in rows),
                    Decimal("0"),
                ),
                rows=rows,
            )
        )
    return trend_months


def _build_business_trend_months(
    raw_rows: list[dict[str, object]],
) -> list[AccountingBusinessMovementTrendMonthPayload]:
    grouped: dict[str, list[AccountingBusinessMovementRowPayload]] = {}
    for raw_row in raw_rows:
        row = AccountingBusinessMovementRowPayload.model_validate(raw_row)
        grouped.setdefault(row.report_date, []).append(row)

    trend_months: list[AccountingBusinessMovementTrendMonthPayload] = []
    for report_date in sorted(grouped.keys(), reverse=True):
        rows = sorted(grouped[report_date], key=lambda row: row.sort_order)
        asset_total = sum(
            (row.current_balance for row in rows if row.side == "asset"),
            Decimal("0"),
        )
        liability_total = sum(
            (row.current_balance for row in rows if row.side == "liability"),
            Decimal("0"),
        )
        trend_months.append(
            AccountingBusinessMovementTrendMonthPayload(
                report_date=report_date,
                report_month=rows[0].report_month,
                asset_balance_total=asset_total,
                liability_balance_total=liability_total,
                net_balance_total=asset_total + liability_total,
                rows=rows,
            )
        )
    return trend_months


def _joined_latest(values: Iterable[object]) -> str:
    unique: list[str] = []
    for value in values:
        for token in str(value or "").split("__"):
            normalized = token.strip()
            if normalized and normalized not in unique:
                unique.append(normalized)
    return "__".join(unique)
