from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS, match_zqtz_asset_bond_rows
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.schemas.pnl import (
    PnlByBusinessAnalysisDimension,
    PnlByBusinessAnalysisPayload,
    PnlByBusinessAnalysisRow,
    PnlByBusinessMonthlyBucket,
    PnlByBusinessMonthlyItem,
    PnlByBusinessMonthlyPayload,
    PnlByBusinessMonthlySummary,
)

TWOPLACES = Decimal("0.01")
RATIOPLACES = Decimal("0.000001")
FTP_RATE_PCT = Decimal("1.600000")
FTP_RATE_RATIO = Decimal("0.016")
PNL_BY_BUSINESS_PRECOMPUTE_SOURCE_VERSION = "sv_pnl_by_business_precompute_v1"
PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION = "rv_pnl_by_business_precompute_v1"
PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS: tuple[PnlByBusinessAnalysisDimension, ...] = (
    "bond_bucket",
    "bond_bucket_monthly",
)
PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS: tuple[PnlByBusinessAnalysisDimension, ...] = (
    "monthly",
    "portfolio",
    "accounting",
    "cost_center",
    "instrument",
)
ANALYSIS_BOND_BUCKETS: tuple[tuple[str, str, frozenset[str]], ...] = (
    (
        "rate_bond",
        "利率债",
        frozenset(
            {
                "asset_zqtz_central_bank_bill",
                "asset_zqtz_treasury_bond",
                "asset_zqtz_local_government_bond",
                "asset_zqtz_policy_financial_bond",
                "asset_zqtz_railway_bond",
            }
        ),
    ),
    (
        "credit_bond",
        "信用债",
        frozenset({"asset_zqtz_nonfinancial_enterprise_bond", "asset_zqtz_abs"}),
    ),
    (
        "financial_bond",
        "金融债",
        frozenset({"asset_zqtz_commercial_financial_bond", "asset_zqtz_interbank_cd"}),
    ),
    (
        "other_bond",
        "其它债券",
        frozenset(
            {
                "asset_zqtz_foreign_bond",
                "asset_zqtz_public_fund",
                "asset_zqtz_non_bottom_investment",
                "asset_zqtz_detail_trust_plan",
                "asset_zqtz_detail_securities_asset_management_plan",
                "asset_zqtz_detail_structured_finance_broker",
                "asset_zqtz_detail_foreign_currency_delegated",
                "asset_zqtz_detail_local_currency_delegated_market_value",
                "asset_zqtz_detail_local_currency_special_account_cost",
                "asset_zqtz_other_debt_financing",
            }
        ),
    ),
)
ANALYSIS_BOND_BUCKET_SORT = {key: index for index, (key, _label, _row_keys) in enumerate(ANALYSIS_BOND_BUCKETS)}
ANALYSIS_BOND_BUCKET_LABELS = {key: label for key, label, _row_keys in ANALYSIS_BOND_BUCKETS}

def precompute_pnl_by_business_payloads(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    """Materialize the page-local `/pnl-by-business` read model for one cutoff date."""
    _ = governance_dir
    repo = PnlRepository(duckdb_path)
    as_cap = as_of_date or repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=None)
    if not as_cap:
        raise ValueError(f"No formal pnl rows found for year={year}.")
    if not str(as_cap).startswith(f"{year:04d}-"):
        raise ValueError(f"as_of_date={as_cap} is outside requested year={year}.")

    period_end = repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=str(as_cap))
    if period_end is None:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
    loaded_dates = sorted(
        d
        for d in repo.list_union_report_dates()
        if str(d).startswith(f"{year:04d}") and str(d) <= period_end
    )
    if not loaded_dates:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")

    period_start = f"{min(loaded_dates)[:7]}-01"
    pnl_rows = repo.fetch_by_business_analysis_pnl_rows(year=year, as_of_date=period_end)
    balance_rows = repo.fetch_by_business_analysis_balance_rows(
        start_date=period_start,
        end_date=period_end,
    )
    if not pnl_rows:
        raise ValueError(f"No aggregated pnl positions for year={year} through as_of_date={period_end}.")

    source_tables = [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_zqtz_balance_daily",
        "ZQTZ_ASSET_BOND_ROWS",
    ]
    source_version_resolver = getattr(repo, "pnl_by_business_precompute_source_version", None)
    precompute_source_version = (
        source_version_resolver(year=year, as_of_date=period_end)
        if callable(source_version_resolver)
        else PNL_BY_BUSINESS_PRECOMPUTE_SOURCE_VERSION
    )
    generated_at = datetime.now(UTC).isoformat()
    records: list[dict[str, object]] = []

    monthly_payload = PnlByBusinessMonthlyPayload(
        year=year,
        as_of_date=period_end,
        source_tables=source_tables,
        months=_build_pnl_by_business_monthly_buckets(
            pnl_rows=tuple(pnl_rows),
            balance_rows=tuple(balance_rows),
            loaded_dates=loaded_dates,
        ),
    )
    records.append(
        _pnl_by_business_precompute_record(
            year=year,
            as_of_date=period_end,
            result_kind="monthly",
            dimension="",
            business_key="",
            payload=monthly_payload,
            generated_at=generated_at,
            source_version=precompute_source_version,
        )
    )

    analysis_payloads = _build_pnl_by_business_analysis_payloads_for_precompute(
        year=year,
        period_start=period_start,
        period_end=period_end,
        source_tables=source_tables,
        pnl_rows=pnl_rows,
        balance_rows=balance_rows,
        loaded_dates=loaded_dates,
    )
    for payload in analysis_payloads:
        records.append(
            _pnl_by_business_precompute_record(
                year=year,
                as_of_date=period_end,
                result_kind="analysis",
                dimension=payload.dimension,
                business_key=payload.business_key or "",
                payload=payload,
                generated_at=generated_at,
                source_version=precompute_source_version,
            )
        )

    persist_pnl_by_business_precompute(
        duckdb_path=duckdb_path,
        year=year,
        as_of_date=period_end,
        records=records,
        repository_cls=PnlRepository,
    )
    return {
        "year": year,
        "as_of_date": period_end,
        "records": len(records),
        "monthly_records": 1,
        "analysis_records": len(records) - 1,
    }

