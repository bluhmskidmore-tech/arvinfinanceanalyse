from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance import FiPnlRecord, build_formal_pnl_fi_fact_rows


def _fi_record(
    *,
    instrument_code: str,
    invest_type_std: str,
    accounting_basis: str,
    approval_status: str = "",
    governance_status: str = "",
    event_semantics: str = "",
    realized_flag: bool = False,
) -> FiPnlRecord:
    return FiPnlRecord(
        report_date=date(2025, 12, 31),
        instrument_code=instrument_code,
        portfolio_name="FI Desk",
        cost_center="CC100",
        invest_type_raw=invest_type_std,
        invest_type_std=invest_type_std,  # type: ignore[arg-type]
        accounting_basis=accounting_basis,  # type: ignore[arg-type]
        interest_income_514=Decimal("10.00"),
        fair_value_change_516=Decimal("5.00"),
        capital_gain_517=Decimal("4.00"),
        manual_adjustment=Decimal("3.00"),
        total_pnl=Decimal("22.00"),
        approval_status=approval_status,
        governance_status=governance_status,
        event_semantics=event_semantics,
        realized_flag=realized_flag,
    )


def test_formal_pnl_matrix_does_not_use_standardized_total_as_formal_total():
    rows = build_formal_pnl_fi_fact_rows(
        [
            _fi_record(
                instrument_code="AC-001",
                invest_type_std="H",
                accounting_basis="AC",
                approval_status="approved",
                event_semantics="realized_formal",
                realized_flag=True,
            ),
            _fi_record(
                instrument_code="OCI-001",
                invest_type_std="A",
                accounting_basis="FVOCI",
                governance_status="pending",
                event_semantics="realized_formal",
                realized_flag=True,
            ),
            _fi_record(
                instrument_code="TPL-001",
                invest_type_std="T",
                accounting_basis="FVTPL",
                approval_status="pending",
                event_semantics="mark_to_market",
                realized_flag=False,
            ),
        ]
    )

    assert [(row.instrument_code, row.total_pnl) for row in rows] == [
        ("AC-001", Decimal("17.00")),
        ("OCI-001", Decimal("14.00")),
        ("TPL-001", Decimal("15.00")),
    ]


def test_517_requires_realized_flag_and_formal_event_semantics_even_for_fvtpl():
    rows = build_formal_pnl_fi_fact_rows(
        [
            _fi_record(
                instrument_code="TPL-NOT-REALIZED",
                invest_type_std="T",
                accounting_basis="FVTPL",
                event_semantics="realized_formal",
                realized_flag=False,
            ),
            _fi_record(
                instrument_code="TPL-NOT-FORMAL-EVENT",
                invest_type_std="T",
                accounting_basis="FVTPL",
                event_semantics="mark_to_market",
                realized_flag=True,
            ),
        ]
    )

    assert [(row.instrument_code, row.capital_gain_517, row.total_pnl) for row in rows] == [
        ("TPL-NOT-REALIZED", Decimal("0"), Decimal("15.00")),
        ("TPL-NOT-FORMAL-EVENT", Decimal("0"), Decimal("15.00")),
    ]


def test_manual_adjustment_requires_governed_approval_not_free_text():
    rows = build_formal_pnl_fi_fact_rows(
        [
            _fi_record(
                instrument_code="FREE-TEXT-APPROVED",
                invest_type_std="T",
                accounting_basis="FVTPL",
                approval_status="approved in comment",
            ),
            _fi_record(
                instrument_code="GOVERNANCE-APPROVED",
                invest_type_std="T",
                accounting_basis="FVTPL",
                governance_status="approved",
            ),
        ]
    )

    assert [(row.instrument_code, row.manual_adjustment, row.total_pnl) for row in rows] == [
        ("FREE-TEXT-APPROVED", Decimal("0"), Decimal("15.00")),
        ("GOVERNANCE-APPROVED", Decimal("3.00"), Decimal("18.00")),
    ]
