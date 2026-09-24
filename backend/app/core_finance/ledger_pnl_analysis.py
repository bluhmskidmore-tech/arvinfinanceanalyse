from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.config.classification_rules import (
    LEDGER_PNL_ACCOUNT_PREFIXES,
)

ZERO = Decimal("0")
CORE_PNL_PREFIXES = LEDGER_PNL_ACCOUNT_PREFIXES
ALL_PNL_PREFIXES = ("5",)
SUPPORTED_CURRENCY_BASES = ("CNX", "CNY")
TOP_CONTRIBUTOR_LIMIT = 5

_METRIC_NAMES = {
    "assets": "总资产",
    "liabilities": "总负债",
    "net_assets": "净资产",
    "core_pnl": "核心损益",
    "all_pnl": "全量损益",
    "other_5_pnl": "其他 5* 科目损益",
}


def build_ledger_pnl_analysis(
    *,
    report_date: date,
    source_version: str,
    currency_basis: str,
    current_facts: Sequence[Any],
    previous_report_date: date | None,
    previous_source_version: str | None,
    previous_facts: Sequence[Any],
) -> dict[str, Any]:
    if currency_basis not in SUPPORTED_CURRENCY_BASES:
        raise ValueError(f"Unsupported ledger currency basis: {currency_basis!r}")

    current_by_basis = {
        basis: _calculate_basis_metrics(current_facts, basis)
        for basis in SUPPORTED_CURRENCY_BASES
    }
    selected = current_by_basis[currency_basis]
    analysis_ready = bool(selected["has_pnl_data"])

    return {
        "report_date": report_date.isoformat(),
        "source_version": source_version,
        "currency_basis": currency_basis,
        "analysis_status": "ready" if analysis_ready else "no_data",
        "metric_status": "candidate",
        "basis_availability": {
            basis: "ready" if metrics["has_pnl_data"] else "no_data"
            for basis, metrics in current_by_basis.items()
        },
        "conclusion": {
            "direction": _signed_label(
                selected["all_pnl"],
                positive="positive",
                negative="negative",
                zero="flat",
                available=analysis_ready,
            ),
            "other_effect": _signed_label(
                selected["other_5_pnl"],
                positive="support",
                negative="drag",
                zero="neutral",
                available=analysis_ready,
            ),
            "core_pnl": selected["core_pnl"] if analysis_ready else None,
            "other_5_pnl": selected["other_5_pnl"] if analysis_ready else None,
            "all_pnl": selected["all_pnl"] if analysis_ready else None,
        },
        "pnl_bridge": _build_pnl_bridge(selected),
        "basis_comparison": _build_basis_comparison(current_by_basis),
        "contributors": _build_contributors(selected),
        "period_comparison": _build_period_comparison(
            currency_basis=currency_basis,
            current=selected,
            previous_report_date=previous_report_date,
            previous_source_version=previous_source_version,
            previous_facts=previous_facts,
        ),
        "calculation_basis": {
            "core_pnl_prefixes": list(CORE_PNL_PREFIXES),
            "all_pnl_prefixes": list(ALL_PNL_PREFIXES),
            "other_5_pnl_formula": "all_pnl - core_pnl",
            "other_5_pnl_boundary": (
                "arithmetic residual within 5* accounts; not a formal attribution category"
            ),
            "basis_difference_formula": "CNX - CNY",
            "basis_boundary": (
                "CNX and CNY are overlapping accounting bases and must not be added; "
                "CNX - CNY is not FX PnL."
            ),
            "basis_availability_boundary": (
                "basis_availability reports PnL analyzability only; balance metric "
                "availability and evidence are reported per comparison row"
            ),
            "previous_period_rule": (
                "latest available report_date strictly earlier than current report_date"
            ),
            "metric_boundary": (
                "candidate analytical evidence only; not a formal metric or formal PnL truth"
            ),
        },
    }


