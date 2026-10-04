from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest

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


def test_unnormalized_fi_source_517_zeroing_emits_explicit_disclosure(caplog):
    """绕过源表标准化、缺少已实现语义的 517 仍拒绝进入正式事实并披露。"""
    with caplog.at_level(logging.WARNING):
        rows = build_formal_pnl_fi_fact_rows(
            [
                _fi_record(
                    instrument_code="TPL-PRE-EFFECTIVE",
                    invest_type_std="T",
                    accounting_basis="FVTPL",
                    report_date=date(2024, 12, 31),
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
    assert "2024-12-31" in messages[0]
    assert "4.00" in messages[0]
    assert "not derived by source normalization" in messages[0]


def test_explicitly_recognized_historical_517_does_not_emit_disclosure(caplog):
    """历史日期中具有已实现语义的标准化行正常进入正式事实。"""
    with caplog.at_level(logging.WARNING):
        rows = build_formal_pnl_fi_fact_rows(
            [
                _fi_record(
                    instrument_code="TPL-PRE-EFFECTIVE-RECOGNIZED",
                    invest_type_std="T",
                    accounting_basis="FVTPL",
                    report_date=date(2024, 12, 31),
                    event_type=FI_CUMULATIVE_REALIZED_517_EVENT_TYPE,
                    event_semantics="realized_incremental",
                    realized_flag=True,
                ),
            ]
        )

    assert rows[0].capital_gain_517 == Decimal("4.00")
    assert _disclosure_messages(caplog) == []


def test_full_chain_cumulative_517_is_independent_of_report_date(caplog):
    """全链路锁定：2025 年以前、2026H1 与 7 月以后均沿用同一 FI 源口径。

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
        h1 = build_formal_pnl_fi_fact_rows(
            normalize_fi_pnl_records([_raw_row("2026-03-31", "FI-H1")])
        )
        post_h1_normalized = normalize_fi_pnl_records(
            [_raw_row("2026-07-31", "FI-POST-H1")]
        )
        post_h1 = build_formal_pnl_fi_fact_rows(post_h1_normalized)
    # 2026 全年延续同一源口径：符号反向 ÷1.06 后进入正式事实，无披露。
    assert h1[0].capital_gain_517 == Decimal("-10")
    assert post_h1_normalized[0].capital_gain_517 == Decimal("-10")
    assert post_h1_normalized[0].realized_flag is True
    assert post_h1[0].capital_gain_517 == Decimal("-10")
    assert _disclosure_messages(caplog) == []

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        pre_effective_normalized = normalize_fi_pnl_records(
            [_raw_row("2024-12-31", "FI-PRE-EFFECTIVE")]
        )
        pre_effective = build_formal_pnl_fi_fact_rows(pre_effective_normalized)
    assert pre_effective_normalized[0].capital_gain_517 == Decimal("-10")
    assert pre_effective_normalized[0].realized_flag is True
    assert pre_effective[0].capital_gain_517 == Decimal("-10")
    assert _disclosure_messages(caplog) == []


@pytest.mark.parametrize("report_date", [
    "0001-01-01", "2024-12-31", "2025-01-01", "2025-12-31", "2026-07-31", "9999-12-31",
])
@pytest.mark.parametrize("invest_type", ["H", "A", "T"])
@pytest.mark.parametrize("raw_517,expected_517", [("-106", "100"), ("106", "-100")])
def test_treasury_cumulative_517_recognition_applies_to_all_dates(
    report_date, invest_type, raw_517, expected_517, caplog
):
    """国债收益与损失均沿用已确认的符号、含税及已实现口径。"""
    normalized = normalize_fi_pnl_records([{
        "report_date": report_date,
        "instrument_code": "TREASURY-517",
        "portfolio_name": "FI Desk",
        "cost_center": "CC100",
        "invest_type_raw": invest_type,
        "asset_class": "国债",
        "interest_income_514": "10",
        "fair_value_change_516": "5",
        "capital_gain_517": raw_517,
        "event_type": FI_CUMULATIVE_REALIZED_517_EVENT_TYPE,
        "currency_basis": "CNY",
    }])
    with caplog.at_level(logging.WARNING):
        formal = build_formal_pnl_fi_fact_rows(normalized)[0]

    assert normalized[0].realized_flag is True
    assert normalized[0].event_semantics == (
        "realized_incremental" if invest_type == "T" else "realized_formal"
    )
    assert formal.capital_gain_517 == Decimal(expected_517)
    assert formal.interest_income_514 == Decimal("10")
    assert formal.fair_value_change_516 == (Decimal("5") if invest_type == "T" else Decimal("0"))
    assert formal.total_pnl == Decimal(expected_517) + Decimal("10") + formal.fair_value_change_516
    assert _disclosure_messages(caplog) == []
