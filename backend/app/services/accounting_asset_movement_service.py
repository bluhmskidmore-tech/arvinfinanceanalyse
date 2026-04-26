from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from backend.app.governance.settings import Settings
from backend.app.repositories.accounting_asset_movement_repo import (
    AccountingAssetMovementRepository,
)
from backend.app.schemas.accounting_asset_movement import (
    AccountingAssetMovementDatesPayload,
    AccountingAssetMovementPayload,
    AccountingAssetMovementRefreshPayload,
    AccountingAssetMovementRowPayload,
    AccountingAssetMovementSummaryPayload,
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
        source_version=repo.latest_source_version(),
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        filters_applied={"currency_basis": currency_basis},
        tables_used=[
            "product_category_pnl_canonical_fact",
            "fact_accounting_asset_movement_monthly",
        ],
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
    rows = [
        AccountingAssetMovementRowPayload.model_validate(row)
        for row in repo.fetch_rows(report_date=report_date, currency_basis=currency_basis)
    ]
    if not rows:
        raise AccountingAssetMovementReadModelNotFoundError(
            f"No balance movement rows for report_date={report_date}, currency_basis={currency_basis}."
        )

    payload = AccountingAssetMovementPayload(
        report_date=report_date,
        currency_basis=currency_basis,
        rows=rows,
        summary=_build_summary(rows),
        accounting_controls=CONTROL_ACCOUNTS,
        excluded_controls=EXCLUDED_CONTROLS,
    )
    meta = build_formal_result_meta(
        trace_id=f"tr_balance_movement_{report_date}_{currency_basis}",
        result_kind="balance-analysis.movement.detail",
        source_version=_joined_latest(row.source_version for row in rows),
        rule_version=_joined_latest(row.rule_version for row in rows) or RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="warning"
        if any(row.reconciliation_status != "matched" for row in rows)
        else "ok",
        filters_applied={"report_date": report_date, "currency_basis": currency_basis},
        tables_used=["fact_accounting_asset_movement_monthly"],
        evidence_rows=len(rows),
        next_drill=[
            "product_category_pnl_canonical_fact: CNX 141/142/143/1440101 control accounts",
            "fact_formal_zqtz_balance_daily: CNY auxiliary detail comparison",
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


def _joined_latest(values: Iterable[object]) -> str:
    unique: list[str] = []
    for value in values:
        for token in str(value or "").split("__"):
            normalized = token.strip()
            if normalized and normalized not in unique:
                unique.append(normalized)
    return "__".join(unique)