def persist_pnl_by_business_precompute(
    *,
    duckdb_path: str,
    year: int,
    as_of_date: str,
    records: list[dict[str, object]],
    repository_cls: type[PnlRepository] | None = None,
) -> None:
    repo_cls = repository_cls or PnlRepository
    repo = repo_cls(duckdb_path)
    with repository_task_write_scope(__name__):
        repo.replace_pnl_by_business_precompute(year=year, as_of_date=as_of_date, records=records)

def _manual_adjustment_row_def(record: dict[str, object]) -> dict[str, object]:
    row_key = str(record.get("manual_business_row_key") or record.get("row_key") or "").strip()
    for row_def in ZQTZ_ASSET_BOND_ROWS:
        if str(row_def.get("row_key") or "") == row_key:
            return row_def
    return {
        "row_key": row_key or "manual_unclassified",
        "sort_order": 999,
        "row_label": str(record.get("manual_business_type") or record.get("business_type") or row_key or "手工调整"),
        "source_note": str(record.get("source_note") or "pnl_by_business_adjustments"),
    }

def _pnl_by_business_manual_classification(record: dict[str, object]) -> dict[str, object]:
    row_def = _manual_adjustment_row_def(record)
    label = str(row_def.get("row_label") or record.get("manual_business_type") or "")
    return {
        "report_date": _norm_text(record.get("report_date")),
        "instrument_code": _norm_text(record.get("instrument_code")),
        "instrument_name": label,
        "account_category": "manual_adjustment",
        "asset_class": label,
        "bond_type": label,
        "sub_type": label,
        "business_type_primary": label,
        "business_type_final": label,
        "invest_type_std": "",
        "accounting_basis": "manual_adjustment",
        "currency_code": "CNY",
        "manual_business_row_key": str(row_def.get("row_key") or ""),
    }

def _pnl_by_business_precompute_record(
    *,
    year: int,
    as_of_date: str,
    result_kind: str,
    dimension: str,
    business_key: str,
    payload: PnlByBusinessMonthlyPayload | PnlByBusinessAnalysisPayload,
    generated_at: str,
    source_version: str,
) -> dict[str, object]:
    return {
        "year": year,
        "as_of_date": as_of_date,
        "result_kind": result_kind,
        "dimension": dimension,
        "business_key": business_key,
        "payload_json": json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
        "source_version": source_version,
        "rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        "generated_at": generated_at,
    }

