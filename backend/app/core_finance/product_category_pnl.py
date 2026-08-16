from __future__ import annotations

from calendar import monthrange
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from backend.app.core_finance.field_normalization import is_approved_status

ZERO = Decimal("0")
DAYS_IN_YEAR = Decimal("365")
ASSET_SCALE_EXCLUSIONS = {
    "\u751f\u606f\u8d44\u4ea7",
    "\u884d\u751f\u54c1",
    "\u4e2d\u95f4\u4e1a\u52a1\u6536\u5165",
}
ASSET_PNL_EXCLUSIONS = {"\u751f\u606f\u8d44\u4ea7"}
PRODUCT_CATEGORY_RATE_RAW_QUANT = Decimal("0.00000001")
PRODUCT_CATEGORY_RATE_DISPLAY_QUANT = Decimal("0.01")
# Percent rates display at 2 decimals, i.e. 1bp resolution. A bp-denominated value
# rendered at 2 decimals would claim 0.01bp resolution the underlying rates do not
# have, so bp displays stop at 1 decimal. The 8-decimal raw is kept for audit.
PRODUCT_CATEGORY_BP_DISPLAY_QUANT = Decimal("0.1")
FTP_RESULT_FIELDS = ("cny_ftp", "foreign_ftp", "cny_net", "foreign_net", "business_net_income")


@dataclass(slots=True)
class CanonicalFactRow:
    report_date: date
    account_code: str
    currency: str
    account_name: str
    beginning_balance: Decimal
    ending_balance: Decimal
    monthly_pnl: Decimal
    daily_avg_balance: Decimal
    annual_avg_balance: Decimal
    days_in_period: int


@dataclass(slots=True)
class ManualAdjustment:
    report_date: date
    operator: str
    approval_status: str
    account_code: str
    currency: str
    account_name: str = ""
    beginning_balance: Decimal | None = None
    ending_balance: Decimal | None = None
    monthly_pnl: Decimal | None = None
    daily_avg_balance: Decimal | None = None
    annual_avg_balance: Decimal | None = None


@dataclass(slots=True)
class ProductCategoryMetricValue:
    raw: Decimal
    display: str
    unit: Literal["percent", "bp"] = "percent"


@dataclass(slots=True)
class ProductCategoryLiabilityCostDecomposition:
    liability_yield_pct: ProductCategoryMetricValue | None
    liability_yield_ex_cln_pct: ProductCategoryMetricValue | None
    cln_yield_pct: ProductCategoryMetricValue | None
    cln_drag_bp: ProductCategoryMetricValue | None
    cln_scale: Decimal | None


@dataclass(slots=True)
class ProductCategoryInterestSpreadMetrics:
    all_currency_asset_yield_pct: ProductCategoryMetricValue | None
    all_currency_liability_yield_pct: ProductCategoryMetricValue | None
    all_currency_spread_pct: ProductCategoryMetricValue | None
    cny_asset_yield_pct: ProductCategoryMetricValue | None
    cny_liability_yield_pct: ProductCategoryMetricValue | None
    cny_spread_pct: ProductCategoryMetricValue | None


def derive_monthly_pnl(period_debit: Decimal, period_credit: Decimal) -> Decimal:
    return period_credit - period_debit


def calculate_product_category_interest_spread_metrics(
    *,
    report_date: date | str,
    view: str,
    asset_row: Mapping[str, object],
    liability_row: Mapping[str, object],
) -> ProductCategoryInterestSpreadMetrics:
    days_for_view = _days_for_view(_parse_report_date(report_date), view)

    all_currency_asset_yield = _decimal_or_none(asset_row.get("weighted_yield"))
    all_currency_liability_yield = _decimal_or_none(liability_row.get("weighted_yield"))
    cny_asset_yield = _calculate_weighted_yield_from_row(asset_row, "cny_cash", "cny_scale", days_for_view)
    cny_liability_yield = _calculate_weighted_yield_from_row(
        liability_row,
        "cny_cash",
        "cny_scale",
        days_for_view,
    )

    return ProductCategoryInterestSpreadMetrics(
        all_currency_asset_yield_pct=_build_product_category_metric_value(all_currency_asset_yield),
        all_currency_liability_yield_pct=_build_product_category_metric_value(all_currency_liability_yield),
        all_currency_spread_pct=_build_product_category_metric_value(
            _subtract_when_present(all_currency_asset_yield, all_currency_liability_yield)
        ),
        cny_asset_yield_pct=_build_product_category_metric_value(cny_asset_yield),
        cny_liability_yield_pct=_build_product_category_metric_value(cny_liability_yield),
        cny_spread_pct=_build_product_category_metric_value(
            _subtract_when_present(cny_asset_yield, cny_liability_yield)
        ),
    )


