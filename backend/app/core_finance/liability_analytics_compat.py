# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.app.core_finance.rate_units import pct_to_decimal

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
ONE_HUNDRED_MILLION = Decimal("100000000")

RISK_BUCKET_ORDER: tuple[str, ...] = (
    "已到期/逾期",
    "3个月以内",
    "3-6个月",
    "6-12个月",
    "1-2年",
    "2-3年",
    "3-5年",
    "5-10年",
    "10年以上",
)

V1_MONTHLY_BUCKET_ORDER: tuple[str, ...] = (
    "0-3M",
    "3-6M",
    "6-12M",
    "1-3Y",
    "3-5Y",
    "5-10Y",
    "10Y+",
    "Matured",
)


@dataclass
class CounterpartyAggregate:
    value: Decimal = ZERO
    weighted_num: Decimal = ZERO
    weighted_den: Decimal = ZERO
    by_type: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    first_report_date: date | None = None
    first_position_id: str = ""


@dataclass
class MonthlyAggregate:
    dates: set[date] = field(default_factory=set)
    total_sum: Decimal = ZERO
    interbank_sum: Decimal = ZERO
    issued_sum: Decimal = ZERO
    weighted_num: Decimal = ZERO
    weighted_den: Decimal = ZERO
    total_term: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    interbank_term: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    issued_term: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    interbank_by_type: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    issued_by_type: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    counterparty: dict[str, CounterpartyAggregate] = field(default_factory=dict)


def to_decimal(value: object | None) -> Decimal:
    if value in (None, ""):
        return ZERO
    return Decimal(str(value))


def to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def to_amount_yi(value: Decimal) -> Decimal:
    return value / ONE_HUNDRED_MILLION