def _build_pnl_by_business_analysis_payloads_for_precompute(
    *,
    year: int,
    period_start: str,
    period_end: str,
    source_tables: list[str],
    pnl_rows: list[dict[str, object]],
    balance_rows: list[dict[str, object]],
    loaded_dates: list[str],
) -> list[PnlByBusinessAnalysisPayload]:
    balance_lookup = _analysis_balance_lookup(balance_rows)
    historical_balance_lookup = _analysis_historical_balance_lookup(balance_rows)
    sub_type_by_date_code = _analysis_sub_type_by_date_code(balance_rows)
    month_end_by_month: dict[str, str] = {}
    for report_date in sorted(loaded_dates):
        month_end_by_month[str(report_date)[:7]] = str(report_date)

    bucket_maps: dict[tuple[str | None, PnlByBusinessAnalysisDimension], dict[str, dict[str, object]]] = {}
    avg_sums: dict[tuple[str | None, PnlByBusinessAnalysisDimension, str], Decimal] = {}
    current_sums: dict[tuple[str | None, PnlByBusinessAnalysisDimension, str], Decimal] = {}
    coverage_dates = {_norm_text(row.get("report_date")) for row in balance_rows if _norm_text(row.get("report_date"))}
    coverage_dates_by_month_key: dict[str, set[str]] = {}
    business_keys = tuple(str(row_def["row_key"]) for row_def in ZQTZ_ASSET_BOND_ROWS)

    def _bucket_map(
        business_key: str | None,
        dimension: PnlByBusinessAnalysisDimension,
    ) -> dict[str, dict[str, object]]:
        map_key = (business_key, dimension)
        if map_key not in bucket_maps:
            bucket_maps[map_key] = {}
            if business_key is None and dimension == "bond_bucket":
                for key, label in ANALYSIS_BOND_BUCKET_LABELS.items():
                    bucket_maps[map_key][key] = _new_analysis_dimension_bucket(key, label)
            elif business_key is None and dimension == "bond_bucket_monthly":
                for month_end in sorted(month_end_by_month.values()):
                    for key, label in ANALYSIS_BOND_BUCKET_LABELS.items():
                        dimension_key = f"{month_end}::{key}"
                        bucket_maps[map_key][dimension_key] = _new_analysis_dimension_bucket(
                            dimension_key,
                            f"{month_end} {label}",
                        )
        return bucket_maps[map_key]

    for dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
        _bucket_map(None, dimension)

    def _add_pnl(
        *,
        business_key: str | None,
        dimension: PnlByBusinessAnalysisDimension,
        key_label: tuple[str, str] | None,
        row: dict[str, object],
    ) -> None:
        if key_label is None:
            return
        dimension_key, dimension_label = key_label
        bucket = _bucket_map(business_key, dimension).setdefault(
            dimension_key,
            _new_analysis_dimension_bucket(dimension_key, dimension_label),
        )
        bucket["interest_income"] = Decimal(str(bucket["interest_income"])) + _decimal_value(
            row.get("interest_income_514")
        )
        bucket["fair_value_change"] = Decimal(str(bucket["fair_value_change"])) + _decimal_value(
            row.get("fair_value_change_516")
        )
        bucket["capital_gain"] = Decimal(str(bucket["capital_gain"])) + _decimal_value(row.get("capital_gain_517"))
        bucket["manual_adjustment"] = Decimal(str(bucket["manual_adjustment"])) + _decimal_value(
            row.get("manual_adjustment")
        )
        bucket["total_pnl"] = Decimal(str(bucket["total_pnl"])) + _decimal_value(row.get("total_pnl"))
        code = _norm_text(row.get("instrument_code"))
        if code:
            bucket["asset_codes"].add(code)

    def _add_balance(
        *,
        business_key: str | None,
        dimension: PnlByBusinessAnalysisDimension,
        key_label: tuple[str, str] | None,
        row: dict[str, object],
    ) -> None:
        if key_label is None:
            return
        dimension_key, _dimension_label = key_label
        sum_key = (business_key, dimension, dimension_key)
        avg_sums[sum_key] = avg_sums.get(sum_key, Decimal("0")) + _decimal_value(row.get("avg_amount"))
        report_date = _norm_text(row.get("report_date"))
        dimension_report_date = _analysis_dimension_report_date(dimension_key)
        if (_analysis_is_monthly_dimension(dimension) and report_date == dimension_report_date) or (
            not _analysis_is_monthly_dimension(dimension) and report_date == period_end
        ):
            current_sums[sum_key] = current_sums.get(sum_key, Decimal("0")) + _decimal_value(
                row.get("current_amount")
            )

    for pnl_row in pnl_rows:
        classification = (
            _pnl_by_business_manual_classification(pnl_row)
            if _norm_text(pnl_row.get("source_kind")) == "manual_adjustment"
            else _analysis_classification_for_pnl_row(
                pnl_row=pnl_row,
                balance_lookup=balance_lookup,
                historical_balance_lookup=historical_balance_lookup,
                sub_type_by_date_code=sub_type_by_date_code,
                fallback_date=period_end,
            )
        )
        matched_keys = _analysis_matched_business_keys(classification)
        for dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
            _add_pnl(
                business_key=None,
                dimension=dimension,
                key_label=_analysis_global_bond_bucket_dimension_for_pnl_row(pnl_row, matched_keys, dimension),
                row=pnl_row,
            )
        for business_key in matched_keys:
            for dimension in PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS:
                _add_pnl(
                    business_key=business_key,
                    dimension=dimension,
                    key_label=_analysis_dimension_for_pnl_row(pnl_row, classification, dimension),
                    row=pnl_row,
                )

    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        month_key = month_end_by_month.get(report_date[:7])
        if month_key:
            coverage_dates_by_month_key.setdefault(month_key, set()).add(report_date)
        classification = _analysis_classification_from_balance_row(row)
        matched_keys = _analysis_matched_business_keys(classification)
        for dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
            _add_balance(
                business_key=None,
                dimension=dimension,
                key_label=_analysis_global_bond_bucket_dimension_for_balance_row(
                    row,
                    matched_keys,
                    dimension,
                    month_end_by_month,
                ),
                row=row,
            )
        for business_key in matched_keys:
            for dimension in PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS:
                _add_balance(
                    business_key=business_key,
                    dimension=dimension,
                    key_label=_analysis_dimension_for_balance_row(row, dimension, month_end_by_month),
                    row=row,
                )

    payloads: list[PnlByBusinessAnalysisPayload] = []
    for dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
        payloads.append(
            PnlByBusinessAnalysisPayload(
                year=year,
                as_of_date=period_end,
                business_key=None,
                dimension=dimension,
                period_start_date=period_start,
                period_end_date=period_end,
                source_tables=source_tables,
                rows=_analysis_rows_from_precompute_buckets(
                    bucket_map=_bucket_map(None, dimension),
                    avg_sums=avg_sums,
                    current_sums=current_sums,
                    coverage_dates=coverage_dates,
                    coverage_dates_by_month_key=coverage_dates_by_month_key,
                    period_start=period_start,
                    period_end=period_end,
                    business_key=None,
                    dimension=dimension,
                ),
            )
        )
    for business_key in business_keys:
        for dimension in PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS:
            payloads.append(
                PnlByBusinessAnalysisPayload(
                    year=year,
                    as_of_date=period_end,
                    business_key=business_key,
                    dimension=dimension,
                    period_start_date=period_start,
                    period_end_date=period_end,
                    source_tables=source_tables,
                    rows=_analysis_rows_from_precompute_buckets(
                        bucket_map=bucket_maps.get((business_key, dimension), {}),
                        avg_sums=avg_sums,
                        current_sums=current_sums,
                        coverage_dates=coverage_dates,
                        coverage_dates_by_month_key=coverage_dates_by_month_key,
                        period_start=period_start,
                        period_end=period_end,
                        business_key=business_key,
                        dimension=dimension,
                    ),
                )
            )
    return payloads