def calculate_product_category_liability_cost_decomposition(
    *,
    report_date: date | str,
    view: str,
    liability_row: Mapping[str, object],
    credit_linked_notes_row: Mapping[str, object] | None,
) -> ProductCategoryLiabilityCostDecomposition:
    """Split the liability-side cost rate into an ex-CLN base and the CLN drag.

    Liability rows carry negative `cnx_scale` / `cnx_cash`, so the negative-over-negative
    quotient stays positive and matches the existing `weighted_yield` convention. The
    decomposition is meaningful only when total, CLN, and ex-CLN scales all preserve
    the liability-side negative sign. Missing rows or invalid denominators therefore
    return every field as None instead of falling back to 0.
    """
    empty = ProductCategoryLiabilityCostDecomposition(
        liability_yield_pct=None,
        liability_yield_ex_cln_pct=None,
        cln_yield_pct=None,
        cln_drag_bp=None,
        cln_scale=None,
    )
    if credit_linked_notes_row is None:
        return empty

    liability_scale = _decimal_or_none(liability_row.get("cnx_scale"))
    liability_cash = _decimal_or_none(liability_row.get("cnx_cash"))
    cln_scale = _decimal_or_none(credit_linked_notes_row.get("cnx_scale"))
    cln_cash = _decimal_or_none(credit_linked_notes_row.get("cnx_cash"))
    if liability_scale is None or liability_cash is None or cln_scale is None or cln_cash is None:
        return empty

    ex_cln_scale = liability_scale - cln_scale
    if liability_scale >= ZERO or cln_scale >= ZERO or ex_cln_scale >= ZERO:
        return empty

    days_for_view = _days_for_view(_parse_report_date(report_date), view)
    liability_yield = _decimal_or_none(liability_row.get("weighted_yield"))
    cln_yield = _decimal_or_none(credit_linked_notes_row.get("weighted_yield"))
    ex_cln_yield = _calculate_weighted_yield(liability_cash - cln_cash, ex_cln_scale, days_for_view)
    drag = _subtract_when_present(liability_yield, ex_cln_yield)

    return ProductCategoryLiabilityCostDecomposition(
        liability_yield_pct=_build_product_category_metric_value(liability_yield),
        liability_yield_ex_cln_pct=_build_product_category_metric_value(ex_cln_yield),
        cln_yield_pct=_build_product_category_metric_value(cln_yield),
        cln_drag_bp=_build_product_category_bp_metric_value(
            None if drag is None else drag * Decimal("100")
        ),
        cln_scale=cln_scale,
    )


def apply_manual_adjustments(
    rows: list[CanonicalFactRow],
    adjustments: list[ManualAdjustment],
) -> list[CanonicalFactRow]:
    approved = [item for item in adjustments if _is_approved_status(item.approval_status)]
    by_key = {(row.account_code, row.currency): row for row in rows}

    for operator in ("ADD", "DELTA", "OVERRIDE"):
        for adjustment in approved:
            if adjustment.operator != operator:
                continue
            key = (adjustment.account_code, adjustment.currency)
            existing = by_key.get(key)

            if operator == "ADD":
                if existing is not None:
                    continue
                by_key[key] = CanonicalFactRow(
                    report_date=adjustment.report_date,
                    account_code=adjustment.account_code,
                    currency=adjustment.currency,
                    account_name=adjustment.account_name,
                    beginning_balance=adjustment.beginning_balance or ZERO,
                    ending_balance=adjustment.ending_balance or ZERO,
                    monthly_pnl=adjustment.monthly_pnl or ZERO,
                    daily_avg_balance=adjustment.daily_avg_balance or ZERO,
                    annual_avg_balance=adjustment.annual_avg_balance or ZERO,
                    days_in_period=monthrange(adjustment.report_date.year, adjustment.report_date.month)[1],
                )
                continue

            if existing is None:
                continue

            if operator == "DELTA":
                by_key[key] = replace(
                    existing,
                    account_name=adjustment.account_name or existing.account_name,
                    beginning_balance=existing.beginning_balance + (adjustment.beginning_balance or ZERO),
                    ending_balance=existing.ending_balance + (adjustment.ending_balance or ZERO),
                    monthly_pnl=existing.monthly_pnl + (adjustment.monthly_pnl or ZERO),
                    daily_avg_balance=existing.daily_avg_balance + (adjustment.daily_avg_balance or ZERO),
                    annual_avg_balance=existing.annual_avg_balance + (adjustment.annual_avg_balance or ZERO),
                )
                continue

            by_key[key] = replace(
                existing,
                account_name=adjustment.account_name or existing.account_name,
                beginning_balance=existing.beginning_balance if adjustment.beginning_balance is None else adjustment.beginning_balance,
                ending_balance=existing.ending_balance if adjustment.ending_balance is None else adjustment.ending_balance,
                monthly_pnl=existing.monthly_pnl if adjustment.monthly_pnl is None else adjustment.monthly_pnl,
                daily_avg_balance=existing.daily_avg_balance if adjustment.daily_avg_balance is None else adjustment.daily_avg_balance,
                annual_avg_balance=existing.annual_avg_balance if adjustment.annual_avg_balance is None else adjustment.annual_avg_balance,
            )

    return list(by_key.values())