def build_ledger_pnl_account_detail(
    *,
    report_date: date,
    source_version: str,
    account_code: str,
    currency_basis: str,
    current_facts: Sequence[Any],
    previous_report_date: date | None,
    previous_source_version: str | None,
    previous_facts: Sequence[Any],
) -> dict[str, Any]:
    if currency_basis not in SUPPORTED_CURRENCY_BASES:
        raise ValueError(f"Unsupported ledger currency basis: {currency_basis!r}")
    if (previous_report_date is None) != (previous_source_version is None):
        raise ValueError("Previous report date and source version must be provided together")

    normalized_account_code = account_code.strip()
    current_rows = _exact_account_rows(current_facts, normalized_account_code)
    previous_rows = (
        _exact_account_rows(previous_facts, normalized_account_code)
        if previous_report_date is not None
        else []
    )
    current_snapshot = _build_account_basis_snapshot(
        report_date=report_date,
        source_version=source_version,
        rows=current_rows,
    )
    previous_snapshot = (
        _build_account_basis_snapshot(
            report_date=previous_report_date,
            source_version=previous_source_version,
            rows=previous_rows,
        )
        if previous_report_date is not None and previous_source_version is not None
        else None
    )

    current_selected_rows = _rows_for_basis(current_rows, currency_basis)
    previous_selected_rows = _rows_for_basis(previous_rows, currency_basis)
    current_amount = _account_monthly_pnl(current_selected_rows)
    previous_amount = _account_monthly_pnl(previous_selected_rows)
    if not current_selected_rows:
        comparison_status = "current_account_no_data"
    elif previous_report_date is None:
        comparison_status = "no_previous_period"
    elif not previous_selected_rows:
        comparison_status = "previous_account_no_data"
    else:
        comparison_status = "available"

    evidence_rows = _build_account_evidence_rows(
        period="current",
        source_version=source_version,
        rows=current_rows,
    )
    if previous_report_date is not None and previous_source_version is not None:
        evidence_rows.extend(
            _build_account_evidence_rows(
                period="previous",
                source_version=previous_source_version,
                rows=previous_rows,
            )
        )

    return {
        "report_date": report_date.isoformat(),
        "source_version": source_version,
        "currency_basis": currency_basis,
        "analysis_status": "ready" if current_selected_rows else "no_data",
        "metric_status": "candidate",
        "account": {
            "account_code": normalized_account_code,
            "account_name": _first_account_name(
                current_selected_rows,
                current_rows,
                previous_selected_rows,
                previous_rows,
            ),
        },
        "period_comparison": {
            "status": comparison_status,
            "previous_report_date": (
                previous_report_date.isoformat()
                if previous_report_date is not None
                else None
            ),
            "previous_source_version": previous_source_version,
            "current_monthly_pnl": current_amount,
            "previous_monthly_pnl": previous_amount,
            "change": (
                current_amount - previous_amount
                if comparison_status == "available"
                and current_amount is not None
                and previous_amount is not None
                else None
            ),
            "current_evidence_rows": len(current_selected_rows),
            "previous_evidence_rows": len(previous_selected_rows),
        },
        "basis_comparison": {
            "current": current_snapshot,
            "previous": previous_snapshot,
        },
        "canonical_evidence_rows": evidence_rows,
        "calculation_basis": {
            "account_match": "exact",
            "amount_field": "monthly_pnl",
            "change_formula": "current_monthly_pnl - previous_monthly_pnl",
            "basis_difference_formula": "CNX - CNY",
            "basis_boundary": (
                "CNX and CNY are overlapping accounting bases; CNX - CNY is not FX PnL."
            ),
            "previous_period_rule": (
                "latest available report_date strictly earlier than current report_date"
            ),
            "evidence_boundary": (
                "canonical facts normalized from paired workbooks; not raw workbook rows or vouchers"
            ),
            "metric_boundary": (
                "candidate analytical evidence only; not a formal metric or formal PnL truth"
            ),
        },
    }


def _calculate_basis_metrics(
    facts: Sequence[Any],
    currency_basis: str,
) -> dict[str, Any]:
    selected = [row for row in facts if str(getattr(row, "currency", "")) == currency_basis]
    asset_rows = [row for row in selected if _account_code(row).startswith(("1",))]
    liability_rows = [row for row in selected if _account_code(row).startswith(("2",))]
    pnl_rows = [row for row in selected if _account_code(row).startswith(ALL_PNL_PREFIXES)]
    assets = _sum_field(asset_rows, ("1",), "ending_balance")
    liabilities = abs(_sum_field(liability_rows, ("2",), "ending_balance"))
    core_pnl = _sum_field(pnl_rows, CORE_PNL_PREFIXES, "monthly_pnl")
    all_pnl = _sum_field(pnl_rows, ALL_PNL_PREFIXES, "monthly_pnl")
    has_assets = bool(asset_rows)
    has_liabilities = bool(liability_rows)
    has_pnl_data = bool(pnl_rows)
    metric_availability = {
        "assets": has_assets,
        "liabilities": has_liabilities,
        "net_assets": has_assets and has_liabilities,
        "core_pnl": has_pnl_data,
        "all_pnl": has_pnl_data,
        "other_5_pnl": has_pnl_data,
    }
    metric_evidence_rows = {
        "assets": len(asset_rows),
        "liabilities": len(liability_rows),
        "net_assets": len(asset_rows) + len(liability_rows),
        "core_pnl": len(pnl_rows),
        "all_pnl": len(pnl_rows),
        "other_5_pnl": len(pnl_rows),
    }
    return {
        "has_pnl_data": has_pnl_data,
        "evidence_rows": len(pnl_rows),
        "metric_availability": metric_availability,
        "metric_evidence_rows": metric_evidence_rows,
        "assets": assets,
        "liabilities": liabilities,
        "net_assets": assets - liabilities,
        "core_pnl": core_pnl,
        "all_pnl": all_pnl,
        "other_5_pnl": all_pnl - core_pnl,
        "pnl_rows": pnl_rows,
    }