def _analysis_rows_from_precompute_buckets(
    *,
    bucket_map: dict[str, dict[str, object]],
    avg_sums: dict[tuple[str | None, PnlByBusinessAnalysisDimension, str], Decimal],
    current_sums: dict[tuple[str | None, PnlByBusinessAnalysisDimension, str], Decimal],
    coverage_dates: set[str],
    coverage_dates_by_month_key: dict[str, set[str]],
    period_start: str,
    period_end: str,
    business_key: str | None,
    dimension: PnlByBusinessAnalysisDimension,
) -> list[PnlByBusinessAnalysisRow]:
    period_calendar_days = _calendar_days(period_start, period_end)
    rows: list[PnlByBusinessAnalysisRow] = []
    for bucket in sorted(bucket_map.values(), key=lambda item: _analysis_dimension_row_sort_key(item, dimension)):
        dimension_key = str(bucket["dimension_key"])
        if _analysis_is_monthly_dimension(dimension):
            month_end_key = _analysis_dimension_report_date(dimension_key)
            denom = len(coverage_dates_by_month_key.get(month_end_key, set()))
            calendar_days = _calendar_days(f"{month_end_key[:7]}-01", month_end_key)
        else:
            denom = len(coverage_dates)
            calendar_days = period_calendar_days
        sum_key = (business_key, dimension, dimension_key)
        avg_balance = (avg_sums.get(sum_key, Decimal("0")) / Decimal(str(denom))) if denom > 0 else Decimal("0")
        current_balance = current_sums.get(sum_key, Decimal("0"))
        total_pnl = Decimal(str(bucket["total_pnl"]))
        annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days)
        ftp_values = _analysis_ftp_values(
            total_pnl=total_pnl,
            avg_balance=avg_balance,
            annualized_yield_pct=annualized_yield_pct,
            calendar_days=calendar_days,
        )
        rows.append(
            PnlByBusinessAnalysisRow(
                dimension_key=dimension_key,
                dimension_label=str(bucket["dimension_label"]),
                interest_income=_quantize_decimal(Decimal(str(bucket["interest_income"]))),
                fair_value_change=_quantize_decimal(Decimal(str(bucket["fair_value_change"]))),
                capital_gain=_quantize_decimal(Decimal(str(bucket["capital_gain"]))),
                manual_adjustment=_quantize_decimal(Decimal(str(bucket["manual_adjustment"]))),
                total_pnl=_quantize_decimal(total_pnl),
                avg_balance=_quantize_decimal(avg_balance),
                current_balance=_quantize_decimal(current_balance),
                annualized_yield_pct=annualized_yield_pct,
                ftp_rate_pct=FTP_RATE_PCT,
                ftp_cost=ftp_values["ftp_cost"],
                ftp_net_pnl=ftp_values["ftp_net_pnl"],
                ftp_net_annualized_yield_pct=ftp_values["ftp_net_annualized_yield_pct"],
                asset_count=len(bucket["asset_codes"]) if bucket["asset_codes"] else 0,
            )
        )
    return rows

def _analysis_dimension_row_sort_key(
    item: dict[str, object],
    dimension: PnlByBusinessAnalysisDimension,
) -> tuple[object, ...]:
    if dimension == "monthly":
        return (str(item["dimension_key"]),)
    if dimension == "bond_bucket_monthly":
        dimension_key = str(item["dimension_key"])
        report_date = _analysis_dimension_report_date(dimension_key)
        bucket_key = dimension_key.split("::", 1)[1] if "::" in dimension_key else ""
        return (report_date, ANALYSIS_BOND_BUCKET_SORT.get(bucket_key, 99))
    if dimension == "bond_bucket":
        return (ANALYSIS_BOND_BUCKET_SORT.get(str(item["dimension_key"]), 99),)
    return (-abs(Decimal(str(item["total_pnl"]))), str(item["dimension_label"]))

def _analysis_matched_business_keys(classification: dict[str, object]) -> tuple[str, ...]:
    manual_key = _norm_text(classification.get("manual_business_row_key"))
    if manual_key:
        return (manual_key,)
    return tuple(str(row_def.get("row_key")) for row_def in match_zqtz_asset_bond_rows(classification))

def _analysis_bond_bucket_for_matched_keys(matched_keys: tuple[str, ...]) -> tuple[str, str]:
    matched_set = set(matched_keys)
    for bucket_key, label, row_keys in ANALYSIS_BOND_BUCKETS:
        if matched_set & row_keys:
            return bucket_key, label
    return "other_bond", ANALYSIS_BOND_BUCKET_LABELS["other_bond"]

def _analysis_global_bond_bucket_dimension_for_pnl_row(
    row: dict[str, object],
    matched_keys: tuple[str, ...],
    dimension: PnlByBusinessAnalysisDimension,
) -> tuple[str, str] | None:
    bucket_key, label = _analysis_bond_bucket_for_matched_keys(matched_keys)
    if dimension == "bond_bucket":
        return bucket_key, label
    report_date = _norm_text(row.get("report_date"))
    if not report_date:
        return None
    return f"{report_date}::{bucket_key}", f"{report_date} {label}"

def _analysis_global_bond_bucket_dimension_for_balance_row(
    row: dict[str, object],
    matched_keys: tuple[str, ...],
    dimension: PnlByBusinessAnalysisDimension,
    month_end_by_month: dict[str, str],
) -> tuple[str, str] | None:
    bucket_key, label = _analysis_bond_bucket_for_matched_keys(matched_keys)
    if dimension == "bond_bucket":
        return bucket_key, label
    report_date = _norm_text(row.get("report_date"))
    month_end = month_end_by_month.get(report_date[:7])
    if not month_end:
        return None
    return f"{month_end}::{bucket_key}", f"{month_end} {label}"

