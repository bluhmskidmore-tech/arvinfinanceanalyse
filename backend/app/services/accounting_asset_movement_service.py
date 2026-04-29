from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
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
    AccountingAssetMovementTrendMonthPayload,
    AccountingBasisMovementBucketPayload,
    AccountingBasisMovementComponentPayload,
    AccountingBasisMovementDecompositionPayload,
    AccountingBusinessMovementRowPayload,
    AccountingBusinessMovementTrendMonthPayload,
    AccountingDifferenceAttributionComponentPayload,
    AccountingDifferenceAttributionWaterfallPayload,
    AccountingDrilldownMetaPayload,
    AccountingStructureMigrationAnalysisPayload,
    AccountingStructureMigrationBucketPayload,
    AccountingStructureMigrationPairPayload,
    AccountingZqtzCalibrationAnalysisPayload,
    AccountingZqtzCalibrationItemPayload,
    AccountingZqtzConcentrationAnalysisPayload,
    AccountingZqtzConcentrationDimensionPayload,
    AccountingZqtzConcentrationItemPayload,
    AccountingZqtzMaturityBucketPayload,
    AccountingZqtzMaturityStructurePayload,
)
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)
from backend.app.tasks.accounting_asset_movement import (
    CACHE_KEY,
    RULE_VERSION,
    materialize_accounting_asset_movement_on_connection,
)
from backend.app.tasks.formal_balance_pipeline import run_formal_balance_pipeline
from backend.app.tasks.product_category_pnl import materialize_product_category_pnl