def _sum_field(rows: Sequence[Any], prefixes: tuple[str, ...], field: str) -> Decimal:
    return sum(
        (
            _decimal(getattr(row, field, None))
            for row in rows
            if _account_code(row).startswith(prefixes)
        ),
        ZERO,
    )


def _build_pnl_bridge(selected: dict[str, Any]) -> dict[str, Any]:
    if not selected["has_pnl_data"]:
        return {
            "components": [
                {
                    "metric_key": "core_pnl",
                    "metric_name": _METRIC_NAMES["core_pnl"],
                    "amount": None,
                },
                {
                    "metric_key": "other_5_pnl",
                    "metric_name": _METRIC_NAMES["other_5_pnl"],
                    "amount": None,
                },
            ],
            "total": None,
            "residual": None,
        }
    total = selected["all_pnl"]
    core = selected["core_pnl"]
    other = selected["other_5_pnl"]
    return {
        "components": [
            {
                "metric_key": "core_pnl",
                "metric_name": _METRIC_NAMES["core_pnl"],
                "amount": core,
            },
            {
                "metric_key": "other_5_pnl",
                "metric_name": _METRIC_NAMES["other_5_pnl"],
                "amount": other,
            },
        ],
        "total": total,
        "residual": total - core - other,
    }


def _build_basis_comparison(current_by_basis: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for metric_key in (
        "assets",
        "liabilities",
        "net_assets",
        "core_pnl",
        "all_pnl",
        "other_5_pnl",
    ):
        cnx_metrics = current_by_basis["CNX"]
        cny_metrics = current_by_basis["CNY"]
        cnx_available = bool(cnx_metrics["metric_availability"][metric_key])
        cny_available = bool(cny_metrics["metric_availability"][metric_key])
        cnx = cnx_metrics[metric_key] if cnx_available else None
        cny = cny_metrics[metric_key] if cny_available else None
        rows.append(
            {
                "metric_key": metric_key,
                "metric_name": _METRIC_NAMES[metric_key],
                "cnx": cnx,
                "cny": cny,
                "cnx_minus_cny": cnx - cny if cnx is not None and cny is not None else None,
                "availability": {
                    "CNX": "ready" if cnx_available else "no_data",
                    "CNY": "ready" if cny_available else "no_data",
                },
                "evidence_rows": {
                    "CNX": int(cnx_metrics["metric_evidence_rows"][metric_key]),
                    "CNY": int(cny_metrics["metric_evidence_rows"][metric_key]),
                },
            }
        )
    return rows


def _build_contributors(selected: dict[str, Any]) -> dict[str, Any]:
    if not selected["has_pnl_data"]:
        return {
            "positive_total": None,
            "negative_total": None,
            "net_total": None,
            "top_positive": [],
            "top_negative": [],
        }
    accounts: dict[str, dict[str, Any]] = {}
    for row in selected["pnl_rows"]:
        code = _account_code(row)
        account = accounts.setdefault(
            code,
            {
                "account_code": code,
                "account_name": "",
                "amount": ZERO,
                "count": 0,
            },
        )
        name = str(getattr(row, "account_name", "") or "").strip()
        if name and not account["account_name"]:
            account["account_name"] = name
        account["amount"] += _decimal(getattr(row, "monthly_pnl", None))
        account["count"] += 1

    positive = sorted(
        (row for row in accounts.values() if row["amount"] > ZERO),
        key=lambda row: (-row["amount"], row["account_code"]),
    )
    negative = sorted(
        (row for row in accounts.values() if row["amount"] < ZERO),
        key=lambda row: (row["amount"], row["account_code"]),
    )
    return {
        "positive_total": sum((row["amount"] for row in positive), ZERO),
        "negative_total": sum((row["amount"] for row in negative), ZERO),
        "net_total": selected["all_pnl"],
        "top_positive": _rank_rows(positive),
        "top_negative": _rank_rows(negative),
    }


def _rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "account_code": row["account_code"],
            "account_name": row["account_name"],
            "amount": row["amount"],
            "count": row["count"],
        }
        for rank, row in enumerate(rows[:TOP_CONTRIBUTOR_LIMIT], start=1)
    ]