def _build_pnl_by_business_monthly_buckets(
    *,
    pnl_rows: tuple[dict[str, object], ...],
    balance_rows: tuple[dict[str, object], ...],
    loaded_dates: list[str],
) -> list[PnlByBusinessMonthlyBucket]:
    balance_rows_list = list(balance_rows)
    balance_lookup = _analysis_balance_lookup(balance_rows_list)
    historical_balance_lookup = _analysis_historical_balance_lookup(balance_rows_list)
    sub_type_by_date_code = _analysis_sub_type_by_date_code(balance_rows_list)
    month_end_by_month: dict[str, str] = {}
    for report_date in sorted(loaded_dates):
        month_end_by_month[str(report_date)[:7]] = str(report_date)

    buckets: list[PnlByBusinessMonthlyBucket] = []
    for month_key, month_end in sorted(month_end_by_month.items()):
        month_start = f"{month_key}-01"
        calendar_days = _calendar_days(month_start, month_end)
        groups: dict[str, dict[str, object]] = {
            str(row_def["row_key"]): _new_monthly_business_group(row_def) for row_def in ZQTZ_ASSET_BOND_ROWS
        }

        for pnl_row in pnl_rows:
            if _norm_text(pnl_row.get("report_date"))[:7] != month_key:
                continue
            classification = (
                _pnl_by_business_manual_classification(pnl_row)
                if _norm_text(pnl_row.get("source_kind")) == "manual_adjustment"
                else _analysis_classification_for_pnl_row(
                    pnl_row=pnl_row,
                    balance_lookup=balance_lookup,
                    historical_balance_lookup=historical_balance_lookup,
                    sub_type_by_date_code=sub_type_by_date_code,
                    fallback_date=month_end,
                )
            )
            for row_def in match_zqtz_asset_bond_rows(classification):
                _merge_monthly_business_pnl_row(groups, row_def, pnl_row)

        avg_sums: dict[str, Decimal] = {}
        current_sums: dict[str, Decimal] = {}
        coverage_dates: set[str] = set()
        for row in balance_rows:
            report_date = _norm_text(row.get("report_date"))
            if report_date[:7] != month_key:
                continue
            coverage_dates.add(report_date)
            classification = _analysis_classification_from_balance_row(row)
            for row_def in match_zqtz_asset_bond_rows(classification):
                row_key = str(row_def["row_key"])
                avg_sums[row_key] = avg_sums.get(row_key, Decimal("0")) + _decimal_value(row.get("avg_amount"))
                if report_date == month_end:
                    current_sums[row_key] = current_sums.get(row_key, Decimal("0")) + _decimal_value(
                        row.get("current_amount")
                    )

        denom = len(coverage_dates)
        item_inputs: list[tuple[dict[str, object], Decimal, Decimal]] = []
        parent_total = Decimal("0")
        for group in sorted(groups.values(), key=lambda item: (int(item["sort_order"]), str(item["row_key"]))):
            row_key = str(group["row_key"])
            if denom > 0:
                avg_balance = avg_sums.get(row_key, Decimal("0")) / Decimal(str(denom))
            else:
                avg_balance = Decimal("0")
            current_balance = current_sums.get(row_key, Decimal("0"))
            total_pnl = Decimal(str(group["total_pnl"]))
            if _is_parent_monthly_business_group(group):
                parent_total += total_pnl
            item_inputs.append((group, avg_balance, current_balance))

        items = [
            _monthly_business_item_from_group(
                group=group,
                avg_balance=avg_balance,
                current_balance=current_balance,
                total_pnl_for_proportion=parent_total,
                calendar_days=calendar_days,
            )
            for group, avg_balance, current_balance in item_inputs
        ]
        summary = _monthly_business_summary_from_items(items, calendar_days)
        buckets.append(
            PnlByBusinessMonthlyBucket(
                month_key=month_key,
                period_start_date=month_start,
                period_end_date=month_end,
                calendar_days=calendar_days,
                summary=summary,
                items=items,
            )
        )
    return buckets

def _new_monthly_business_group(row_def: dict[str, object]) -> dict[str, object]:
    return {
        "row_key": str(row_def["row_key"]),
        "sort_order": int(row_def["sort_order"]),
        "business_type": str(row_def["row_label"]),
        "source_note": str(row_def.get("source_note") or "ZQTZ_ASSET_BOND_ROWS"),
        "interest_income": Decimal("0"),
        "fair_value_change": Decimal("0"),
        "capital_gain": Decimal("0"),
        "manual_adjustment": Decimal("0"),
        "total_pnl": Decimal("0"),
        "asset_codes": set(),
        "row_count": 0,
    }

def _merge_monthly_business_pnl_row(
    groups: dict[str, dict[str, object]],
    row_def: dict[str, object],
    row: dict[str, object],
) -> None:
    row_key = str(row_def["row_key"])
    group = groups.setdefault(row_key, _new_monthly_business_group(row_def))
    group["interest_income"] = Decimal(str(group["interest_income"])) + _decimal_value(row.get("interest_income_514"))
    group["fair_value_change"] = Decimal(str(group["fair_value_change"])) + _decimal_value(row.get("fair_value_change_516"))
    group["capital_gain"] = Decimal(str(group["capital_gain"])) + _decimal_value(row.get("capital_gain_517"))
    group["manual_adjustment"] = Decimal(str(group["manual_adjustment"])) + _decimal_value(row.get("manual_adjustment"))
    group["total_pnl"] = Decimal(str(group["total_pnl"])) + _decimal_value(row.get("total_pnl"))
    code = _norm_text(row.get("instrument_code"))
    if code:
        group["asset_codes"].add(code)
    group["row_count"] = int(group["row_count"]) + 1

