"""V1 PnL source and detail admission against the selected formal snapshot."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from backend.app.core_finance.pnl import (
    PNL_FORMAL_FACT_RULE_VERSION,
    JournalType,
    build_formal_pnl_fi_fact_rows,
    build_nonstd_pnl_bridge_rows,
    normalize_fi_pnl_records,
    normalize_nonstd_journal_entries,
)
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.pnl import PnlV1DetailRow


def _require_v1_source_matches_formal_snapshot(
    repo: PnlRepository, refresh_input, fx_lineage: dict[str, tuple[Decimal, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Fail closed when current source rows no longer match the selected formal facts.

    This proves canonical row equivalence at the fact tables' decimal(24, 8)
    precision. Legacy opaque source versions do not prove original byte identity.
    Reuse the exact formal normalizers/projectors; never invent a second formula.
    """
    message = "V1 PnL source does not match the selected formal snapshot; detail is unavailable."
    if any(not version.strip() for _, version in fx_lineage.values()):
        raise RuntimeError(message + " FX source lineage is missing.")
    try:
        if any(
            not str(row.get("source_version") or "").strip()
            for row in (
                *refresh_input.fi_rows,
                *(row for rows in refresh_input.nonstd_rows_by_type.values() for row in rows),
            )
        ):
            raise RuntimeError(message + " Source lineage is missing.")
        formal_fi = build_formal_pnl_fi_fact_rows(normalize_fi_pnl_records(
            refresh_input.fi_rows, fx_rates_by_currency=fx_lineage,
        ))
        entries = []
        for journal_type, source_rows in sorted(refresh_input.nonstd_rows_by_type.items()):
            entries.extend(normalize_nonstd_journal_entries(
                source_rows, journal_type=cast(JournalType, journal_type),
                fx_rates_by_currency=fx_lineage,
            ))
        bridge = build_nonstd_pnl_bridge_rows(
            entries, target_date=date.fromisoformat(refresh_input.report_date),
            is_month_end=refresh_input.is_month_end,
        )
        current_fi = [asdict(row) for row in formal_fi]
        current_nonstd = [asdict(row) for row in bridge]
        stored_fi = repo.fetch_formal_fi_rows(refresh_input.report_date)
        stored_nonstd = repo.fetch_nonstd_bridge_rows(refresh_input.report_date)
        if not stored_fi and not stored_nonstd:
            raise RuntimeError(message + " Formal rows are missing.")
        common = ("report_date", "portfolio_name", "cost_center")
        fi_fields = (*common, "instrument_code", "invest_type_std", "accounting_basis", "currency_basis")
        nonstd_fields = (*common, "bond_code")
        amounts = ("interest_income_514", "fair_value_change_516", "capital_gain_517", "manual_adjustment", "total_pnl")

        def signature(row: dict[str, object], fields: tuple[str, ...], *, stored: bool):
            if stored and row.get("rule_version") != PNL_FORMAL_FACT_RULE_VERSION:
                raise RuntimeError(message + " Historical rule is unsupported by this current-rule comparison.")
            source = str(row["source_version"] or "").strip()
            if not source:
                raise RuntimeError(message + " Source lineage is missing.")
            values = []
            for field in amounts:
                value = Decimal(str(row[field]))
                if not value.is_finite():
                    raise RuntimeError(message + " A formal amount is not finite.")
                values.append(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))
            return (
                *(str(row[field]) for field in fields),
                tuple(sorted(set(source.split("__")))), *values,
            )

        for current, stored, fields in (
            (current_fi, stored_fi, fi_fields), (current_nonstd, stored_nonstd, nonstd_fields),
        ):
            # Counter preserves duplicates; aggregate sums alone hide offsetting edits.
            if Counter(signature(row, fields, stored=False) for row in current) != Counter(
                signature(row, fields, stored=True) for row in stored
            ):
                raise RuntimeError(message)
    except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
        raise RuntimeError(message + " Required row comparison evidence is missing or invalid.") from exc
    return stored_fi, stored_nonstd


def _require_v1_detail_matches_formal_snapshot(
    rows: list[PnlV1DetailRow], stored_fi: list[dict[str, object]],
    stored_nonstd: list[dict[str, object]],
) -> None:
    """The legacy display formula may differ from canonical recognition (e.g. H/A 516).

    Keep both policies unchanged, but do not label an incompatible display formal.
    FI retains one signature per source leg. NonStd projects stored cost-centre
    facts to asset/portfolio rows after the canonical-grain comparison succeeds.
    """
    precision = Decimal("0.00000001")
    fields = ("interest_income_514", "fair_value_change_516", "capital_gain_517", "total_pnl")

    def values(row):
        return tuple(Decimal(str(row[field])).quantize(precision, rounding=ROUND_HALF_UP) for field in fields)

    fi_expected = Counter(
        (str(row["instrument_code"]), str(row["portfolio_name"]), *values(row)) for row in stored_fi
    )
    fi_actual = Counter(
        (row.asset_code, row.portfolio, *(value.quantize(precision, rounding=ROUND_HALF_UP) for value in (
            row.interest_income, row.fair_value_change, row.capital_gain, row.total_pnl,
        ))) for row in rows if row.source == "FI"
    )
    nonstd_expected: dict[tuple[str, str], list[Decimal]] = {}
    nonstd_manual_adjustments: dict[tuple[str, str], Decimal] = {}
    for row in stored_nonstd:
        key = (str(row["bond_code"]), str(row["portfolio_name"]))
        totals = nonstd_expected.setdefault(key, [Decimal("0")] * len(fields))
        nonstd_manual_adjustments[key] = nonstd_manual_adjustments.get(key, Decimal("0")) + Decimal(
            str(row["manual_adjustment"])
        )
        for index, value in enumerate(values(row)):
            totals[index] += value
    nonstd_expected_rows = Counter((*key, *amounts) for key, amounts in nonstd_expected.items())
    nonstd_actual = Counter(
        (row.asset_code, row.portfolio, *(value.quantize(precision, rounding=ROUND_HALF_UP) for value in (
            row.interest_income, row.fair_value_change, row.capital_gain, row.total_pnl,
        ))) for row in rows if row.source == "NonStd"
    )
    if (
        fi_actual != fi_expected or nonstd_actual != nonstd_expected_rows
        or any(nonstd_manual_adjustments.values())
    ):
        raise RuntimeError(
            "V1 PnL legacy detail components differ from the selected formal snapshot; "
            "detail is unavailable until the display and formal recognition policies agree."
        )