def _build_period_comparison(
    *,
    currency_basis: str,
    current: dict[str, Any],
    previous_report_date: date | None,
    previous_source_version: str | None,
    previous_facts: Sequence[Any],
) -> dict[str, Any]:
    previous = _calculate_basis_metrics(previous_facts, currency_basis)
    if not current["has_pnl_data"]:
        status = "current_basis_no_data"
    elif previous_report_date is None:
        status = "no_previous_period"
    elif not previous["has_pnl_data"]:
        status = "previous_basis_no_data"
    else:
        status = "available"

    rows = []
    if status == "available":
        for metric_key in ("core_pnl", "other_5_pnl", "all_pnl"):
            current_value = current[metric_key]
            previous_value = previous[metric_key]
            rows.append(
                {
                    "metric_key": metric_key,
                    "metric_name": _METRIC_NAMES[metric_key],
                    "current": current_value,
                    "previous": previous_value,
                    "change": current_value - previous_value,
                }
            )
    return {
        "status": status,
        "previous_report_date": (
            previous_report_date.isoformat() if previous_report_date is not None else None
        ),
        "previous_source_version": previous_source_version,
        "rows": rows,
    }


def _signed_label(
    amount: Decimal,
    *,
    positive: str,
    negative: str,
    zero: str,
    available: bool,
) -> str:
    if not available:
        return "unavailable"
    if amount > ZERO:
        return positive
    if amount < ZERO:
        return negative
    return zero


def _account_code(row: Any) -> str:
    return str(getattr(row, "account_code", "") or "").strip()


def _decimal(value: Any) -> Decimal:
    return ZERO if value in (None, "") else Decimal(str(value))


def _exact_account_rows(
    facts: Sequence[Any],
    account_code: str,
) -> list[Any]:
    return [
        row
        for row in facts
        if _account_code(row) == account_code
        and str(getattr(row, "currency", "")) in SUPPORTED_CURRENCY_BASES
    ]


def _rows_for_basis(rows: Sequence[Any], currency_basis: str) -> list[Any]:
    return [
        row
        for row in rows
        if str(getattr(row, "currency", "")) == currency_basis
    ]


def _account_monthly_pnl(rows: Sequence[Any]) -> Decimal | None:
    if not rows:
        return None
    return sum((_decimal(getattr(row, "monthly_pnl", None)) for row in rows), ZERO)


def _build_account_basis_snapshot(
    *,
    report_date: date,
    source_version: str,
    rows: Sequence[Any],
) -> dict[str, Any]:
    by_basis = {
        basis: _rows_for_basis(rows, basis)
        for basis in SUPPORTED_CURRENCY_BASES
    }
    amounts = {
        basis: _account_monthly_pnl(basis_rows)
        for basis, basis_rows in by_basis.items()
    }
    return {
        "report_date": report_date.isoformat(),
        "source_version": source_version,
        "cnx": amounts["CNX"],
        "cny": amounts["CNY"],
        "cnx_minus_cny": (
            amounts["CNX"] - amounts["CNY"]
            if amounts["CNX"] is not None and amounts["CNY"] is not None
            else None
        ),
        "availability": {
            basis: "ready" if by_basis[basis] else "no_data"
            for basis in SUPPORTED_CURRENCY_BASES
        },
        "evidence_rows": {
            basis: len(by_basis[basis])
            for basis in SUPPORTED_CURRENCY_BASES
        },
    }


def _build_account_evidence_rows(
    *,
    period: str,
    source_version: str,
    rows: Sequence[Any],
) -> list[dict[str, Any]]:
    ordered_rows = sorted(
        rows,
        key=lambda row: (
            SUPPORTED_CURRENCY_BASES.index(str(getattr(row, "currency", ""))),
            str(getattr(row, "account_name", "") or ""),
        ),
    )
    return [
        {
            "period": period,
            "report_date": row.report_date.isoformat(),
            "source_version": source_version,
            "account_code": _account_code(row),
            "account_name": str(getattr(row, "account_name", "") or "").strip(),
            "currency": str(getattr(row, "currency", "")),
            "beginning_balance": _decimal(getattr(row, "beginning_balance", None)),
            "ending_balance": _decimal(getattr(row, "ending_balance", None)),
            "monthly_pnl": _decimal(getattr(row, "monthly_pnl", None)),
            "days_in_period": int(getattr(row, "days_in_period", 0)),
        }
        for row in ordered_rows
    ]


def _first_account_name(*row_groups: Sequence[Any]) -> str | None:
    for rows in row_groups:
        for row in rows:
            name = str(getattr(row, "account_name", "") or "").strip()
            if name:
                return name
    return None