def calculate_read_model(
    facts_by_report_date: dict[date, list[CanonicalFactRow]],
    report_date: date,
    view: str,
    config: list[dict[str, object]],
) -> dict[str, object]:
    if report_date not in facts_by_report_date:
        raise ValueError(f"Missing canonical facts for report_date={report_date}")

    report_rows = _build_report_rows(facts_by_report_date, report_date, view)
    days_for_view = _days_for_view(report_date, view)
    config_by_id = {str(item["id"]): item for item in config}
    child_map = {
        str(item["id"]): [str(child) for child in item.get("children", [])]
        for item in config
    }
    computed: dict[str, dict[str, object]] = {}

    def compute_category(category_id: str) -> dict[str, object]:
        if category_id in computed:
            return computed[category_id]

        category = config_by_id[category_id]
        child_ids = child_map.get(category_id, [])
        scale_field = _scale_field(report_date, view)
        scale_cnx = _calculate_sum(report_rows, category["scale_accounts"], scale_field, "CNX", exact=True)
        scale_cny = _calculate_sum(report_rows, category["scale_accounts"], scale_field, "CNY", exact=True)
        scale_foreign = scale_cnx - scale_cny
        ftp_rate_pct = Decimal(str(category["ftp_rate_pct"]))
        ftp_rate = ftp_rate_pct / Decimal("100")

        if child_ids:
            child_rows = [compute_category(child_id) for child_id in child_ids]
            cnx_cash = sum((Decimal(str(item["cnx_cash"])) for item in child_rows), ZERO)
            cny_cash = sum((Decimal(str(item["cny_cash"])) for item in child_rows), ZERO)
            foreign_cash = sum((Decimal(str(item["foreign_cash"])) for item in child_rows), ZERO)
            cny_ftp = sum((Decimal(str(item["cny_ftp"])) for item in child_rows), ZERO)
            foreign_ftp = sum((Decimal(str(item["foreign_ftp"])) for item in child_rows), ZERO)
        else:
            # 2026-08 B8 口径修正：所有受治理视图（monthly/qtd/ytd/year_to_report_month_end）
            # 的现金均为期间发生额口径——monthly 取单月 monthly_pnl，qtd/ytd 由
            # _build_report_rows 预先按期间内各月 monthly_pnl 累加。历史 qtd 曾走
            # "季末月期末余额取负"路径，与期间收益率公式（cash/days*365/scale，
            # docs/metric_dictionary.md §12.3.2）不自洽，已移除。
            cnx_cash = _calculate_sum(report_rows, category["pnl_accounts"], "monthly_pnl", "CNX", exact=False)
            cny_cash = _calculate_sum(report_rows, category["pnl_accounts"], "monthly_pnl", "CNY", exact=False)
            foreign_cash = cnx_cash - cny_cash
            cny_ftp = _calculate_ftp(scale_cny, ftp_rate, days_for_view)
            foreign_ftp = _calculate_ftp(scale_foreign, ftp_rate, days_for_view)

        cny_net = cny_cash - cny_ftp
        foreign_net = foreign_cash - foreign_ftp
        business_net_income = cny_net + foreign_net
        weighted_yield = _calculate_weighted_yield(cnx_cash, scale_cnx, days_for_view)

        result = {
            "category_id": category_id,
            "category_name": str(category["name"]),
            "side": str(category["side"]),
            "level": int(category["level"]),
            "view": view,
            "report_date": report_date.isoformat(),
            "baseline_ftp_rate_pct": ftp_rate_pct,
            "cnx_scale": scale_cnx,
            "cny_scale": scale_cny,
            "foreign_scale": scale_foreign,
            "cnx_cash": cnx_cash,
            "cny_cash": cny_cash,
            "foreign_cash": foreign_cash,
            "cny_ftp": cny_ftp,
            "foreign_ftp": foreign_ftp,
            "cny_net": cny_net,
            "foreign_net": foreign_net,
            "business_net_income": business_net_income,
            "weighted_yield": weighted_yield,
            "is_total": False,
            "children": child_ids,
        }
        computed[category_id] = result
        return result

    level_zero_rows = [compute_category(str(item["id"])) for item in config if int(item["level"]) == 0]
    asset_rows = [row for row in level_zero_rows if row["side"] == "asset"]
    liability_rows = [row for row in level_zero_rows if row["side"] == "liability"]
    asset_total = _build_total_row(
        "\u8d44\u4ea7\u7aef\u5408\u8ba1",
        "asset",
        asset_rows,
        days_for_view,
        scale_exclusions=ASSET_SCALE_EXCLUSIONS,
        pnl_exclusions=ASSET_PNL_EXCLUSIONS,
    )
    liability_total = _build_total_row(
        "\u8d1f\u503a\u7aef\u5408\u8ba1",
        "liability",
        liability_rows,
        days_for_view,
    )
    baseline_rate = Decimal(str(asset_total["baseline_ftp_rate_pct"])) if asset_rows else ZERO
    grand_cnx_cash = Decimal(str(asset_total["cnx_cash"])) + Decimal(str(liability_total["cnx_cash"]))
    grand_cny_cash = Decimal(str(asset_total["cny_cash"])) + Decimal(str(liability_total["cny_cash"]))
    grand_foreign_cash = Decimal(str(asset_total["foreign_cash"])) + Decimal(str(liability_total["foreign_cash"]))
    grand_cny_ftp = Decimal(str(asset_total["cny_ftp"])) + Decimal(str(liability_total["cny_ftp"]))
    grand_foreign_ftp = Decimal(str(asset_total["foreign_ftp"])) + Decimal(str(liability_total["foreign_ftp"]))
    grand_cny_net = Decimal(str(asset_total["cny_net"])) + Decimal(str(liability_total["cny_net"]))
    grand_foreign_net = Decimal(str(asset_total["foreign_net"])) + Decimal(str(liability_total["foreign_net"]))
    grand_business_net_income = grand_cny_net + grand_foreign_net
    grand_total = {
        "category_id": "grand_total",
        "category_name": "grand_total",
        "side": "all",
        "level": 0,
        "view": view,
        "report_date": report_date.isoformat(),
        "baseline_ftp_rate_pct": baseline_rate,
        "cnx_scale": ZERO,
        "cny_scale": ZERO,
        "foreign_scale": ZERO,
        "cnx_cash": grand_cnx_cash,
        "cny_cash": grand_cny_cash,
        "foreign_cash": grand_foreign_cash,
        "cny_ftp": grand_cny_ftp,
        "foreign_ftp": grand_foreign_ftp,
        "cny_net": grand_cny_net,
        "foreign_net": grand_foreign_net,
        "business_net_income": grand_business_net_income,
        "weighted_yield": None,
        "is_total": True,
        "children": [],
    }

    ordered_rows = [computed[str(item["id"])] for item in config]
    ordered_rows.extend([asset_total, liability_total, grand_total])
    return {
        "rows": ordered_rows,
        "asset_total": asset_total,
        "liability_total": liability_total,
        "grand_total": grand_total,
    }


