from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from backend.app.core_finance.field_normalization import is_approved_status


ZERO = Decimal("0")
DAYS_IN_YEAR = Decimal("365")
ASSET_SCALE_EXCLUSIONS = {
    "\u751f\u606f\u8d44\u4ea7",
    "\u884d\u751f\u54c1",
    "\u4e2d\u95f4\u4e1a\u52a1\u6536\u5165",
}
ASSET_PNL_EXCLUSIONS = {"\u751f\u606f\u8d44\u4ea7"}


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


def derive_monthly_pnl(period_debit: Decimal, period_credit: Decimal) -> Decimal:
    return period_credit - period_debit


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
            cash_field = "monthly_pnl" if view == "monthly" else "ending_balance"
            sign = Decimal("1") if view == "monthly" else Decimal("-1")
            cnx_cash = sign * _calculate_sum(report_rows, category["pnl_accounts"], cash_field, "CNX", exact=False)
            cny_cash = sign * _calculate_sum(report_rows, category["pnl_accounts"], cash_field, "CNY", exact=False)
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
        "cnx_cash": ZERO,
        "cny_cash": ZERO,
        "foreign_cash": ZERO,
        "cny_ftp": ZERO,
        "foreign_ftp": ZERO,
        "cny_net": ZERO,
        "foreign_net": ZERO,
        "business_net_income": Decimal(str(asset_total["business_net_income"])) + Decimal(str(liability_total["business_net_income"])),
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
    adjusted: list[dict[str, object]] = []
    for row in rows:
        baseline_rate = Decimal(str(row["baseline_ftp_rate_pct"]))
        ratio = ZERO if baseline_rate == ZERO else scenario_rate_pct / baseline_rate

        cny_ftp = Decimal(str(row["cny_ftp"]))
        foreign_ftp = Decimal(str(row["foreign_ftp"]))
        cny_cash = Decimal(str(row["cny_cash"]))
        foreign_cash = Decimal(str(row["foreign_cash"]))

        cny_ftp_new = cny_ftp * ratio
        foreign_ftp_new = foreign_ftp * ratio
        cny_net = cny_cash - cny_ftp_new
        foreign_net = foreign_cash - foreign_ftp_new
        business_net_income = cny_net + foreign_net

        cloned = dict(row)
        cloned["scenario_rate_pct"] = scenario_rate_pct
        cloned["cny_ftp"] = cny_ftp_new
        cloned["foreign_ftp"] = foreign_ftp_new
        cloned["cny_net"] = cny_net
        cloned["foreign_net"] = foreign_net
        cloned["business_net_income"] = business_net_income
        adjusted.append(cloned)
    return adjusted


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

    combined: dict[tuple[str, str], dict[str, Decimal | str | int | date]] = {}
    for item_date in quarter_months:
        days = Decimal(monthrange(item_date.year, item_date.month)[1])
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
                    "daily_avg_balance": ZERO,
                    "annual_avg_balance": row.annual_avg_balance,
                    "weight": ZERO,
                    "days_in_period": _days_for_view(report_date, view),
                },
            )
            current["account_name"] = row.account_name
            current["ending_balance"] = row.ending_balance
            current["annual_avg_balance"] = row.annual_avg_balance
            current["daily_avg_balance"] = Decimal(str(current["daily_avg_balance"])) + (row.daily_avg_balance * days)
            current["weight"] = Decimal(str(current["weight"])) + days

    result: list[CanonicalFactRow] = []
    for data in combined.values():
        weight = Decimal(str(data["weight"])) or Decimal("1")
        result.append(
            CanonicalFactRow(
                report_date=report_date,
                account_code=str(data["account_code"]),
                currency=str(data["currency"]),
                account_name=str(data["account_name"]),
                beginning_balance=ZERO,
                ending_balance=Decimal(str(data["ending_balance"])),
                monthly_pnl=ZERO,
                daily_avg_balance=Decimal(str(data["daily_avg_balance"])) / weight,
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
        days = Decimal(monthrange(item_date.year, item_date.month)[1])
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
                    "ending_balance": ZERO,
                    "monthly_pnl": ZERO,
                    "daily_avg_balance": ZERO,
                    "annual_avg_balance": row.annual_avg_balance,
                    "weight": ZERO,
                    "days_in_period": _days_for_view(report_date, view),
                },
            )
            current["account_name"] = row.account_name
            current["ending_balance"] = Decimal(str(current["ending_balance"])) + row.ending_balance
            current["monthly_pnl"] = Decimal(str(current["monthly_pnl"])) + row.monthly_pnl
            current["daily_avg_balance"] = Decimal(str(current["daily_avg_balance"])) + (row.daily_avg_balance * days)
            current["annual_avg_balance"] = row.annual_avg_balance
            current["weight"] = Decimal(str(current["weight"])) + days

    result: list[CanonicalFactRow] = []
    for data in combined.values():
        weight = Decimal(str(data["weight"])) or Decimal("1")
        result.append(
            CanonicalFactRow(
                report_date=report_date,
                account_code=str(data["account_code"]),
                currency=str(data["currency"]),
                account_name=str(data["account_name"]),
                beginning_balance=Decimal(str(data["beginning_balance"])),
                ending_balance=Decimal(str(data["ending_balance"])),
                monthly_pnl=Decimal(str(data["monthly_pnl"])),
                daily_avg_balance=Decimal(str(data["daily_avg_balance"])) / weight,
                annual_avg_balance=Decimal(str(data["annual_avg_balance"])),
                days_in_period=int(data["days_in_period"]),
            )
        )
    return result


def _scale_field(report_date: date, view: str) -> str:
    if view == "monthly":
        return "annual_avg_balance" if report_date.month == 1 else "daily_avg_balance"
    if view == "qtd":
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