CACHE_VERSION = "cv_accounting_asset_movement_v1"
CONTROL_ACCOUNTS = ["141%", "142%", "143%", "1440101%"]
EXCLUDED_CONTROLS = ["144020%"]
REFRESH_MONTH_COUNT = 6
CONCENTRATION_DIMENSIONS = ("issuer_name", "rating", "industry_name")
CONCENTRATION_TOP_N = 10
CONCENTRATION_COVERAGE_THRESHOLD = Decimal("80")
INTEREST_RATE_BOND_DEFAULT_RATING = "AAA"
INTEREST_RATE_BOND_KEYWORDS = (
    "央行票据",
    "央票",
    "记账式国债",
    "凭证式国债",
    "国债",
    "地方政府债",
    "地方债",
    "地方政府债券",
    "政策性金融债",
    "政策性银行债",
    "政金债",
)
INTEREST_RATE_BOND_EXCLUDE_KEYWORDS = ("外国债", "外债")
INTEREST_RATE_BOND_DESCRIPTOR_FIELDS = (
    "bond_type",
    "business_type_primary",
    "business_type_final",
    "sub_type",
    "instrument_name",
)
MATURITY_BUCKETS = (
    ("overdue_or_matured", "已到期/逾期"),
    ("<=30d", "30天内"),
    ("31-90d", "31-90天"),
    ("91d-1y", "91天-1年"),
    ("1-3y", "1-3年"),
    ("3-5y", "3-5年"),
    (">5y", "5年以上"),
    ("unknown", "未映射"),
)
ZQTZ228_REFERENCE_AMOUNTS = {
    "asset_zqtz_policy_financial_bond": Decimal("65228031802.46"),
    "asset_zqtz_local_government_bond": Decimal("42264356556.22"),
    "asset_zqtz_foreign_bond": Decimal("496000000.00"),
}


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
    structure_diagnostic_inputs = repo.fetch_structure_diagnostic_inputs(
        report_dates=[month.report_date for month in trend_months],
        currency_basis=currency_basis,
    )
    difference_attribution_inputs = repo.fetch_difference_attribution_inputs(
        report_date=report_date,
        currency_basis=currency_basis,
    )
    prior_report_date = trend_months[1].report_date if len(trend_months) > 1 else None
    basis_components = repo.fetch_basis_movement_components(
        report_date=report_date,
        currency_basis=currency_basis,
    )
    zqtz_drilldown_rows = repo.fetch_zqtz_asset_drilldown_rows(
        report_dates=[date_value for date_value in (report_date, prior_report_date) if date_value],
        currency_basis=currency_basis,
    )

    summary = _build_summary(rows)
    payload = AccountingAssetMovementPayload(
        report_date=report_date,
        currency_basis=currency_basis,
        rows=rows,
        summary=summary,
        trend_months=trend_months,
        business_trend_months=business_trend_months,
        zqtz_calibration_analysis=_build_zqtz_calibration_analysis(
            report_date=report_date,
            business_trend_months=business_trend_months,
        ),
        structure_migration_analysis=_build_structure_migration_analysis(
            trend_months=trend_months,
            diagnostic_inputs=structure_diagnostic_inputs,
        ),
        difference_attribution_waterfall=_build_difference_attribution_waterfall(
            report_date=report_date,
            summary=summary,
            business_trend_months=business_trend_months,
            attribution_inputs=difference_attribution_inputs,
        ),
        basis_movement_decomposition=_build_basis_movement_decomposition(
            report_date=report_date,
            prior_report_date=prior_report_date,
            currency_basis=currency_basis,
            rows=rows,
            component_result=basis_components,
        ),
        zqtz_maturity_structure=_build_zqtz_maturity_structure(
            report_date=report_date,
            prior_report_date=prior_report_date,
            currency_basis=currency_basis,
            drilldown_result=zqtz_drilldown_rows,
        ),
        zqtz_concentration_analysis=_build_zqtz_concentration_analysis(
            report_date=report_date,
            prior_report_date=prior_report_date,
            currency_basis=currency_basis,
            drilldown_result=zqtz_drilldown_rows,
        ),
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
            "fact_formal_zqtz_balance_daily: ZQTZSHOW asset product rows by bond_type / instrument_code prefix",
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
    duckdb_path = str(settings.duckdb_path)
    report_dates = _recent_report_dates_for_refresh(
        duckdb_path,
        report_date=report_date,
        currency_basis=currency_basis,
        month_count=REFRESH_MONTH_COUNT,
    )
    product_category_refreshed_dates = _refresh_missing_product_category_dates(
        settings,
        report_dates=report_dates,
        currency_basis=currency_basis,
    )
    formal_balance_refreshed_dates = _refresh_formal_zqtz_dates(
        settings,
        report_dates=report_dates,
    )

    payloads_by_date = _materialize_accounting_asset_movement_window(
        duckdb_path=duckdb_path,
        report_dates=report_dates,
        currency_basis=currency_basis,
    )
    payload = payloads_by_date[report_date]
    payload["product_category_refreshed_dates"] = product_category_refreshed_dates
    payload["formal_balance_refreshed_dates"] = formal_balance_refreshed_dates
    payload["movement_refreshed_dates"] = report_dates
    return AccountingAssetMovementRefreshPayload.model_validate(payload).model_dump(mode="json")


def _recent_report_dates_for_refresh(
    duckdb_path: str,
    *,
    report_date: str,
    currency_basis: str,
    month_count: int,
) -> list[str]:
    repo = AccountingAssetMovementRepository(duckdb_path)
    report_dates = [
        current_report_date
        for current_report_date in repo.list_report_dates(currency_basis=currency_basis)
        if current_report_date <= report_date
    ][:month_count]
    if report_date not in report_dates:
        report_dates.append(report_date)
    return sorted(set(report_dates))


def _materialize_accounting_asset_movement_window(
    *,
    duckdb_path: str,
    report_dates: list[str],
    currency_basis: str,
) -> dict[str, dict[str, object]]:
    duckdb_file = Path(duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    payloads_by_date: dict[str, dict[str, object]] = {}
    conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        conn.execute("begin transaction")
        for current_report_date in report_dates:
            rows = materialize_accounting_asset_movement_on_connection(
                conn,
                report_date=current_report_date,
                currency_basis=currency_basis,
            )
            source_versions = sorted(
                {
                    token
                    for row in rows
                    for token in row.source_version.split("__")
                    if token
                }
            )
            payloads_by_date[current_report_date] = {
                "status": "completed",
                "cache_key": CACHE_KEY,
                "report_date": current_report_date,
                "currency_basis": currency_basis,
                "row_count": len(rows),
                "source_version": "__".join(source_versions),
                "rule_version": RULE_VERSION,
            }
        conn.execute("commit")
        _checkpoint_if_possible(conn)
    except Exception:
        conn.execute("rollback")
        raise
    finally:
        conn.close()
    return payloads_by_date


def _checkpoint_if_possible(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("checkpoint")
    except duckdb.Error:
        pass


def _connect_for_read_after_refresh(duckdb_path: str) -> duckdb.DuckDBPyConnection:
    try:
        return duckdb.connect(duckdb_path, read_only=True)
    except duckdb.Error as exc:
        if "different configuration" not in str(exc).lower():
            raise
        return duckdb.connect(duckdb_path, read_only=False)


def _refresh_missing_product_category_dates(
    settings: Settings,
    *,
    report_dates: list[str],
    currency_basis: str,
) -> list[str]:
    missing_dates = _missing_product_category_control_dates(
        str(settings.duckdb_path),
        report_dates=report_dates,
        currency_basis=currency_basis,
    )
    if not missing_dates:
        return []

    source_dir = _resolve_refresh_product_category_source_dir(settings, missing_dates)
    if not _has_product_category_sources_for_dates(source_dir, missing_dates):
        joined_dates = ", ".join(missing_dates)
        raise RuntimeError(
            "Cannot refresh accounting asset movement because "
            "product_category_pnl_canonical_fact has no control-account rows "
            f"for {joined_dates}, and no matching product-category source files were found."
        )

    materialize_product_category_pnl.fn(
        duckdb_path=str(settings.duckdb_path),
        source_dir=str(source_dir),
        governance_dir=str(settings.governance_path),
    )

    remaining_dates = _missing_product_category_control_dates(
        str(settings.duckdb_path),
        report_dates=missing_dates,
        currency_basis=currency_basis,
    )
    if remaining_dates:
        joined_dates = ", ".join(remaining_dates)
        raise RuntimeError(
            "Product-category PnL refresh completed but control-account rows "
            f"are still missing for {joined_dates}."
        )
    return missing_dates


def _missing_product_category_control_dates(
    duckdb_path: str,
    *,
    report_dates: list[str],
    currency_basis: str,
) -> list[str]:
    if not report_dates:
        return []
    try:
        conn = _connect_for_read_after_refresh(duckdb_path)
        table_exists = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_name = 'product_category_pnl_canonical_fact'
            limit 1
            """
        ).fetchone()
        if table_exists is None:
            return report_dates
        rows = conn.execute(
            """
            select cast(report_date as varchar) as report_date, count(*) as row_count
            from product_category_pnl_canonical_fact
            where cast(report_date as varchar) in (select unnest(?))
              and currency = ?
              and (
                account_code like '141%'
                or account_code like '142%'
                or account_code like '143%'
                or account_code like '1440101%'
              )
            group by 1
            """,
            [report_dates, currency_basis],
        ).fetchall()
    except duckdb.Error:
        return report_dates
    finally:
        if "conn" in locals():
            conn.close()

    available_dates = {str(row[0]) for row in rows if int(row[1] or 0) > 0}
    return [
        current_report_date
        for current_report_date in report_dates
        if current_report_date not in available_dates
    ]


def _resolve_refresh_product_category_source_dir(
    settings: Settings,
    report_dates: list[str],
) -> Path:
    configured_dir = Path(settings.product_category_source_dir)
    if _has_product_category_sources_for_dates(configured_dir, report_dates):
        return configured_dir

    repo_source_dir = Path(__file__).resolve().parents[3] / "data_input" / configured_dir.name
    if (
        str(settings.environment).lower() == "development"
        and repo_source_dir != configured_dir
        and _has_product_category_sources_for_dates(repo_source_dir, report_dates)
    ):
        return repo_source_dir
    return configured_dir


def _has_product_category_sources_for_dates(
    source_dir: Path,
    report_dates: list[str],
) -> bool:
    if not report_dates or not source_dir.exists():
        return False
    for report_date in report_dates:
        month_token = report_date[:7].replace("-", "")
        if not any(source_dir.glob(f"*{month_token}*.xls*")):
            return False
    return True


def _refresh_formal_zqtz_dates(
    settings: Settings,
    *,
    report_dates: list[str],
) -> list[str]:
    fx_source_path = _resolve_refresh_fx_source_path(settings)
    data_root = _resolve_refresh_data_root(settings, report_dates)
    if not _has_zqtz_sources_for_dates(data_root, report_dates):
        joined_dates = ", ".join(report_dates)
        raise RuntimeError(
            "Cannot refresh formal ZQTZ balances because matching ZQTZSHOW "
            f"source files were not found for {joined_dates}."
        )
    for current_report_date in report_dates:
        run_formal_balance_pipeline.fn(
            report_date=current_report_date,
            data_root=str(data_root),
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            archive_dir=str(settings.local_archive_path),
            fx_source_path=fx_source_path,
        )
    return report_dates


def _resolve_refresh_data_root(settings: Settings, report_dates: list[str]) -> Path:
    configured_root = Path(settings.data_input_root)
    if _has_zqtz_sources_for_dates(configured_root, report_dates):
        return configured_root

    repo_data_input = Path(__file__).resolve().parents[3] / "data_input"
    if (
        str(settings.environment).lower() == "development"
        and repo_data_input != configured_root
        and _has_zqtz_sources_for_dates(repo_data_input, report_dates)
    ):
        return repo_data_input
    return configured_root


def _has_zqtz_sources_for_dates(data_root: Path, report_dates: list[str]) -> bool:
    if not report_dates or not data_root.exists():
        return False
    for report_date in report_dates:
        compact_date = report_date.replace("-", "")
        dotted_date = report_date.replace("-", ".")
        has_source = any(
            any(data_root.glob(pattern))
            for pattern in (
                f"ZQTZSHOW*{compact_date}*.xls",
                f"ZQTZSHOW*{dotted_date}*.xls",
            )
        )
        if not has_source:
            return False
    return True


def _resolve_refresh_fx_source_path(settings: Settings) -> str | None:
    for configured_path in (
        settings.fx_official_source_path,
        settings.fx_mid_csv_path,
    ):
        normalized_path = str(configured_path or "").strip()
        if normalized_path:
            return normalized_path

    default_path = Path(settings.data_input_root) / "fx" / "fx_daily_mid.csv"
    if default_path.exists():
        return str(default_path)
    repo_default_path = Path(__file__).resolve().parents[3] / "data_input" / "fx" / "fx_daily_mid.csv"
    if str(settings.environment).lower() == "development" and repo_default_path.exists():
        return str(repo_default_path)
    return None


def _stale_formal_zqtz_dates(
    duckdb_path: str,
    *,
    report_dates: list[str],
) -> list[str]:
    if not report_dates:
        return []
    try:
        conn = _connect_for_read_after_refresh(duckdb_path)
        rows = conn.execute(
            """
            select
              cast(report_date as varchar) as report_date,
              count(*) as row_count,
              sum(
                case
                  when coalesce(trim(business_type_primary), '') = '' then 1
                  else 0
                end
              ) as empty_business_type_count
            from fact_formal_zqtz_balance_daily
            where cast(report_date as varchar) in (select unnest(?))
              and currency_basis = 'CNY'
              and position_scope = 'asset'
            group by 1
            """,
            [report_dates],
        ).fetchall()
    except duckdb.Error:
        return report_dates
    finally:
        if "conn" in locals():
            conn.close()

    freshness_by_date = {
        str(row[0]): {
            "row_count": int(row[1] or 0),
            "empty_business_type_count": int(row[2] or 0),
        }
        for row in rows
    }
    stale_dates: list[str] = []
    for current_report_date in report_dates:
        freshness = freshness_by_date.get(current_report_date)
        if freshness is None:
            stale_dates.append(current_report_date)
            continue
        row_count = freshness["row_count"]
        if row_count == 0 or freshness["empty_business_type_count"] == row_count:
            stale_dates.append(current_report_date)
    return stale_dates


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


def _build_structure_migration_analysis(
    *,
    trend_months: list[AccountingAssetMovementTrendMonthPayload],
    diagnostic_inputs: dict[str, dict[str, Decimal]],
) -> AccountingStructureMigrationAnalysisPayload | None:
    ordered_months = sorted(trend_months, key=lambda month: month.report_date)
    if len(ordered_months) < 2:
        return None

    pairs: list[AccountingStructureMigrationPairPayload] = []
    for previous_month, current_month in zip(
        ordered_months,
        ordered_months[1:],
        strict=False,
    ):
        buckets: list[AccountingStructureMigrationBucketPayload] = []
        for bucket in ("AC", "OCI", "TPL"):
            previous_row = _trend_row_by_bucket(previous_month, bucket)
            current_row = _trend_row_by_bucket(current_month, bucket)
            previous_balance = (
                previous_row.current_balance if previous_row is not None else Decimal("0")
            )
            current_balance = (
                current_row.current_balance if current_row is not None else Decimal("0")
            )
            previous_share = _pct(previous_balance, previous_month.current_balance_total)
            current_share = _pct(current_balance, current_month.current_balance_total)
            share_delta = (
                current_share - previous_share
                if current_share is not None and previous_share is not None
                else None
            )
            buckets.append(
                AccountingStructureMigrationBucketPayload(
                    basis_bucket=bucket,
                    previous_balance=previous_balance,
                    current_balance=current_balance,
                    balance_delta=current_balance - previous_balance,
                    previous_share_pct=previous_share,
                    current_share_pct=current_share,
                    share_delta_pp=share_delta,
                )
            )

        positive_share_buckets = [
            bucket for bucket in buckets if bucket.share_delta_pp is not None
        ]
        dominant_bucket = None
        if positive_share_buckets:
            dominant = max(
                positive_share_buckets,
                key=lambda bucket: bucket.share_delta_pp or Decimal("0"),
            )
            if (dominant.share_delta_pp or Decimal("0")) > Decimal("0"):
                dominant_bucket = dominant.basis_bucket

        pairs.append(
            AccountingStructureMigrationPairPayload(
                previous_report_date=previous_month.report_date,
                current_report_date=current_month.report_date,
                previous_report_month=previous_month.report_month,
                current_report_month=current_month.report_month,
                total_balance_delta=(
                    current_month.current_balance_total
                    - previous_month.current_balance_total
                ),
                dominant_share_increase_bucket=dominant_bucket,
                fvtpl_volatility_signal=_build_fvtpl_signal(buckets),
                oci_valuation_signal=_build_oci_valuation_signal(
                    previous_month=previous_month,
                    current_month=current_month,
                    diagnostic_inputs=diagnostic_inputs,
                ),
                buckets=buckets,
            )
        )

    latest_pair = pairs[-1]
    dominant_text = latest_pair.dominant_share_increase_bucket or "无"
    return AccountingStructureMigrationAnalysisPayload(
        summary=(
            f"{latest_pair.current_report_month} 较 {latest_pair.previous_report_month}："
            f"占比正向抬升最明显的是 {dominant_text}。"
        ),
        caveat=(
            "这是汇总会计分类桶的结构信号，不等同于单只资产已经在 "
            "AC/OCI/FVTPL 之间完成会计分类迁移。"
        ),
        pairs=pairs,
    )


def _build_difference_attribution_waterfall(
    *,
    report_date: str,
    summary: AccountingAssetMovementSummaryPayload,
    business_trend_months: list[AccountingBusinessMovementTrendMonthPayload],
    attribution_inputs: dict[str, Decimal],
) -> AccountingDifferenceAttributionWaterfallPayload | None:
    current_month = next(
        (month for month in business_trend_months if month.report_date == report_date),
        None,
    )
    if current_month is None:
        return None

    reference_total = _zqtz_detail_reference_total(current_month)
    target_total = summary.current_balance_total
    net_difference = target_total - reference_total

    rows_by_key = {row.row_key: row for row in current_month.rows}
    long_equity = rows_by_key.get("asset_long_term_equity_investment")
    long_equity_amount = (
        long_equity.current_balance if long_equity is not None else Decimal("0")
    )

    voucher_cost_gap = attribution_inputs.get(
        "ledger_voucher_cost",
        Decimal("0"),
    ) - attribution_inputs.get("formal_voucher_amortized_cost", Decimal("0"))
    voucher_interest_gap = attribution_inputs.get(
        "ledger_voucher_accrued_interest",
        Decimal("0"),
    ) - attribution_inputs.get("formal_voucher_accrued_interest", Decimal("0"))

    components = [
        AccountingDifferenceAttributionComponentPayload(
            component_key="long_term_equity_investment",
            component_label="长期股权投资",
            amount=-long_equity_amount,
            source_kind="ledger",
            evidence_note=(
                "ZQTZ 明细页汇总包含总账长期股权投资行；AC/OCI/FVTPL "
                "控制合计剔除 145*。"
            ),
        ),
        AccountingDifferenceAttributionComponentPayload(
            component_key="voucher_treasury_1430101_cost",
            component_label="凭证式国债 / 1430101 成本",
            amount=voucher_cost_gap,
            source_kind="derived",
            evidence_note=(
                "总账 14301010001 期末余额与 formal ZQTZ 凭证式国债成本口径"
                "（摊余/市值缺省时按面值）的差额。"
            ),
        ),
        AccountingDifferenceAttributionComponentPayload(
            component_key="voucher_treasury_1430101_accrued_interest",
            component_label="凭证式国债 / 1430101 应计利息",
            amount=voucher_interest_gap,
            source_kind="derived",
            evidence_note=(
                "总账 14301010002 期末余额与 formal ZQTZ 凭证式国债应计利息的差额。"
            ),
        ),
        AccountingDifferenceAttributionComponentPayload(
            component_key="valuation_gap",
            component_label="估值差",
            amount=Decimal("0"),
            source_kind="derived",
            evidence_note=(
                "当前 payload 没有可独立闭合的估值拆分；未支持金额保留在残差中。"
            ),
            is_supported=False,
        ),
        AccountingDifferenceAttributionComponentPayload(
            component_key="fx_translation_gap",
            component_label="外币折算差",
            amount=Decimal("0"),
            source_kind="derived",
            evidence_note=(
                "当前 payload 没有可独立闭合的外币折算拆分；未支持金额保留在残差中。"
            ),
            is_supported=False,
        ),
    ]
    explained = sum((component.amount for component in components), Decimal("0"))
    residual = net_difference - explained
    components.append(
        AccountingDifferenceAttributionComponentPayload(
            component_key="residual_unclassified",
            component_label="未分类 / 残差",
            amount=residual,
            source_kind="residual",
            evidence_note=(
                "直接支持项拆分后，为闭合瀑布图所需的剩余差额。"
            ),
            is_residual=True,
        )
    )
    closing_check = (
        sum((component.amount for component in components), Decimal("0"))
        - net_difference
    )
    return AccountingDifferenceAttributionWaterfallPayload(
        reference_label="ZQTZ 明细汇总",
        reference_total=reference_total,
        target_label="AC/OCI/FVTPL 合计",
        target_total=target_total,
        net_difference=net_difference,
        components=components,
        closing_check=closing_check,
        caveat=(
            "瀑布金额表示从 ZQTZ 明细汇总调整到 AC/OCI/FVTPL 合计的方向。"
            "估值差和外币折算差目前只展示可确认部分，不反推未闭合金额。"
        ),
    )


def _build_basis_movement_decomposition(
    *,
    report_date: str,
    prior_report_date: str | None,
    currency_basis: str,
    rows: list[AccountingAssetMovementRowPayload],
    component_result: dict[str, object],
) -> AccountingBasisMovementDecompositionPayload:
    status = _drilldown_status(str(component_result.get("status") or "no_data"))
    raw_components = [
        item
        for item in component_result.get("components", [])
        if isinstance(item, dict)
    ]
    rows_by_bucket = {row.basis_bucket: row for row in rows}
    component_payloads: dict[str, list[AccountingBasisMovementComponentPayload]] = {
        "AC": [],
        "OCI": [],
        "TPL": [],
    }

    for item in raw_components:
        bucket = str(item.get("basis_bucket") or "")
        if bucket not in component_payloads:
            continue
        previous_balance = _decimal_from_object(item.get("previous_balance"))
        current_balance = _decimal_from_object(item.get("current_balance"))
        account_code = str(item.get("account_code") or "")
        account_name = str(item.get("account_name") or "")
        component_payloads[bucket].append(
            AccountingBasisMovementComponentPayload(
                component_key=account_code,
                component_label=f"{account_name} {account_code}".strip(),
                account_code_pattern=account_code,
                previous_balance=previous_balance,
                current_balance=current_balance,
                balance_change=current_balance - previous_balance,
                source_note="product_category_pnl_canonical_fact beginning_balance/ending_balance",
                is_supported=status == "supported",
            )
        )

    buckets: list[AccountingBasisMovementBucketPayload] = []
    for bucket in ("AC", "OCI", "TPL"):
        row = rows_by_bucket.get(bucket)
        previous_balance = row.previous_balance if row is not None else Decimal("0")
        current_balance = row.current_balance if row is not None else Decimal("0")
        balance_change = current_balance - previous_balance
        components = sorted(
            component_payloads[bucket],
            key=lambda item: (-abs(item.balance_change), item.component_key),
        )
        denominator = sum((abs(item.balance_change) for item in components), Decimal("0"))
        if denominator != Decimal("0"):
            components = [
                item.model_copy(
                    update={
                        "contribution_pct": abs(item.balance_change)
                        / denominator
                        * Decimal("100")
                    }
                )
                for item in components
            ]
        component_change = sum(
            (item.balance_change for item in components),
            Decimal("0"),
        )
        residual_amount = balance_change - component_change
        buckets.append(
            AccountingBasisMovementBucketPayload(
                basis_bucket=bucket,
                previous_balance=previous_balance,
                current_balance=current_balance,
                balance_change=balance_change,
                rows=components,
                residual_amount=residual_amount,
                closing_check=residual_amount,
            )
        )

    eligible_total = sum((bucket.current_balance for bucket in buckets), Decimal("0"))
    missing_columns = component_result.get("missing_columns", [])
    caveat = (
        "product_category_pnl_canonical_fact columns missing: "
        + ", ".join(str(item) for item in missing_columns)
        if status == "unsupported_missing_columns"
        else "Uses product_category_pnl_canonical_fact beginning_balance and ending_balance only."
    )
    return AccountingBasisMovementDecompositionPayload(
        meta=AccountingDrilldownMetaPayload(
            source_tables=["product_category_pnl_canonical_fact"],
            source_scope="CNX GL control accounts 141/142/143/1440101, excluding 144020",
            report_date=report_date,
            prior_report_date=prior_report_date,
            currency_basis=currency_basis,
            eligible_total=eligible_total,
            covered_total=eligible_total if status == "supported" else None,
            unknown_total=Decimal("0") if status == "supported" else None,
            coverage_pct=Decimal("100") if status == "supported" and eligible_total != Decimal("0") else None,
            status=status,
            caveat=caveat,
        ),
        buckets=buckets,
    )


def _build_zqtz_maturity_structure(
    *,
    report_date: str,
    prior_report_date: str | None,
    currency_basis: str,
    drilldown_result: dict[str, object],
) -> AccountingZqtzMaturityStructurePayload:
    rows = _drilldown_rows(drilldown_result)
    current_rows = [row for row in rows if str(row.get("report_date")) == report_date]
    prior_rows = [
        row
        for row in rows
        if prior_report_date is not None and str(row.get("report_date")) == prior_report_date
    ]
    missing_columns = _missing_columns(drilldown_result)
    missing_maturity = "maturity_date" in missing_columns or bool(
        missing_columns and "fact_formal_zqtz_balance_daily" in missing_columns
    )
    current_totals = _maturity_totals(
        current_rows,
        report_date=report_date,
        force_unknown=missing_maturity,
    )
    prior_totals = _maturity_totals(
        prior_rows,
        report_date=prior_report_date or report_date,
        force_unknown=missing_maturity or prior_report_date is None,
    )
    eligible_total = sum((amount for amount, _count in current_totals.values()), Decimal("0"))
    unknown_total = current_totals["unknown"][0]
    covered_total = eligible_total - unknown_total
    if eligible_total == Decimal("0"):
        status = "no_data"
    elif missing_maturity:
        status = "unsupported_missing_columns"
    else:
        status = "supported"

    buckets = []
    for bucket_key, label in MATURITY_BUCKETS:
        current_amount, item_count = current_totals[bucket_key]
        prior_amount = prior_totals[bucket_key][0]
        buckets.append(
            AccountingZqtzMaturityBucketPayload(
                maturity_bucket=bucket_key,
                bucket_label=label,
                current_amount=current_amount,
                prior_amount=prior_amount,
                delta_amount=current_amount - prior_amount,
                item_count=item_count,
                share_pct=_pct(current_amount, eligible_total),
            )
        )

    return AccountingZqtzMaturityStructurePayload(
        meta=AccountingDrilldownMetaPayload(
            source_tables=["fact_formal_zqtz_balance_daily"],
            source_scope="formal ZQTZ primary asset rows using existing page predicates",
            report_date=report_date,
            prior_report_date=prior_report_date,
            currency_basis=currency_basis,
            zqtz_currency_basis=str(drilldown_result.get("zqtz_currency_basis") or ""),
            eligible_total=eligible_total,
            covered_total=covered_total,
            unknown_total=unknown_total,
            coverage_pct=_pct(covered_total, eligible_total),
            status=status,
            caveat=(
                "maturity_date source column is absent; all maturity buckets are unsupported."
                if status == "unsupported_missing_columns"
                else "Uses maturity_date only; invalid or blank dates are reported as unknown."
            ),
        ),
        buckets=buckets,
    )


def _build_zqtz_concentration_analysis(
    *,
    report_date: str,
    prior_report_date: str | None,
    currency_basis: str,
    drilldown_result: dict[str, object],
) -> AccountingZqtzConcentrationAnalysisPayload:
    rows = _drilldown_rows(drilldown_result)
    current_rows = [row for row in rows if str(row.get("report_date")) == report_date]
    prior_rows = [
        row
        for row in rows
        if prior_report_date is not None and str(row.get("report_date")) == prior_report_date
    ]
    eligible_total = _sum_row_amounts(current_rows)
    missing_columns = _missing_columns(drilldown_result)
    dimensions = [
        _build_concentration_dimension(
            dimension=dimension,
            current_rows=current_rows,
            prior_rows=prior_rows,
            eligible_total=eligible_total,
            missing_columns=missing_columns,
        )
        for dimension in CONCENTRATION_DIMENSIONS
    ]
    supported_dimensions = [
        dimension
        for dimension in dimensions
        if dimension.status == "supported"
    ]
    if eligible_total == Decimal("0"):
        meta_status = "no_data"
    elif any(dimension.status == "unsupported_low_coverage" for dimension in dimensions):
        meta_status = "unsupported_low_coverage"
    elif any(dimension.status == "unsupported_missing_columns" for dimension in dimensions):
        meta_status = "unsupported_missing_columns"
    elif supported_dimensions and len(supported_dimensions) == len(dimensions):
        meta_status = "supported"
    else:
        meta_status = "no_data"

    weakest_supported_dimension = min(
        supported_dimensions,
        key=lambda dimension: dimension.coverage_pct or Decimal("-1"),
        default=None,
    )
    covered_total = (
        weakest_supported_dimension.covered_total
        if meta_status == "supported" and weakest_supported_dimension is not None
        else None
    )
    unknown_total = (
        weakest_supported_dimension.unknown_total
        if meta_status == "supported" and weakest_supported_dimension is not None
        else None
    )
    coverage_pct = (
        weakest_supported_dimension.coverage_pct
        if meta_status == "supported" and weakest_supported_dimension is not None
        else None
    )
    meta_caveat = (
        "Issuer, rating, and industry concentration are all supported; headline coverage is the weakest dimension."
        if meta_status == "supported"
        else "Issuer, rating, and industry concentration may differ in coverage; inspect each dimension status."
    )
    return AccountingZqtzConcentrationAnalysisPayload(
        meta=AccountingDrilldownMetaPayload(
            source_tables=["fact_formal_zqtz_balance_daily"],
            source_scope="formal ZQTZ primary asset rows using existing page predicates",
            report_date=report_date,
            prior_report_date=prior_report_date,
            currency_basis=currency_basis,
            zqtz_currency_basis=str(drilldown_result.get("zqtz_currency_basis") or ""),
            eligible_total=eligible_total,
            covered_total=covered_total,
            unknown_total=unknown_total,
            coverage_pct=coverage_pct,
            status=meta_status,
            caveat=meta_caveat,
        ),
        dimensions=dimensions,
    )


def _build_concentration_dimension(
    *,
    dimension: str,
    current_rows: list[dict[str, object]],
    prior_rows: list[dict[str, object]],
    eligible_total: Decimal,
    missing_columns: list[str],
) -> AccountingZqtzConcentrationDimensionPayload:
    if dimension in missing_columns or "fact_formal_zqtz_balance_daily" in missing_columns:
        return AccountingZqtzConcentrationDimensionPayload(
            dimension=dimension,
            status="unsupported_missing_columns",
            eligible_total=eligible_total,
            covered_total=Decimal("0"),
            unknown_total=eligible_total,
            coverage_pct=None,
            prior_coverage_pct=None,
            top_n=CONCENTRATION_TOP_N,
            hhi=None,
            top5_share_pct=None,
            items=[],
            caveat=f"Source column {dimension} is absent.",
        )
    if eligible_total == Decimal("0"):
        return AccountingZqtzConcentrationDimensionPayload(
            dimension=dimension,
            status="no_data",
            eligible_total=Decimal("0"),
            covered_total=Decimal("0"),
            unknown_total=Decimal("0"),
            coverage_pct=None,
            prior_coverage_pct=None,
            top_n=CONCENTRATION_TOP_N,
            hhi=None,
            top5_share_pct=None,
            items=[],
            caveat="No eligible ZQTZ asset population.",
        )

    current = _dimension_amounts(current_rows, dimension)
    prior = _dimension_amounts(prior_rows, dimension)
    covered_total = sum(current["known"].values(), Decimal("0"))
    unknown_total = current["unknown_amount"]
    coverage_pct = _pct(covered_total, eligible_total)
    prior_eligible_total = prior["known_total"] + prior["unknown_amount"]
    prior_covered_total = prior["known_total"]
    prior_unknown_total = prior["unknown_amount"]
    prior_coverage_pct = _pct(prior_covered_total, prior_eligible_total)

    if coverage_pct is None or coverage_pct < CONCENTRATION_COVERAGE_THRESHOLD:
        return AccountingZqtzConcentrationDimensionPayload(
            dimension=dimension,
            status="unsupported_low_coverage",
            eligible_total=eligible_total,
            covered_total=covered_total,
            unknown_total=unknown_total,
            coverage_pct=coverage_pct,
            prior_coverage_pct=prior_coverage_pct,
            top_n=CONCENTRATION_TOP_N,
            hhi=None,
            top5_share_pct=None,
            items=[],
            caveat=f"{dimension} coverage is below 80%; rankings are not rendered.",
        )

    prior_supported = (
        prior_coverage_pct is not None
        and prior_coverage_pct >= CONCENTRATION_COVERAGE_THRESHOLD
    )
    sorted_known = sorted(
        current["known"].items(),
        key=lambda item: (-item[1], item[0]),
    )
    top_values = [value for value, _amount in sorted_known[:CONCENTRATION_TOP_N]]
    top_set = set(top_values)
    items: list[AccountingZqtzConcentrationItemPayload] = []

    def item_payload(
        *,
        rank: int,
        value: str,
        current_amount: Decimal,
        prior_amount: Decimal | None,
        item_count: int,
        item_kind: str,
    ) -> AccountingZqtzConcentrationItemPayload:
        return AccountingZqtzConcentrationItemPayload(
            rank=rank,
            dimension_value=value,
            current_amount=current_amount,
            prior_amount=prior_amount,
            delta_amount=(
                current_amount - prior_amount
                if prior_amount is not None
                else None
            ),
            share_pct=_pct(current_amount, eligible_total),
            item_count=item_count,
            item_kind=item_kind,
        )

    rank = 1
    for value in top_values:
        prior_amount = prior["known"].get(value, Decimal("0")) if prior_supported else None
        items.append(
            item_payload(
                rank=rank,
                value=value,
                current_amount=current["known"][value],
                prior_amount=prior_amount,
                item_count=current["counts"].get(value, 0),
                item_kind="top",
            )
        )
        rank += 1

    other_current = sum(
        (amount for value, amount in current["known"].items() if value not in top_set),
        Decimal("0"),
    )
    other_prior = (
        sum(
            (amount for value, amount in prior["known"].items() if value not in top_set),
            Decimal("0"),
        )
        if prior_supported
        else None
    )
    if other_current != Decimal("0") or (
        other_prior is not None and other_prior != Decimal("0")
    ):
        items.append(
            item_payload(
                rank=rank,
                value="其他",
                current_amount=other_current,
                prior_amount=other_prior,
                item_count=sum(
                    count
                    for value, count in current["counts"].items()
                    if value not in top_set
                ),
                item_kind="other",
            )
        )
        rank += 1

    unknown_prior = prior_unknown_total if prior_supported else None
    if unknown_total != Decimal("0") or (
        unknown_prior is not None and unknown_prior != Decimal("0")
    ):
        items.append(
            item_payload(
                rank=rank,
                value="未映射",
                current_amount=unknown_total,
                prior_amount=unknown_prior,
                item_count=current["unknown_count"],
                item_kind="unknown",
            )
        )

    caveat = (
        "Prior coverage is below 80%; MoM prior and delta values are disabled."
        if prior_rows and not prior_supported
        else "Top values are anchored on the current period; other and unknown stay separate."
    )
    return AccountingZqtzConcentrationDimensionPayload(
        dimension=dimension,
        status="supported",
        eligible_total=eligible_total,
        covered_total=covered_total,
        unknown_total=unknown_total,
        coverage_pct=coverage_pct,
        prior_coverage_pct=prior_coverage_pct,
        top_n=CONCENTRATION_TOP_N,
        hhi=_hhi(current["known"], covered_total),
        top5_share_pct=_pct(
            sum((amount for _value, amount in sorted_known[:5]), Decimal("0")),
            covered_total,
        ),
        items=items,
        caveat=caveat,
    )


def _build_zqtz_calibration_analysis(
    *,
    report_date: str,
    business_trend_months: list[AccountingBusinessMovementTrendMonthPayload],
) -> AccountingZqtzCalibrationAnalysisPayload | None:
    if report_date != "2026-02-28":
        return None
    current_month = next(
        (month for month in business_trend_months if month.report_date == report_date),
        None,
    )
    if current_month is None:
        return None
    if not any(
        row.source_kind == "zqtz" and "sv_b9f27f66f761" in row.source_version
        for row in current_month.rows
    ):
        return None

    rows_by_key = {row.row_key: row for row in current_month.rows}
    item_specs = [
        (
            "asset_zqtz_policy_financial_bond",
            "ZQTZ228 原表按会计分类保留多笔同券持仓后，与展示表一致。",
        ),
        (
            "asset_zqtz_local_government_bond",
            "同一口径下，地方政府债与展示表一致。",
        ),
        (
            "asset_zqtz_foreign_bond",
            "外国债券当前按 US* + HK0001155867 清单和 CNY formal 金额折算，仍保留清单/汇率小额观察。",
        ),
    ]
    items: list[AccountingZqtzCalibrationItemPayload] = []
    for row_key, note in item_specs:
        row = rows_by_key.get(row_key)
        reference_amount = ZQTZ228_REFERENCE_AMOUNTS[row_key]
        system_amount = row.current_balance if row is not None else Decimal("0")
        diff_amount = system_amount - reference_amount
        tolerance = Decimal("1000000") if row_key != "asset_zqtz_foreign_bond" else Decimal("20000000")
        items.append(
            AccountingZqtzCalibrationItemPayload(
                row_key=row_key,
                row_label=row.row_label if row is not None else row_key,
                system_amount=system_amount,
                reference_amount=reference_amount,
                diff_amount=diff_amount,
                status="matched" if abs(diff_amount) <= tolerance else "watch",
                note=note,
            )
        )

    return AccountingZqtzCalibrationAnalysisPayload(
        source_file="ZQTZSHOW-20260228.xls / ZQTZ228",
        conclusion="政策性金融债的大额差异已定位并修复：不是外债折算，也不是政策债口径包含凭证式国债/地方债，而是 ZQTZ 标准化粒度覆盖了同券多笔持仓。",
        root_cause="旧 canonical grain 只按日期、债券代码、组合、成本中心、币种聚合；25国开清发02、24国开15、17农发15、23国开03 等同券多分类持仓被后到行覆盖，导致政策性金融债少约 58.12 亿元。",
        remediation="现已把 ZQTZ grain 扩到会计分类、业务种类、到期日、来源批次等维度，并在同一会计桶内加总面值/市值/摊余成本/应计利息。",
        items=items,
        residual_risks=[
            "外国债券仍依赖披露外债清单；如后续 ZQTZ 提供明确 sub_type=外国债券，应替换清单规则。",
            "2026-03 展示表需要 2026-03 ZQTZ/总账入库后才能做同样核对。",
        ],
    )


def _trend_row_by_bucket(
    month: AccountingAssetMovementTrendMonthPayload,
    bucket: str,
) -> AccountingAssetMovementRowPayload | None:
    return next((row for row in month.rows if row.basis_bucket == bucket), None)


def _build_fvtpl_signal(
    buckets: list[AccountingStructureMigrationBucketPayload],
) -> str:
    fvtpl = next((bucket for bucket in buckets if bucket.basis_bucket == "TPL"), None)
    if fvtpl is None:
        return "本月对缺少 FVTPL 分类桶，暂不判断损益波动暴露。"
    share_delta = fvtpl.share_delta_pp or Decimal("0")
    if fvtpl.balance_delta > Decimal("0") or share_delta > Decimal("0"):
        return (
            "FVTPL 余额或占比上升，说明损益波动暴露在抬升；"
            "这不是已实现损益结论。"
        )
    return (
        "FVTPL 余额和占比没有同时抬升，本月对不标记新增损益波动暴露。"
    )


def _build_oci_valuation_signal(
    *,
    previous_month: AccountingAssetMovementTrendMonthPayload,
    current_month: AccountingAssetMovementTrendMonthPayload,
    diagnostic_inputs: dict[str, dict[str, Decimal]],
) -> str:
    previous_oci = _trend_row_by_bucket(previous_month, "OCI")
    current_oci = _trend_row_by_bucket(current_month, "OCI")
    if previous_oci is None or current_oci is None:
        return "本月对缺少 OCI 分类桶，暂不判断估值驱动。"
    oci_delta = current_oci.current_balance - previous_oci.current_balance
    if oci_delta == Decimal("0"):
        return "OCI 余额未变化，暂不判断估值驱动占比。"

    previous_fv = diagnostic_inputs.get(previous_month.report_date, {}).get(
        "oci_fair_value_balance"
    )
    current_fv = diagnostic_inputs.get(current_month.report_date, {}).get(
        "oci_fair_value_balance"
    )
    if previous_fv is None or current_fv is None:
        return (
            "OCI 余额发生变化，但缺少公允价值变动科目的证据；"
            "当前不归因为估值驱动。"
        )

    fair_value_delta = current_fv - previous_fv
    ratio = abs(fair_value_delta) / abs(oci_delta)
    if ratio >= Decimal("0.5"):
        return (
            "OCI 公允价值变动科目的变化可解释至少一半 OCI 余额变动；"
            "这是估值代理信号，仍需持仓层确认。"
        )
    return (
        "OCI 公允价值变动科目的变化解释不足一半 OCI 余额变动；"
        "估值不是本月对的主导代理信号。"
    )


def _zqtz_detail_reference_total(
    month: AccountingBusinessMovementTrendMonthPayload,
) -> Decimal:
    return sum(
        (
            row.current_balance
            for row in month.rows
            if row.side == "asset"
            and (
                row.source_kind == "zqtz"
                or row.row_key == "asset_long_term_equity_investment"
            )
            and not row.row_key.startswith("asset_zqtz_detail_")
        ),
        Decimal("0"),
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


def _drilldown_status(value: str) -> str:
    if value in {
        "supported",
        "unsupported_missing_columns",
        "unsupported_low_coverage",
        "no_data",
    }:
        return value
    return "no_data"


def _drilldown_rows(result: dict[str, object]) -> list[dict[str, object]]:
    rows = result.get("rows", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _missing_columns(result: dict[str, object]) -> list[str]:
    columns = result.get("missing_columns", [])
    if not isinstance(columns, list):
        return []
    return [str(column) for column in columns]


def _decimal_from_object(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _sum_row_amounts(rows: list[dict[str, object]]) -> Decimal:
    return sum((_decimal_from_object(row.get("amount")) for row in rows), Decimal("0"))


def _maturity_totals(
    rows: list[dict[str, object]],
    *,
    report_date: str,
    force_unknown: bool,
) -> dict[str, tuple[Decimal, int]]:
    totals = {
        bucket_key: (Decimal("0"), 0)
        for bucket_key, _label in MATURITY_BUCKETS
    }
    report_date_value = _parse_iso_date(report_date)
    for row in rows:
        amount = _decimal_from_object(row.get("amount"))
        bucket_key = "unknown"
        if not force_unknown and report_date_value is not None:
            maturity_date = _parse_iso_date(row.get("maturity_date"))
            bucket_key = _maturity_bucket(maturity_date, report_date_value)
        bucket_amount, bucket_count = totals[bucket_key]
        totals[bucket_key] = (bucket_amount + amount, bucket_count + 1)
    return totals


def _maturity_bucket(maturity_date: date | None, report_date: date) -> str:
    if maturity_date is None:
        return "unknown"
    days_to_maturity = (maturity_date - report_date).days
    if days_to_maturity < 0:
        return "overdue_or_matured"
    if days_to_maturity <= 30:
        return "<=30d"
    if days_to_maturity <= 90:
        return "31-90d"
    if days_to_maturity <= 365:
        return "91d-1y"
    if days_to_maturity <= 1095:
        return "1-3y"
    if days_to_maturity <= 1825:
        return "3-5y"
    return ">5y"


def _parse_iso_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _dimension_amounts(
    rows: list[dict[str, object]],
    dimension: str,
) -> dict[str, object]:
    known: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    unknown_amount = Decimal("0")
    unknown_count = 0
    for row in rows:
        amount = _decimal_from_object(row.get("amount"))
        value = _concentration_dimension_value(row, dimension)
        if not value:
            unknown_amount += amount
            unknown_count += 1
            continue
        known[value] = known.get(value, Decimal("0")) + amount
        counts[value] = counts.get(value, 0) + 1
    known_total = sum(known.values(), Decimal("0"))
    return {
        "known": known,
        "counts": counts,
        "known_total": known_total,
        "unknown_amount": unknown_amount,
        "unknown_count": unknown_count,
    }


def _concentration_dimension_value(row: dict[str, object], dimension: str) -> str:
    raw_value = row.get(dimension)
    value = str(raw_value).strip() if raw_value not in (None, "") else ""
    if value or dimension != "rating":
        return value
    return INTEREST_RATE_BOND_DEFAULT_RATING if _is_interest_rate_bond(row) else ""


def _is_interest_rate_bond(row: dict[str, object]) -> bool:
    descriptors = [
        str(row.get(field) or "").strip()
        for field in INTEREST_RATE_BOND_DESCRIPTOR_FIELDS
    ]
    descriptor_text = " ".join(value for value in descriptors if value)
    if any(keyword in descriptor_text for keyword in INTEREST_RATE_BOND_EXCLUDE_KEYWORDS):
        return False
    return any(keyword in descriptor_text for keyword in INTEREST_RATE_BOND_KEYWORDS)


def _hhi(values: dict[str, Decimal], denominator: Decimal) -> Decimal | None:
    if denominator == Decimal("0"):
        return None
    return sum(
        ((amount / denominator) ** 2 for amount in values.values()),
        Decimal("0"),
    ) * Decimal("10000")


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
            (
                row.current_balance
                for row in rows
                if row.side == "asset"
                and not row.row_key.startswith("asset_zqtz_detail_")
            ),
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