def apply_scenario_to_rows(rows: list[dict[str, object]], scenario_rate_pct: Decimal) -> list[dict[str, object]]:
    _validate_reprice_baselines(rows)
    adjusted: list[dict[str, object]] = []
    used_direct_reprice = False
    for row in rows:
        baseline_rate = Decimal(str(row["baseline_ftp_rate_pct"]))
        ftp_amounts = _reprice_ftp_amounts(
            row,
            current_rate_pct=baseline_rate,
            target_rate_pct=scenario_rate_pct,
        )
        cloned = _with_ftp_amounts(row, *ftp_amounts)
        used_direct_reprice = used_direct_reprice or baseline_rate == ZERO
        cloned["scenario_rate_pct"] = scenario_rate_pct
        adjusted.append(cloned)
    return _roll_up_repriced_rows(adjusted) if used_direct_reprice else adjusted


def apply_baseline_ftp_rate_to_rows(
    rows: list[dict[str, object]],
    baseline_rate_pct: Decimal,
) -> list[dict[str, object]]:
    _validate_reprice_baselines(rows)
    adjusted: list[dict[str, object]] = []
    used_direct_reprice = False
    for row in rows:
        current_rate = Decimal(str(row["baseline_ftp_rate_pct"]))
        ftp_amounts = _reprice_ftp_amounts(
            row,
            current_rate_pct=current_rate,
            target_rate_pct=baseline_rate_pct,
        )
        cloned = _with_ftp_amounts(row, *ftp_amounts)
        used_direct_reprice = used_direct_reprice or current_rate == ZERO
        cloned["baseline_ftp_rate_pct"] = baseline_rate_pct
        adjusted.append(cloned)
    return _roll_up_repriced_rows(adjusted) if used_direct_reprice else adjusted