def coerce_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def clean_text(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def zqtz_liability_amount(row: dict[str, Any]) -> Decimal:
    amortized = row.get("amortized_cost_native")
    market = row.get("market_value_native")
    face = row.get("face_value_native")
    if amortized not in (None, ""):
        return to_decimal(amortized)
    if market not in (None, ""):
        return to_decimal(market)
    return to_decimal(face)


def zqtz_asset_amount(row: dict[str, Any]) -> Decimal:
    market = row.get("market_value_native")
    face = row.get("face_value_native")
    if market not in (None, ""):
        return to_decimal(market)
    return to_decimal(face)


def normalize_bond_rate_decimal(value: object | None) -> Decimal | None:
    if value in (None, ""):
        return None
    rate = Decimal(str(value))
    if rate > Decimal("0.5") and rate <= Decimal("100"):
        return rate / ONE_HUNDRED
    return rate


def normalize_interbank_rate_decimal(value: object | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(pct_to_decimal(float(value))))


def weighted_rate(pairs: list[tuple[Decimal, Decimal | None]]) -> Decimal | None:
    numerator = ZERO
    denominator = ZERO
    for amount, rate in pairs:
        if amount <= ZERO or rate is None:
            continue
        numerator += amount * rate
        denominator += amount
    if denominator <= ZERO:
        return None
    return numerator / denominator


def maturity_bucket(report_date: date, maturity_value: object) -> str:
    maturity_date = coerce_date(maturity_value)
    if maturity_date is None:
        return "3个月以内"
    days = (maturity_date - report_date).days
    if days < 0:
        return "已到期/逾期"
    if days <= 90:
        return "3个月以内"
    if days <= 180:
        return "3-6个月"
    if days <= 365:
        return "6-12个月"
    if days <= 365 * 2:
        return "1-2年"
    if days <= 365 * 3:
        return "2-3年"
    if days <= 365 * 5:
        return "3-5年"
    if days <= 365 * 10:
        return "5-10年"
    return "10年以上"


def monthly_v1_bucket_name(report_date: date, maturity_value: object) -> str:
    maturity_date = coerce_date(maturity_value)
    if maturity_date is None:
        return "0-3M"
    days = (maturity_date - report_date).days
    if days < 0:
        return "Matured"
    if days <= 90:
        return "0-3M"
    if days <= 180:
        return "3-6M"
    if days <= 365:
        return "6-12M"
    if days <= 365 * 3:
        return "1-3Y"
    if days <= 365 * 5:
        return "3-5Y"
    if days <= 365 * 10:
        return "5-10Y"
    return "10Y+"


def is_interbank_cd(row: dict[str, Any]) -> bool:
    bond_type = str(row.get("bond_type") or "")
    instrument_name = str(row.get("instrument_name") or "")
    return "同业存单" in bond_type or "同业存单" in instrument_name


def is_interest_bearing_bond_asset(row: dict[str, Any]) -> bool:
    if bool(row.get("is_issuance_like")):
        return False
    asset_class = str(row.get("asset_class") or "").strip()
    if not asset_class or "交易" in asset_class:
        return False
    return any(
        token in asset_class
        for token in ("可供出售", "持有至到期", "应收投资款项", "应收投资")
    )


def classify_counterparty(name: str) -> str:
    normalized = str(name or "")
    lower = normalized.lower()
    if "银行" in normalized or "bank" in lower:
        return "Bank"
    if any(term in normalized for term in ("证券", "基金", "资管", "信托", "保险", "理财", "券商")):
        return "Non-Bank FI"
    return "Corporate/Other"


def classify_monthly_counterparty(name: str) -> str:
    normalized = str(name or "").strip()
    lower = normalized.lower()
    if not normalized or normalized == "其他":
        return "Other"
    if "银行" in normalized or "bank" in lower:
        return "Bank"
    return "NonBank"


def is_self_counterparty(name: str) -> bool:
    normalized = str(name or "").strip()
    return bool(normalized) and ("青岛银行" in normalized)


def sort_name_amount_items(items: dict[str, Decimal]) -> list[tuple[str, Decimal]]:
    return sorted(items.items(), key=lambda item: (-item[1], item[0]))


def build_name_amount_payload(items: dict[str, Decimal]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for name, amount in sort_name_amount_items(items):
        if amount <= ZERO:
            continue
        payload.append(
            {
                "name": name,
                "amount": to_float(amount),
                "amount_yi": to_float(to_amount_yi(amount)),
            }
        )
    return payload


def build_bucket_amount_payload(items: dict[str, Decimal]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for label in RISK_BUCKET_ORDER:
        amount = items.get(label, ZERO)
        if amount <= ZERO:
            continue
        payload.append(
            {
                "bucket": label,
                "amount": to_float(amount),
                "amount_yi": to_float(to_amount_yi(amount)),
            }
        )
    return payload


def monthly_breakdown_items(
    values: dict[str, Decimal],
    *,
    num_days: int,
    denominator_avg: Decimal,
    label_key: str,
) -> list[dict[str, Any]]:
    if num_days <= 0:
        return []
    divisor = Decimal(num_days)
    rows: list[dict[str, Any]] = []
    for key, total_amount in sorted(values.items(), key=lambda item: (-item[1], item[0])):
        if total_amount <= ZERO:
            continue
        avg_balance = total_amount / divisor
        pct = (avg_balance / denominator_avg * ONE_HUNDRED) if denominator_avg > ZERO else ZERO
        rows.append(
            {
                label_key: key,
                "avg_balance": to_float(avg_balance),
                "proportion": to_float(pct),
                "amount": to_float(avg_balance),
                "pct": to_float(pct),
            }
        )
    return rows


def monthly_v1_term_items(values: dict[str, Decimal], *, num_days: int) -> list[dict[str, Any]]:
    if num_days <= 0:
        return []
    divisor = Decimal(num_days)
    avg_values = {bucket: values.get(bucket, ZERO) / divisor for bucket in V1_MONTHLY_BUCKET_ORDER}
    total_avg = sum(avg_values.values(), ZERO)
    rows: list[dict[str, Any]] = []
    for bucket in V1_MONTHLY_BUCKET_ORDER:
        avg_balance = avg_values[bucket]
        pct = (avg_balance / total_avg * ONE_HUNDRED) if total_avg > ZERO else ZERO
        rows.append(
            {
                "bucket": bucket,
                "avg_balance": to_float(avg_balance),
                "amount": to_float(avg_balance),
                "pct": to_float(pct),
            }
        )
    return rows


def _descending_text_key(text: str) -> tuple[int, ...]:
    return tuple(-ord(ch) for ch in str(text or ""))


def compute_liability_risk_buckets(
    report_date: str,
    zqtz_rows: list[dict[str, Any]],
    tyw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    report_dt = date.fromisoformat(report_date)
    issued_structure: dict[str, Decimal] = defaultdict(lambda: ZERO)
    interbank_structure: dict[str, Decimal] = defaultdict(lambda: ZERO)
    issued_terms: dict[str, Decimal] = defaultdict(lambda: ZERO)
    interbank_terms: dict[str, Decimal] = defaultdict(lambda: ZERO)
    total_terms: dict[str, Decimal] = defaultdict(lambda: ZERO)

    for row in zqtz_rows:
        if not bool(row.get("is_issuance_like")):
            continue
        amount = zqtz_liability_amount(row)
        if amount <= ZERO:
            continue
        name = clean_text(row.get("bond_type"), "发行债券")
        issued_structure[name] += amount
        bucket_name = maturity_bucket(report_dt, row.get("maturity_date"))
        issued_terms[bucket_name] += amount
        total_terms[bucket_name] += amount

    for row in tyw_rows:
        if bool(row.get("is_asset_side")):
            continue
        amount = to_decimal(row.get("principal_native"))
        if amount <= ZERO:
            continue
        name = clean_text(row.get("product_type"), "同业其他")
        interbank_structure[name] += amount
        bucket_name = maturity_bucket(report_dt, row.get("maturity_date"))
        interbank_terms[bucket_name] += amount
        total_terms[bucket_name] += amount

    liabilities_structure: dict[str, Decimal] = {}
    total_interbank = sum(interbank_structure.values(), ZERO)
    total_issued = sum(issued_structure.values(), ZERO)
    if total_interbank > ZERO:
        liabilities_structure["同业负债"] = total_interbank
    if total_issued > ZERO:
        liabilities_structure["发行负债"] = total_issued

    return {
        "report_date": report_date,
        "liabilities_structure": build_name_amount_payload(liabilities_structure),
        "liabilities_term_buckets": build_bucket_amount_payload(total_terms),
        "interbank_liabilities_structure": build_name_amount_payload(interbank_structure),
        "interbank_liabilities_term_buckets": build_bucket_amount_payload(interbank_terms),
        "issued_liabilities_structure": build_name_amount_payload(issued_structure),
        "issued_liabilities_term_buckets": build_bucket_amount_payload(issued_terms),
    }


def compute_liability_yield_metrics(
    report_date: str,
    zqtz_rows: list[dict[str, Any]],
    tyw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    asset_pairs: list[tuple[Decimal, Decimal | None]] = []
    liability_pairs: list[tuple[Decimal, Decimal | None]] = []
    market_liability_pairs: list[tuple[Decimal, Decimal | None]] = []

    for row in zqtz_rows:
        if bool(row.get("is_issuance_like")):
            amount = zqtz_liability_amount(row)
            rate = normalize_bond_rate_decimal(row.get("coupon_rate"))
            liability_pairs.append((amount, rate))
            if is_interbank_cd(row):
                market_liability_pairs.append((amount, rate))
            continue
        if not is_interest_bearing_bond_asset(row):
            continue
        amount = zqtz_asset_amount(row)
        ytm = normalize_bond_rate_decimal(row.get("ytm_value"))
        coupon = normalize_bond_rate_decimal(row.get("coupon_rate"))
        rate = ytm if ytm not in (None, ZERO) else coupon
        asset_pairs.append((amount, rate))

    for row in tyw_rows:
        amount = to_decimal(row.get("principal_native"))
        rate = normalize_interbank_rate_decimal(row.get("funding_cost_rate"))
        if bool(row.get("is_asset_side")):
            asset_pairs.append((amount, rate))
            continue
        liability_pairs.append((amount, rate))
        market_liability_pairs.append((amount, rate))

    asset_yield = weighted_rate(asset_pairs)
    liability_cost = weighted_rate(liability_pairs)
    market_liability_cost = weighted_rate(market_liability_pairs) or liability_cost
    nim = (
        asset_yield - market_liability_cost
        if asset_yield is not None and market_liability_cost is not None
        else None
    )

    return {
        "report_date": report_date,
        "kpi": {
            "asset_yield": to_float(asset_yield),
            "liability_cost": to_float(liability_cost),
            "market_liability_cost": to_float(market_liability_cost),
            "nim": to_float(nim),
        },
    }


def compute_liability_counterparty(
    report_date: str,
    tyw_rows: list[dict[str, Any]],
    *,
    top_n: int,
) -> dict[str, Any]:
    grouped: dict[str, CounterpartyAggregate] = {}
    by_type_amount: dict[str, Decimal] = defaultdict(lambda: ZERO)

    for row in tyw_rows:
        if bool(row.get("is_asset_side")):
            continue
        counterparty_name = clean_text(row.get("counterparty_name"), "其他")
        if is_self_counterparty(counterparty_name):
            continue
        amount = to_decimal(row.get("principal_native"))
        if amount <= ZERO:
            continue
        rate = normalize_interbank_rate_decimal(row.get("funding_cost_rate"))
        cpty_type = classify_counterparty(counterparty_name)

        agg = grouped.setdefault(counterparty_name, CounterpartyAggregate())
        agg.value += amount
        if rate is not None:
            agg.weighted_num += amount * rate
            agg.weighted_den += amount
        agg.by_type[cpty_type] += amount
        by_type_amount[cpty_type] += amount

    ranked = sorted(grouped.items(), key=lambda item: (-item[1].value, item[0]))
    top_ranked = ranked[: max(top_n, 1)]
    total_value = sum((item.value for item in grouped.values()), ZERO)

    top_items: list[dict[str, Any]] = []
    for name, agg in top_ranked:
        row_type = max(agg.by_type.items(), key=lambda item: (item[1], item[0]))[0] if agg.by_type else "Corporate/Other"
        weighted_cost = (agg.weighted_num / agg.weighted_den) if agg.weighted_den > ZERO else None
        top_items.append(
            {
                "name": name,
                "value": to_float(agg.value),
                "type": row_type,
                "weighted_cost": to_float(weighted_cost),
            }
        )

    by_type = [
        {"name": type_name, "value": to_float(amount)}
        for type_name, amount in sorted(by_type_amount.items(), key=lambda item: (-item[1], item[0]))
        if amount > ZERO
    ]

    return {
        "report_date": report_date,
        "total_value": to_float(total_value) or 0.0,
        "top_10": top_items,
        "by_type": by_type,
    }


def compute_liabilities_monthly(year: int, zqtz_rows: list[dict[str, Any]], tyw_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not zqtz_rows and not tyw_rows:
        return {
            "year": year,
            "months": [],
            "ytd_avg_total_liabilities": 0.0,
            "ytd_avg_liability_cost": None,
        }

    monthly: dict[str, MonthlyAggregate] = {}

    for row in zqtz_rows:
        report_dt = coerce_date(row.get("report_date"))
        if report_dt is None or report_dt.year != year:
            continue
        month_key = report_dt.strftime("%Y-%m")
        month_agg = monthly.setdefault(month_key, MonthlyAggregate())
        month_agg.dates.add(report_dt)

        amount = zqtz_liability_amount(row)
        if amount <= ZERO:
            continue
        rate = normalize_bond_rate_decimal(row.get("coupon_rate"))
        month_agg.total_sum += amount
        month_agg.issued_sum += amount
        if rate is not None:
            month_agg.weighted_num += amount * rate
            month_agg.weighted_den += amount

        issued_type = clean_text(row.get("bond_type"), "发行债券")
        month_agg.issued_by_type[issued_type] += amount
        bucket_name = monthly_v1_bucket_name(report_dt, row.get("maturity_date"))
        month_agg.issued_term[bucket_name] += amount
        month_agg.total_term[bucket_name] += amount

    for row in tyw_rows:
        report_dt = coerce_date(row.get("report_date"))
        if report_dt is None or report_dt.year != year:
            continue
        month_key = report_dt.strftime("%Y-%m")
        month_agg = monthly.setdefault(month_key, MonthlyAggregate())
        month_agg.dates.add(report_dt)

        amount = to_decimal(row.get("principal_native"))
        if amount <= ZERO:
            continue
        rate = normalize_interbank_rate_decimal(row.get("funding_cost_rate"))
        month_agg.total_sum += amount
        month_agg.interbank_sum += amount
        if rate is not None:
            month_agg.weighted_num += amount * rate
            month_agg.weighted_den += amount

        product_type = clean_text(row.get("product_type"), "同业其他")
        month_agg.interbank_by_type[product_type] += amount
        bucket_name = monthly_v1_bucket_name(report_dt, row.get("maturity_date"))
        month_agg.interbank_term[bucket_name] += amount
        month_agg.total_term[bucket_name] += amount

        counterparty_name = clean_text(row.get("counterparty_name"), "其他")
        if is_self_counterparty(counterparty_name):
            continue
        counterparty_type = classify_monthly_counterparty(counterparty_name)
        counterparty = month_agg.counterparty.setdefault(counterparty_name, CounterpartyAggregate())
        counterparty.value += amount
        if rate is not None:
            counterparty.weighted_num += amount * rate
            counterparty.weighted_den += amount
        counterparty.by_type[counterparty_type] += amount
        position_id = str(row.get("position_id") or "")
        if (
            counterparty.first_report_date is None
            or report_dt < counterparty.first_report_date
            or (
                report_dt == counterparty.first_report_date
                and position_id > counterparty.first_position_id
            )
        ):
            counterparty.first_report_date = report_dt
            counterparty.first_position_id = position_id

    months: list[dict[str, Any]] = []
    prev_avg_total: Decimal | None = None
    year_total_amount = ZERO
    year_total_days = 0

    for month_key in sorted(monthly.keys()):
        agg = monthly[month_key]
        num_days = len(agg.dates)
        if num_days <= 0:
            continue
        divisor = Decimal(num_days)

        avg_total = agg.total_sum / divisor
        avg_interbank = agg.interbank_sum / divisor
        avg_issued = agg.issued_sum / divisor
        avg_liability_cost = (agg.weighted_num / agg.weighted_den) if agg.weighted_den > ZERO else None

        mom_change = (avg_total - prev_avg_total) if prev_avg_total is not None else None
        mom_change_pct = (
            ((mom_change / prev_avg_total) * ONE_HUNDRED)
            if mom_change is not None and prev_avg_total is not None and prev_avg_total > ZERO
            else None
        )
        prev_avg_total = avg_total

        counterparty_total_avg = sum((cpty.value for cpty in agg.counterparty.values()), ZERO) / divisor
        details: list[dict[str, Any]] = []
        sorted_counterparties = sorted(
            agg.counterparty.items(),
            key=lambda item: (
                -item[1].value,
                item[1].first_report_date or date.max,
                _descending_text_key(item[1].first_position_id),
            ),
        )
        for cpty_name, cpty in sorted_counterparties:
            avg_value = cpty.value / divisor
            weighted_cost = (cpty.weighted_num / cpty.weighted_den) if cpty.weighted_den > ZERO else None
            cpty_type = max(cpty.by_type.items(), key=lambda item: (item[1], item[0]))[0] if cpty.by_type else "Other"
            details.append(
                {
                    "name": cpty_name,
                    "avg_value": to_float(avg_value),
                    "proportion": to_float(
                        (avg_value / counterparty_total_avg * ONE_HUNDRED) if counterparty_total_avg > ZERO else ZERO
                    ),
                    "amount": to_float(avg_value),
                    "pct": to_float((avg_value / avg_total * ONE_HUNDRED) if avg_total > ZERO else ZERO),
                    "weighted_cost": to_float(weighted_cost),
                    "type": cpty_type,
                }
            )

        by_institution_sum: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for row in details:
            by_institution_sum[str(row["type"])] += to_decimal(row["avg_value"])
        by_institution_total = sum(by_institution_sum.values(), ZERO)
        by_institution_type = [
            {
                "type": inst_type,
                "avg_value": to_float(value),
                "amount": to_float(value),
                "pct": to_float((value / by_institution_total * ONE_HUNDRED) if by_institution_total > ZERO else ZERO),
            }
            for inst_type, value in sorted(by_institution_sum.items(), key=lambda item: (-item[1], item[0]))
            if value > ZERO
        ]

        month_int = int(month_key.split("-")[1])
        interbank_pct = (avg_interbank / avg_total * ONE_HUNDRED) if avg_total > ZERO else ZERO
        issued_pct = (avg_issued / avg_total * ONE_HUNDRED) if avg_total > ZERO else ZERO
        structure_overview = [
            {
                "category": "同业负债",
                "avg_balance": to_float(avg_interbank),
                "proportion": to_float(interbank_pct),
                "amount": to_float(avg_interbank),
                "pct": to_float(interbank_pct),
            },
            {
                "category": "发行负债",
                "avg_balance": to_float(avg_issued),
                "proportion": to_float(issued_pct),
                "amount": to_float(avg_issued),
                "pct": to_float(issued_pct),
            },
        ]

        months.append(
            {
                "month": month_key,
                "month_label": f"{year}年{month_int}月",
                "avg_total_liabilities": to_float(avg_total),
                "avg_interbank_liabilities": to_float(avg_interbank),
                "avg_issued_liabilities": to_float(avg_issued),
                "avg_liability_cost": to_float(avg_liability_cost),
                "mom_change": to_float(mom_change),
                "mom_change_pct": to_float(mom_change_pct),
                "counterparty_top10": details[:10],
                "by_institution_type": by_institution_type,
                "structure_overview": structure_overview,
                "term_buckets": monthly_v1_term_items(agg.total_term, num_days=num_days),
                "interbank_by_type": monthly_breakdown_items(
                    agg.interbank_by_type,
                    num_days=num_days,
                    denominator_avg=avg_interbank,
                    label_key="category",
                ),
                "interbank_term_buckets": monthly_v1_term_items(agg.interbank_term, num_days=num_days),
                "issued_by_type": monthly_breakdown_items(
                    agg.issued_by_type,
                    num_days=num_days,
                    denominator_avg=avg_issued,
                    label_key="category",
                ),
                "issued_term_buckets": monthly_v1_term_items(agg.issued_term, num_days=num_days),
                "counterparty_details": details,
                "num_days": num_days,
            }
        )

        year_total_amount += agg.total_sum
        year_total_days += num_days

    ytd_avg_total = (year_total_amount / Decimal(year_total_days)) if year_total_days > 0 else ZERO

    return {
        "year": year,
        "months": months,
        "ytd_avg_total_liabilities": to_float(ytd_avg_total),
        "ytd_avg_liability_cost": None,
    }
