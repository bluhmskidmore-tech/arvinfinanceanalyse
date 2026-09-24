"""pnl_service 门面的分析维度子模块：by-business 分析的维度/分类叶子工具（自 pnl_service.py 逐字拆出）。"""
from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.field_normalization import original_asset_currency_from_instrument_code
from backend.app.core_finance.pnl import compute_pnl_by_business_yield_and_ftp
from backend.app.schemas.pnl import PnlByBusinessAnalysisDimension
from backend.app.services.pnl_service_shared_utils import _calendar_days, _norm_text


def _balance_coverage_diagnostics(
    balance_rows: list[dict[str, object]] | tuple[dict[str, object], ...],
    *,
    period_start: str,
    period_end: str,
) -> tuple[int, int, bool, str | None]:
    coverage_dates = {
        report_date
        for row in balance_rows
        if (report_date := _norm_text(row.get("report_date"))) and period_start <= report_date <= period_end
    }
    coverage_days = len(coverage_dates)
    expected_days = _calendar_days(period_start, period_end)
    sample_filled = 0 < coverage_days < expected_days
    sample_fill_method = "observed_days_scaled_to_calendar" if sample_filled else None
    return coverage_days, expected_days, sample_filled, sample_fill_method


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


def _analysis_original_currency_dimension(
    instrument_code: object,
    currency_code: object = None,
) -> tuple[str, str]:
    if original_asset_currency_from_instrument_code(instrument_code, currency_code) == "USD":
        return "USD", "美元（折人民币）"
    return "CNY", "人民币"


def _dimension_key_label(value: object, blank_label: str) -> tuple[str, str]:
    text = _norm_text(value)
    if text:
        return text, text
    return f"__blank__{blank_label}", blank_label


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


def _analysis_annualized_yield_pct(
    total_pnl: Decimal,
    avg_balance: Decimal,
    calendar_days: int,
    ftp_rate_pct: Decimal,
) -> Decimal | None:
    return compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    ).annualized_yield_pct


def _analysis_ftp_values(
    *,
    total_pnl: Decimal,
    avg_balance: Decimal,
    annualized_yield_pct: Decimal | None,
    calendar_days: int,
    ftp_rate_pct: Decimal,
) -> dict[str, Decimal | None]:
    yield_ftp = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )
    return {
        "ftp_rate_pct": yield_ftp.ftp_rate_pct,
        "ftp_cost": yield_ftp.ftp_cost,
        "ftp_net_pnl": yield_ftp.ftp_net_pnl,
        "ftp_net_annualized_yield_pct": yield_ftp.ftp_net_annualized_yield_pct,
    }