def _reprice_ftp_amounts(
    row: Mapping[str, object],
    *,
    current_rate_pct: Decimal,
    target_rate_pct: Decimal,
) -> tuple[Decimal, Decimal]:
    if current_rate_pct != ZERO:
        ratio = target_rate_pct / current_rate_pct
        return (
            Decimal(str(row["cny_ftp"])) * ratio,
            Decimal(str(row["foreign_ftp"])) * ratio,
        )

    cny_scale = Decimal(str(row["cny_scale"]))
    foreign_scale = Decimal(str(row["foreign_scale"]))
    if cny_scale == ZERO and foreign_scale == ZERO:
        return ZERO, ZERO

    days = _days_for_view(_parse_report_date(str(row["report_date"])), str(row["view"]))
    target_rate = target_rate_pct / Decimal("100")
    return (
        _calculate_ftp(cny_scale, target_rate, days),
        _calculate_ftp(foreign_scale, target_rate, days),
    )


def _with_ftp_amounts(
    row: Mapping[str, object],
    cny_ftp: Decimal,
    foreign_ftp: Decimal,
) -> dict[str, object]:
    adjusted = dict(row)
    cny_net = Decimal(str(row["cny_cash"])) - cny_ftp
    foreign_net = Decimal(str(row["foreign_cash"])) - foreign_ftp
    adjusted["cny_ftp"], adjusted["foreign_ftp"] = cny_ftp, foreign_ftp
    adjusted["cny_net"], adjusted["foreign_net"] = cny_net, foreign_net
    adjusted["business_net_income"] = cny_net + foreign_net
    return adjusted


def _validate_reprice_baselines(rows: list[dict[str, object]]) -> None:
    zero_markers = {Decimal(str(row["baseline_ftp_rate_pct"])) == ZERO for row in rows}
    if len(zero_markers) > 1:
        raise ValueError("Cannot reprice mixed zero/nonzero baseline rates")


def _roll_up_repriced_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_id = {str(row["category_id"]): row for row in rows}
    for row in sorted(rows, key=lambda item: int(item["level"]), reverse=True):
        child_ids = [str(child_id) for child_id in row.get("children", [])]
        if not child_ids or not all(child_id in by_id for child_id in child_ids):
            continue
        children = [by_id[child_id] for child_id in child_ids]
        by_id[str(row["category_id"])] = _with_ftp_amounts(
            row,
            sum((Decimal(str(child["cny_ftp"])) for child in children), ZERO),
            sum((Decimal(str(child["foreign_ftp"])) for child in children), ZERO),
        )

    root_rows = [
        by_id[str(row["category_id"])]
        for row in rows
        if int(row["level"]) == 0
        and not bool(row["is_total"])
        and str(row["side"]) in {"asset", "liability"}
    ]
    asset_rows = [row for row in root_rows if str(row["side"]) == "asset"]
    liability_rows = [row for row in root_rows if str(row["side"]) == "liability"]
    required_total_ids = ("asset_total", "liability_total", "grand_total")
    if not asset_rows or not liability_rows or not all(
        category_id in by_id for category_id in required_total_ids
    ):
        return [by_id[str(row["category_id"])] for row in rows]

    asset_total = by_id["asset_total"]
    report_date = _parse_report_date(str(asset_total["report_date"]))
    days_for_view = _days_for_view(report_date, str(asset_total["view"]))
    rebuilt_totals = (
        _build_total_row(
            str(asset_total["category_name"]),
            "asset",
            asset_rows,
            days_for_view,
            scale_exclusions=ASSET_SCALE_EXCLUSIONS,
            pnl_exclusions=ASSET_PNL_EXCLUSIONS,
        ),
        _build_total_row(
            str(by_id["liability_total"]["category_name"]),
            "liability",
            liability_rows,
            days_for_view,
        ),
    )
    for category_id, rebuilt in zip(required_total_ids[:2], rebuilt_totals, strict=True):
        total = dict(by_id[category_id])
        total.update({field: rebuilt[field] for field in FTP_RESULT_FIELDS})
        by_id[category_id] = total

    grand_total = dict(by_id["grand_total"])
    grand_total.update(
        {
            field: Decimal(str(by_id["asset_total"][field]))
            + Decimal(str(by_id["liability_total"][field]))
            for field in FTP_RESULT_FIELDS
        }
    )
    by_id["grand_total"] = grand_total
    return [by_id[str(row["category_id"])] for row in rows]