def _monthly_business_item_from_group(
    *,
    group: dict[str, object],
    avg_balance: Decimal,
    current_balance: Decimal,
    total_pnl_for_proportion: Decimal,
    calendar_days: int,
) -> PnlByBusinessMonthlyItem:
    total_pnl = Decimal(str(group["total_pnl"]))
    annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days)
    ftp_values = _analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
    )
    return PnlByBusinessMonthlyItem(
        row_key=str(group["row_key"]),
        sort_order=int(group["sort_order"]),
        business_type=str(group["business_type"]),
        interest_income=_quantize_decimal(Decimal(str(group["interest_income"]))),
        fair_value_change=_quantize_decimal(Decimal(str(group["fair_value_change"]))),
        capital_gain=_quantize_decimal(Decimal(str(group["capital_gain"]))),
        manual_adjustment=_quantize_decimal(Decimal(str(group["manual_adjustment"]))),
        total_pnl=_quantize_decimal(total_pnl),
        avg_balance=_quantize_decimal(avg_balance),
        current_balance=_quantize_decimal(current_balance),
        annualized_yield_pct=annualized_yield_pct,
        ftp_rate_pct=FTP_RATE_PCT,
        ftp_cost=ftp_values["ftp_cost"],
        ftp_net_pnl=ftp_values["ftp_net_pnl"],
        ftp_net_annualized_yield_pct=ftp_values["ftp_net_annualized_yield_pct"],
        proportion=(
            _quantize_ratio(total_pnl / total_pnl_for_proportion)
            if total_pnl_for_proportion != Decimal("0")
            else None
        ),
        asset_count=len(group["asset_codes"]) if group["asset_codes"] else int(group["row_count"]),
        source_note=str(group.get("source_note") or "ZQTZ_ASSET_BOND_ROWS"),
    )

def _monthly_business_summary_from_items(
    items: list[PnlByBusinessMonthlyItem],
    calendar_days: int,
) -> PnlByBusinessMonthlySummary:
    parent_items = [item for item in items if _is_parent_monthly_business_item(item)]
    interest_income = sum((Decimal(str(item.interest_income)) for item in parent_items), Decimal("0"))
    fair_value_change = sum((Decimal(str(item.fair_value_change)) for item in parent_items), Decimal("0"))
    capital_gain = sum((Decimal(str(item.capital_gain)) for item in parent_items), Decimal("0"))
    manual_adjustment = sum((Decimal(str(item.manual_adjustment)) for item in parent_items), Decimal("0"))
    total_pnl = sum((Decimal(str(item.total_pnl)) for item in parent_items), Decimal("0"))
    avg_balance = sum((Decimal(str(item.avg_balance)) for item in parent_items), Decimal("0"))
    current_balance = sum((Decimal(str(item.current_balance)) for item in parent_items), Decimal("0"))
    annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days)
    ftp_values = _analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
    )
    return PnlByBusinessMonthlySummary(
        interest_income=_quantize_decimal(interest_income),
        fair_value_change=_quantize_decimal(fair_value_change),
        capital_gain=_quantize_decimal(capital_gain),
        manual_adjustment=_quantize_decimal(manual_adjustment),
        total_pnl=_quantize_decimal(total_pnl),
        avg_balance=_quantize_decimal(avg_balance),
        current_balance=_quantize_decimal(current_balance),
        annualized_yield_pct=annualized_yield_pct,
        ftp_rate_pct=FTP_RATE_PCT,
        ftp_cost=ftp_values["ftp_cost"],
        ftp_net_pnl=ftp_values["ftp_net_pnl"],
        ftp_net_annualized_yield_pct=ftp_values["ftp_net_annualized_yield_pct"],
        asset_count=sum(item.asset_count for item in parent_items),
    )

def _is_parent_monthly_business_group(group: dict[str, object]) -> bool:
    if "_detail_" in str(group.get("row_key") or ""):
        return False
    business_type = str(group.get("business_type") or "")
    if business_type.startswith("其中"):
        return False
    return "其中项" not in str(group.get("source_note") or "")

def _is_parent_monthly_business_item(item: PnlByBusinessMonthlyItem) -> bool:
    if "_detail_" in item.row_key:
        return False
    if item.business_type.startswith("其中"):
        return False
    return "其中项" not in str(item.source_note or "")

def _new_analysis_dimension_bucket(dimension_key: str, dimension_label: str) -> dict[str, object]:
    return {
        "dimension_key": dimension_key,
        "dimension_label": dimension_label,
        "interest_income": Decimal("0"),
        "fair_value_change": Decimal("0"),
        "capital_gain": Decimal("0"),
        "manual_adjustment": Decimal("0"),
        "total_pnl": Decimal("0"),
        "asset_codes": set(),
    }

def _analysis_balance_lookup(balance_rows: list[dict[str, object]]) -> dict[tuple[str, str, str, str, str], dict[str, object]]:
    lookup: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        portfolio_name = _norm_text(row.get("portfolio_name"))
        cost_center = _norm_text(row.get("cost_center"))
        currency_basis = _norm_text(row.get("currency_basis")) or "CNY"
        for code in _instrument_code_variants(row.get("instrument_code")):
            lookup.setdefault((report_date, code, portfolio_name, cost_center, currency_basis), row)
    return lookup

def _analysis_historical_balance_lookup(
    balance_rows: list[dict[str, object]],
) -> dict[tuple[str, str, str, str], list[dict[str, object]]]:
    lookup: dict[tuple[str, str, str, str], list[dict[str, object]]] = {}
    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        portfolio_name = _norm_text(row.get("portfolio_name"))
        cost_center = _norm_text(row.get("cost_center"))
        currency_basis = _norm_text(row.get("currency_basis")) or "CNY"
        if not report_date:
            continue
        for code in _instrument_code_variants(row.get("instrument_code")):
            lookup.setdefault((code, portfolio_name, cost_center, currency_basis), []).append(row)
    for rows in lookup.values():
        rows.sort(key=lambda item: _norm_text(item.get("report_date")))
    return lookup

