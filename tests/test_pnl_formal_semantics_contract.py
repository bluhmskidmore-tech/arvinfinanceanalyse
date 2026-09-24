from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from backend.app.core_finance import (
    FiPnlRecord,
    build_formal_pnl_fi_fact_rows,
    normalize_fi_pnl_records,
)
from backend.app.core_finance.pnl import FI_CUMULATIVE_REALIZED_517_EVENT_TYPE


def _fi_record(
    *,
    instrument_code: str,
    invest_type_std: str,
    accounting_basis: str,
    approval_status: str = "",
    governance_status: str = "",
    event_semantics: str = "",
    realized_flag: bool = False,
    report_date: date = date(2025, 12, 31),
    event_type: str = "",
) -> FiPnlRecord:
    return FiPnlRecord(
        report_date=report_date,
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
        event_type=event_type,
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
            _fi_record(
                instrument_code="TPL-REALIZED-FORMAL-BUT-OVERLAP-NOT-PROVEN",
                invest_type_std="T",
                accounting_basis="FVTPL",
                event_semantics="realized_formal",
                realized_flag=True,
            ),
        ]
    )

    assert [(row.instrument_code, row.capital_gain_517, row.total_pnl) for row in rows] == [
        ("TPL-NOT-REALIZED", Decimal("0"), Decimal("15.00")),
        ("TPL-NOT-FORMAL-EVENT", Decimal("0"), Decimal("15.00")),
        ("TPL-REALIZED-FORMAL-BUT-OVERLAP-NOT-PROVEN", Decimal("0"), Decimal("15.00")),
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


def test_fvtpl_517_enters_formal_only_when_event_semantics_prove_no_overlap_with_516():
    rows = build_formal_pnl_fi_fact_rows(
        [
            _fi_record(
                instrument_code="TPL-INCREMENTAL",
                invest_type_std="T",
                accounting_basis="FVTPL",
                event_semantics="realized_incremental",
                realized_flag=True,
            ),
            _fi_record(
                instrument_code="TPL-NO-PRIOR-516",
                invest_type_std="T",
                accounting_basis="FVTPL",
                event_semantics="realized_no_prior_516",
                realized_flag=True,
            ),
        ]
    )

    assert [(row.instrument_code, row.capital_gain_517, row.total_pnl) for row in rows] == [
        ("TPL-INCREMENTAL", Decimal("4.00"), Decimal("19.00")),
        ("TPL-NO-PRIOR-516", Decimal("4.00"), Decimal("19.00")),
    ]


def _disclosure_messages(caplog) -> list[str]:
    return [record.message for record in caplog.records if "[formal-pnl-517]" in record.message]


def test_out_of_window_cumulative_517_zeroing_emits_explicit_disclosure(caplog):
    """2026H1 窗口外的 fi_cumulative_realized_517 归零必须显式披露（fail-loud 不 fail-closed）。

    2026-08 B8：窗口外（>= 2026-07）累计 517 事件的认定规则待治理决定；在规则落地前，
    正式 capital_gain_517 归零的数值行为保持不变，但归零不得再是静默的。
    """
    with caplog.at_level(logging.WARNING):
        rows = build_formal_pnl_fi_fact_rows(
            [
                _fi_record(
                    instrument_code="TPL-POST-WINDOW",
                    invest_type_std="T",
                    accounting_basis="FVTPL",
                    report_date=date(2026, 7, 31),
                    event_type=FI_CUMULATIVE_REALIZED_517_EVENT_TYPE,
                    realized_flag=False,
                ),
            ]
        )

    # 数值行为不变：正式 517 仍归零，total 不含 517。
    assert rows[0].capital_gain_517 == Decimal("0")
    assert rows[0].total_pnl == Decimal("15.00")
    # 归零必须带一条聚合披露，含报告日与被排除金额。
    messages = _disclosure_messages(caplog)
    assert len(messages) == 1
    assert "2026-07-31" in messages[0]
    assert "4.00" in messages[0]
    assert "governance decision" in messages[0]


def test_explicitly_recognized_out_of_window_517_does_not_emit_disclosure(caplog):
    """窗口外但已被显式认定（realized_flag + 合法 event_semantics）的行不触发披露。"""
    with caplog.at_level(logging.WARNING):
        rows = build_formal_pnl_fi_fact_rows(
            [
                _fi_record(
                    instrument_code="TPL-POST-WINDOW-RECOGNIZED",
                    invest_type_std="T",
                    accounting_basis="FVTPL",
                    report_date=date(2026, 7, 31),
                    event_type=FI_CUMULATIVE_REALIZED_517_EVENT_TYPE,
                    event_semantics="realized_incremental",
                    realized_flag=True,
                ),
            ]
        )

    assert rows[0].capital_gain_517 == Decimal("4.00")
    assert _disclosure_messages(caplog) == []


def test_full_chain_out_of_window_517_zeroes_with_disclosure_and_in_window_stays_silent(caplog):
    """全链路（normalize → build）锁定：窗口外归零必须披露，窗口内正常认定保持无披露。

    输入模拟 _parse_fi_rows 的产物：event_type 无条件为 fi_cumulative_realized_517，
    不带 realized_flag / event_semantics。
    """

    def _raw_row(report_date: str, instrument_code: str) -> dict[str, object]:
        return {
            "report_date": report_date,
            "instrument_code": instrument_code,
            "portfolio_name": "FI Desk",
            "cost_center": "CC100",
            "invest_type_raw": "交易性金融资产",
            "asset_class": "国债",
            "interest_income_514": Decimal("0"),
            "fair_value_change_516": Decimal("0"),
            "capital_gain_517": Decimal("10.60"),
            "event_type": FI_CUMULATIVE_REALIZED_517_EVENT_TYPE,
            "currency_basis": "CNY",
        }

    with caplog.at_level(logging.WARNING):
        in_window = build_formal_pnl_fi_fact_rows(
            normalize_fi_pnl_records([_raw_row("2026-03-31", "FI-IN-WINDOW")])
        )
    # 窗口内：符号反向 ÷1.06 后进入正式事实，无披露。
    assert in_window[0].capital_gain_517 == Decimal("-10")
    assert _disclosure_messages(caplog) == []

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        normalized = normalize_fi_pnl_records([_raw_row("2026-07-31", "FI-POST-WINDOW")])
        out_of_window = build_formal_pnl_fi_fact_rows(normalized)
    # 窗口外：标准化层保留未翻转原值，正式层归零，且必须披露。
    assert normalized[0].capital_gain_517 == Decimal("10.60")
    assert normalized[0].realized_flag is False
    assert out_of_window[0].capital_gain_517 == Decimal("0")
    messages = _disclosure_messages(caplog)
    assert len(messages) == 1
    assert "2026-07-31" in messages[0]
    assert "10.60" in messages[0]