def _build_report_rows(
    facts_by_report_date: dict[date, list[CanonicalFactRow]],
    report_date: date,
    view: str,
) -> list[CanonicalFactRow]:
    if view == "monthly":
        return facts_by_report_date[report_date]
    if view in {"ytd", "year_to_report_month_end"}:
        return _build_ytd_report_rows(facts_by_report_date, report_date, view)
    if view != "qtd":
        raise ValueError(f"Unsupported view={view}")

    quarter_start_month = ((report_date.month - 1) // 3) * 3 + 1
    quarter_months = [
        item_date
        for item_date in sorted(facts_by_report_date)
        if item_date.year == report_date.year and quarter_start_month <= item_date.month <= report_date.month
    ]
    if not quarter_months:
        return facts_by_report_date[report_date]

    # 2026-08 B8 口径修正：qtd 与 ytd 同法——现金按季度内各月 monthly_pnl 累加，
    # 规模按各月 monthly 口径规模字段（一月回退 annual_avg_balance，见 _scale_field）
    # 乘当月天数加权后除以季度天数。
    combined: dict[tuple[str, str], dict[str, Decimal | str | int | date]] = {}
    for item_date in quarter_months:
        days = Decimal(_days_for_view(item_date, "monthly"))
        scale_field = _scale_field(item_date, "monthly")
        for row in facts_by_report_date[item_date]:
            key = (row.account_code, row.currency)
            current = combined.setdefault(
                key,
                {
                    "report_date": report_date,
                    "account_code": row.account_code,
                    "currency": row.currency,
                    "account_name": row.account_name,
                    "ending_balance": row.ending_balance,
                    "monthly_pnl": ZERO,
                    "daily_avg_balance": ZERO,
                    "annual_avg_balance": row.annual_avg_balance,
                    "days_in_period": _days_for_view(report_date, view),
                },
            )
            current["account_name"] = row.account_name
            current["ending_balance"] = row.ending_balance
            current["annual_avg_balance"] = row.annual_avg_balance
            current["monthly_pnl"] = Decimal(str(current["monthly_pnl"])) + row.monthly_pnl
            current["daily_avg_balance"] = Decimal(str(current["daily_avg_balance"])) + (
                getattr(row, scale_field) * days
            )

    result: list[CanonicalFactRow] = []
    period_days = Decimal(_days_for_view(report_date, view))
    for data in combined.values():
        result.append(
            CanonicalFactRow(
                report_date=report_date,
                account_code=str(data["account_code"]),
                currency=str(data["currency"]),
                account_name=str(data["account_name"]),
                beginning_balance=ZERO,
                ending_balance=Decimal(str(data["ending_balance"])),
                monthly_pnl=Decimal(str(data["monthly_pnl"])),
                daily_avg_balance=Decimal(str(data["daily_avg_balance"])) / period_days,
                annual_avg_balance=Decimal(str(data["annual_avg_balance"])),
                days_in_period=int(data["days_in_period"]),
            )
        )
    return result


def _build_ytd_report_rows(
    facts_by_report_date: dict[date, list[CanonicalFactRow]],
    report_date: date,
    view: str,
) -> list[CanonicalFactRow]:
    year_months = [
        item_date
        for item_date in sorted(facts_by_report_date)
        if item_date.year == report_date.year and item_date.month <= report_date.month
    ]
    if not year_months:
        return facts_by_report_date[report_date]

    combined: dict[tuple[str, str], dict[str, Decimal | str | int | date]] = {}
    for item_date in year_months:
        days = Decimal(_days_for_view(item_date, "monthly"))
        scale_field = _scale_field(item_date, "monthly")
        for row in facts_by_report_date[item_date]:
            key = (row.account_code, row.currency)
            current = combined.setdefault(
                key,
                {
                    "report_date": report_date,
                    "account_code": row.account_code,
                    "currency": row.currency,
                    "account_name": row.account_name,
                    "beginning_balance": row.beginning_balance,
                    "ending_balance": row.ending_balance,
                    "monthly_pnl": ZERO,
                    "daily_avg_balance": ZERO,
                    "annual_avg_balance": row.annual_avg_balance,
                    "days_in_period": _days_for_view(report_date, view),
                },
            )
            current["account_name"] = row.account_name
            current["ending_balance"] = row.ending_balance
            current["monthly_pnl"] = Decimal(str(current["monthly_pnl"])) + row.monthly_pnl
            current["daily_avg_balance"] = Decimal(str(current["daily_avg_balance"])) + (
                getattr(row, scale_field) * days
            )
            current["annual_avg_balance"] = row.annual_avg_balance

    result: list[CanonicalFactRow] = []
    period_days = Decimal(_days_for_view(report_date, view))
    for data in combined.values():
        result.append(
            CanonicalFactRow(
                report_date=report_date,
                account_code=str(data["account_code"]),
                currency=str(data["currency"]),
                account_name=str(data["account_name"]),
                beginning_balance=Decimal(str(data["beginning_balance"])),
                ending_balance=Decimal(str(data["ending_balance"])),
                monthly_pnl=Decimal(str(data["monthly_pnl"])),
                daily_avg_balance=Decimal(str(data["daily_avg_balance"])) / period_days,
                annual_avg_balance=Decimal(str(data["annual_avg_balance"])),
                days_in_period=int(data["days_in_period"]),
            )
        )
    return result


def _scale_field(report_date: date, view: str) -> str:
    if view == "monthly":
        return "annual_avg_balance" if report_date.month == 1 else "daily_avg_balance"
    if view in {"qtd", "ytd", "year_to_report_month_end"}:
        return "daily_avg_balance"
    return "annual_avg_balance"


def _days_for_view(report_date: date, view: str) -> int:
    month_end = date(report_date.year, report_date.month, monthrange(report_date.year, report_date.month)[1])
    if view == "monthly":
        return month_end.day
    if view == "qtd":
        quarter_start_month = ((report_date.month - 1) // 3) * 3 + 1
        quarter_start = date(report_date.year, quarter_start_month, 1)
        return (month_end - quarter_start).days + 1
    year_start = date(report_date.year, 1, 1)
    return (month_end - year_start).days + 1


def _calculate_sum(
    rows: list[CanonicalFactRow],
    patterns: list[str],
    field_name: str,
    currency: str,
    *,
    exact: bool,
) -> Decimal:
    total = ZERO
    for pattern in patterns:
        sign_value, target = _normalize_pattern(pattern)
        if not target:
            continue
        sign = Decimal(sign_value)
        subtotal = ZERO
        for row in rows:
            if row.currency != currency:
                continue
            matched = _matches_account(row.account_code, target, exact=exact)
            if matched:
                subtotal += Decimal(str(getattr(row, field_name)))
        total += sign * subtotal
    return total


def _normalize_pattern(pattern: str | None) -> tuple[int, str]:
    if pattern is None:
        return 0, ""
    normalized = str(pattern).strip()
    if not normalized:
        return 0, ""
    if normalized.startswith("-"):
        return -1, normalized[1:].strip()
    return 1, normalized


def _matches_account(account_code: str | None, pattern: str | None, *, exact: bool) -> bool:
    if account_code is None or pattern is None:
        return False
    code = str(account_code).strip()
    target = str(pattern).strip()
    if not code or not target:
        return False
    if exact:
        return code == target
    return code.startswith(target)


def _calculate_ftp(scale: Decimal, ftp_rate: Decimal, days: int) -> Decimal:
    return scale * ftp_rate * Decimal(days) / DAYS_IN_YEAR


def _calculate_weighted_yield(
    pnl_ending: Decimal,
    scale_cnx: Decimal,
    days_for_view: int,
) -> Decimal | None:
    if scale_cnx == ZERO or days_for_view <= 0:
        return None
    return pnl_ending / Decimal(days_for_view) * DAYS_IN_YEAR / scale_cnx * Decimal("100")


def _calculate_weighted_yield_from_row(
    row: Mapping[str, object],
    cash_key: str,
    scale_key: str,
    days_for_view: int,
) -> Decimal | None:
    cash = _decimal_or_none(row.get(cash_key))
    scale = _decimal_or_none(row.get(scale_key))
    if cash is None or scale is None:
        return None
    return _calculate_weighted_yield(cash, scale, days_for_view)


def _subtract_when_present(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None or right is None:
        return None
    return left - right


def _build_product_category_metric_value(value: Decimal | None) -> ProductCategoryMetricValue | None:
    if value is None:
        return None
    raw = value.quantize(PRODUCT_CATEGORY_RATE_RAW_QUANT, rounding=ROUND_HALF_UP)
    display = f"{raw.quantize(PRODUCT_CATEGORY_RATE_DISPLAY_QUANT, rounding=ROUND_HALF_UP)}%"
    return ProductCategoryMetricValue(raw=raw, display=display)


def _build_product_category_bp_metric_value(value: Decimal | None) -> ProductCategoryMetricValue | None:
    if value is None:
        return None
    raw = value.quantize(PRODUCT_CATEGORY_RATE_RAW_QUANT, rounding=ROUND_HALF_UP)
    display = f"{raw.quantize(PRODUCT_CATEGORY_BP_DISPLAY_QUANT, rounding=ROUND_HALF_UP)} bp"
    return ProductCategoryMetricValue(raw=raw, display=display, unit="bp")


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _parse_report_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _build_total_row(
    name: str,
    side: str,
    rows: list[dict[str, object]],
    days_for_view: int,
    *,
    scale_exclusions: set[str] | None = None,
    pnl_exclusions: set[str] | None = None,
) -> dict[str, object]:
    scale_exclusions = scale_exclusions or set()
    pnl_exclusions = pnl_exclusions or set()
    scale_rows = [row for row in rows if str(row["category_name"]) not in scale_exclusions]
    pnl_rows = [row for row in rows if str(row["category_name"]) not in pnl_exclusions]

    cnx_scale = sum((Decimal(str(row["cnx_scale"])) for row in scale_rows), ZERO)
    cny_scale = sum((Decimal(str(row["cny_scale"])) for row in scale_rows), ZERO)
    foreign_scale = sum((Decimal(str(row["foreign_scale"])) for row in scale_rows), ZERO)
    cnx_cash = sum((Decimal(str(row["cnx_cash"])) for row in pnl_rows), ZERO)
    cny_cash = sum((Decimal(str(row["cny_cash"])) for row in pnl_rows), ZERO)
    foreign_cash = sum((Decimal(str(row["foreign_cash"])) for row in pnl_rows), ZERO)
    cny_ftp = sum((Decimal(str(row["cny_ftp"])) for row in pnl_rows), ZERO)
    foreign_ftp = sum((Decimal(str(row["foreign_ftp"])) for row in pnl_rows), ZERO)
    cny_net = sum((Decimal(str(row["cny_net"])) for row in pnl_rows), ZERO)
    foreign_net = sum((Decimal(str(row["foreign_net"])) for row in pnl_rows), ZERO)
    business_net_income = sum((Decimal(str(row["business_net_income"])) for row in pnl_rows), ZERO)

    weighted_yield = _calculate_weighted_yield(cnx_cash, cnx_scale, days_for_view)
    baseline_rate = Decimal(str(rows[0]["baseline_ftp_rate_pct"])) if rows else ZERO
    return {
        "category_id": f"{side}_total",
        "category_name": name,
        "side": side,
        "level": 0,
        "view": rows[0]["view"] if rows else "monthly",
        "report_date": rows[0]["report_date"] if rows else None,
        "baseline_ftp_rate_pct": baseline_rate,
        "cnx_scale": cnx_scale,
        "cny_scale": cny_scale,
        "foreign_scale": foreign_scale,
        "cnx_cash": cnx_cash,
        "cny_cash": cny_cash,
        "foreign_cash": foreign_cash,
        "cny_ftp": cny_ftp,
        "foreign_ftp": foreign_ftp,
        "cny_net": cny_net,
        "foreign_net": foreign_net,
        "business_net_income": business_net_income,
        "weighted_yield": weighted_yield,
        "is_total": True,
        "children": [],
    }


def _is_approved_status(value: str) -> bool:
    return is_approved_status(value)