def _analysis_latest_balance_before_or_on(
    lookup: dict[tuple[str, str, str, str], list[dict[str, object]]],
    key: tuple[str, str, str, str],
    report_date: str,
) -> dict[str, object] | None:
    rows = lookup.get(key)
    if not rows or not report_date:
        return None
    latest: dict[str, object] | None = None
    for row in rows:
        row_date = _norm_text(row.get("report_date"))
        if row_date > report_date:
            break
        latest = row
    return latest

def _analysis_sub_type_by_date_code(balance_rows: list[dict[str, object]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        sub_type = _norm_text(row.get("sub_type")) or _norm_text(row.get("business_type_primary"))
        if not report_date or not sub_type:
            continue
        for code in _instrument_code_variants(row.get("instrument_code")):
            out.setdefault((report_date, code), sub_type)
    return out

def _analysis_classification_for_pnl_row(
    *,
    pnl_row: dict[str, object],
    balance_lookup: dict[tuple[str, str, str, str, str], dict[str, object]],
    sub_type_by_date_code: dict[tuple[str, str], str],
    fallback_date: str,
    historical_balance_lookup: dict[tuple[str, str, str, str], list[dict[str, object]]] | None = None,
) -> dict[str, object]:
    report_date = _norm_text(pnl_row.get("report_date"))
    portfolio_name = _norm_text(pnl_row.get("portfolio_name"))
    cost_center = _norm_text(pnl_row.get("cost_center"))
    currency_basis = _norm_text(pnl_row.get("currency_basis")) or "CNY"
    for code in _instrument_code_variants(pnl_row.get("instrument_code")):
        balance_row = balance_lookup.get((report_date, code, portfolio_name, cost_center, currency_basis))
        if balance_row is not None:
            return _analysis_classification_from_balance_row(balance_row)

    if historical_balance_lookup is not None:
        classification_date = report_date or fallback_date
        for code in _instrument_code_variants(pnl_row.get("instrument_code")):
            balance_row = _analysis_latest_balance_before_or_on(
                historical_balance_lookup,
                (code, portfolio_name, cost_center, currency_basis),
                classification_date,
            )
            if balance_row is not None:
                return _analysis_classification_from_balance_row(balance_row)

    code = _norm_text(pnl_row.get("instrument_code"))
    sub_type = sub_type_by_date_code.get((report_date, code), "") or sub_type_by_date_code.get((fallback_date, code), "")
    if _norm_text(pnl_row.get("source_kind")) == "nonstd_bridge":
        return _v1_nonstd_classification_row(report_date=report_date or fallback_date, code=code, sub_type=sub_type)
    invest = _norm_text(pnl_row.get("invest_type_std")) or "unclassified"
    classification = _v1_fi_classification_row(
        report_date=report_date or fallback_date,
        row={
            "instrument_code": code,
            "currency_basis": currency_basis,
            "currency_code": currency_basis,
            "instrument_name": code,
            "accounting_basis": _norm_text(pnl_row.get("accounting_basis")),
        },
        code=code,
        asset_class=invest,
        sub_type=sub_type or invest,
    )
    classification["accounting_basis"] = _norm_text(pnl_row.get("accounting_basis"))
    return classification

def _analysis_classification_from_balance_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "report_date": _norm_text(row.get("report_date")),
        "instrument_code": _norm_text(row.get("instrument_code")),
        "instrument_name": _norm_text(row.get("instrument_name")),
        "account_category": _norm_text(row.get("account_category")),
        "asset_class": _norm_text(row.get("asset_class")),
        "bond_type": _norm_text(row.get("bond_type")),
        "sub_type": _norm_text(row.get("sub_type")),
        "business_type_primary": _norm_text(row.get("business_type_primary")),
        "business_type_final": _norm_text(row.get("business_type_final")),
        "invest_type_std": _norm_text(row.get("invest_type_std")),
        "accounting_basis": _norm_text(row.get("accounting_basis")),
        "currency_code": _norm_text(row.get("currency_code")),
    }

def _analysis_dimension_for_pnl_row(
    row: dict[str, object],
    classification: dict[str, object],
    dimension: PnlByBusinessAnalysisDimension,
) -> tuple[str, str] | None:
    if dimension == "monthly":
        report_date = _norm_text(row.get("report_date"))
        return (report_date, report_date) if report_date else None
    if dimension == "portfolio":
        return _dimension_key_label(row.get("portfolio_name"), "未填组合")
    if dimension == "accounting":
        return _dimension_key_label(row.get("accounting_basis") or classification.get("accounting_basis"), "未填会计分类")
    if dimension == "cost_center":
        return _dimension_key_label(row.get("cost_center"), "未填成本中心")
    if dimension == "bond_bucket":
        return _analysis_bond_bucket_for_classification(classification)
    if dimension == "bond_bucket_monthly":
        report_date = _norm_text(row.get("report_date"))
        if not report_date:
            return None
        bucket_key, label = _analysis_bond_bucket_for_classification(classification)
        return f"{report_date}::{bucket_key}", f"{report_date} {label}"
    return _instrument_key_label(row.get("instrument_code"), classification.get("instrument_name"))

def _analysis_dimension_for_balance_row(
    row: dict[str, object],
    dimension: PnlByBusinessAnalysisDimension,
    month_end_by_month: dict[str, str],
) -> tuple[str, str] | None:
    if dimension == "monthly":
        report_date = _norm_text(row.get("report_date"))
        month_end = month_end_by_month.get(report_date[:7])
        return (month_end, month_end) if month_end else None
    if dimension == "portfolio":
        return _dimension_key_label(row.get("portfolio_name"), "未填组合")
    if dimension == "accounting":
        return _dimension_key_label(row.get("accounting_basis"), "未填会计分类")
    if dimension == "cost_center":
        return _dimension_key_label(row.get("cost_center"), "未填成本中心")
    if dimension == "bond_bucket":
        return _analysis_bond_bucket_for_classification(_analysis_classification_from_balance_row(row))
    if dimension == "bond_bucket_monthly":
        report_date = _norm_text(row.get("report_date"))
        month_end = month_end_by_month.get(report_date[:7])
        if not month_end:
            return None
        bucket_key, label = _analysis_bond_bucket_for_classification(_analysis_classification_from_balance_row(row))
        return f"{month_end}::{bucket_key}", f"{month_end} {label}"
    return _instrument_key_label(row.get("instrument_code"), row.get("instrument_name"))

def _dimension_key_label(value: object, blank_label: str) -> tuple[str, str]:
    text = _norm_text(value)
    if text:
        return text, text
    return f"__blank__{blank_label}", blank_label

def _analysis_bond_bucket_for_classification(classification: dict[str, object]) -> tuple[str, str]:
    matched_keys = {str(row_def.get("row_key")) for row_def in match_zqtz_asset_bond_rows(classification)}
    for bucket_key, label, row_keys in ANALYSIS_BOND_BUCKETS:
        if matched_keys & row_keys:
            return bucket_key, label
    return "other_bond", ANALYSIS_BOND_BUCKET_LABELS["other_bond"]

def _analysis_is_monthly_dimension(dimension: PnlByBusinessAnalysisDimension) -> bool:
    return dimension in {"monthly", "bond_bucket_monthly"}

def _analysis_dimension_report_date(dimension_key: str) -> str:
    return dimension_key.split("::", 1)[0]

def _instrument_key_label(code_value: object, name_value: object) -> tuple[str, str]:
    code = _norm_text(code_value)
    name = _norm_text(name_value)
    key = code or "__blank__instrument"
    if code and name and name != code:
        return key, f"{code} {name}"
    return key, code or name or "未填资产"

def _instrument_code_variants(value: object) -> tuple[str, ...]:
    code = _norm_text(value)
    if not code:
        return tuple()
    variants = {code}
    if code.startswith("BOND-"):
        variants.add(code[5:])
    else:
        variants.add(f"BOND-{code}")
    return tuple(sorted(variants))

def _analysis_annualized_yield_pct(total_pnl: Decimal, avg_balance: Decimal, calendar_days: int) -> Decimal | None:
    if avg_balance <= Decimal("0") or calendar_days <= 0:
        return None
    return _quantize_yield_pct((total_pnl / avg_balance) * Decimal("365") / Decimal(str(calendar_days)) * Decimal("100"))

def _analysis_ftp_values(
    *,
    total_pnl: Decimal,
    avg_balance: Decimal,
    annualized_yield_pct: Decimal | None,
    calendar_days: int,
) -> dict[str, Decimal | None]:
    if avg_balance <= Decimal("0") or calendar_days <= 0 or annualized_yield_pct is None:
        return {
            "ftp_cost": None,
            "ftp_net_pnl": None,
            "ftp_net_annualized_yield_pct": None,
        }
    ftp_cost = avg_balance * FTP_RATE_RATIO * Decimal(str(calendar_days)) / Decimal("365")
    return {
        "ftp_cost": _quantize_decimal(ftp_cost),
        "ftp_net_pnl": _quantize_decimal(total_pnl - ftp_cost),
        "ftp_net_annualized_yield_pct": _quantize_yield_pct(annualized_yield_pct - FTP_RATE_PCT),
    }

def _calendar_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    return max((end - start).days + 1, 0)

def _decimal_value(value: object) -> Decimal:
    return Decimal(str(value or "0"))

def _norm_text(value: object) -> str:
    return str(value or "").strip()

def _v1_fi_classification_row(
    *,
    report_date: str,
    row: dict[str, object],
    code: str,
    asset_class: str,
    sub_type: str,
) -> dict[str, object]:
    currency_code = str(row.get("fx_base_currency") or row.get("currency_code") or row.get("currency_basis") or "CNY")
    return {
        "report_date": report_date,
        "instrument_code": code,
        "sub_type": sub_type,
        "business_type_final": sub_type,
        "business_type_primary": sub_type or asset_class,
        "bond_type": asset_class or sub_type,
        "instrument_name": str(row.get("instrument_name") or row.get("bond_name") or code),
        "asset_class": asset_class,
        "currency_code": currency_code.strip().upper() or "CNY",
    }

def _v1_nonstd_classification_row(*, report_date: str, code: str, sub_type: str) -> dict[str, object]:
    bond_type = _zqtz_other_bond_type()
    code_u = code.upper()
    return {
        "report_date": report_date,
        "instrument_code": code,
        "sub_type": sub_type,
        "business_type_final": sub_type,
        "business_type_primary": bond_type,
        "bond_type": bond_type,
        "instrument_name": code,
        "asset_class": sub_type or bond_type,
        "currency_code": "USD" if code_u.startswith("J1") else "CNY",
    }

def _zqtz_other_bond_type() -> str:
    for row_def in ZQTZ_ASSET_BOND_ROWS:
        if row_def.get("row_key") == "asset_zqtz_non_bottom_investment":
            bond_types = tuple(str(value) for value in row_def.get("bond_types", ()))
            if bond_types:
                return bond_types[0]
    return "其他"

def _quantize_decimal(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES)

def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIOPLACES)

def _quantize_yield_pct(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.000001"))
