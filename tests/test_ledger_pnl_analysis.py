from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance import ledger_pnl_analysis
from backend.app.core_finance.ledger_pnl_analysis import build_ledger_pnl_analysis
from backend.app.core_finance.product_category_pnl import CanonicalFactRow


def _fact(
    account_code: str,
    currency: str,
    *,
    account_name: str = "",
    beginning_balance: str = "0",
    ending_balance: str = "0",
    monthly_pnl: str = "0",
    report_date: date = date(2026, 6, 30),
) -> CanonicalFactRow:
    return CanonicalFactRow(
        report_date=report_date,
        account_code=account_code,
        currency=currency,
        account_name=account_name or account_code,
        beginning_balance=Decimal(beginning_balance),
        ending_balance=Decimal(ending_balance),
        monthly_pnl=Decimal(monthly_pnl),
        daily_avg_balance=Decimal("0"),
        annual_avg_balance=Decimal("0"),
        days_in_period=report_date.day,
    )


def _current_sample_facts() -> list[CanonicalFactRow]:
    facts = [
        _fact("10100000001", "CNX", ending_balance="1000"),
        _fact("20100000001", "CNX", ending_balance="-300"),
        _fact("10100000001", "CNY", ending_balance="800"),
        _fact("20100000001", "CNY", ending_balance="-250"),
    ]
    facts.extend(
        _fact(code, "CNX", account_name=name, monthly_pnl=amount)
        for code, name, amount in [
            ("51603030006", "贵金属掉期近端公允价值变动", "337860000"),
            ("51701010001", "金融资产差价收益", "151806954.90"),
            ("51603030002", "贵金属掉期公允价值变动损益", "-343483174.92"),
            ("51490000001", "核心补充分项1", "120000000"),
            ("51490000002", "核心补充分项2", "120000000"),
            ("51490000003", "核心补充分项3", "120000000"),
            ("51490000004", "核心补充分项4", "120000000"),
            ("51490000005", "核心补充分项5", "2442229.99"),
            ("50106000001", "中长期抵押质押贷款利息收入", "299224980.96"),
            ("50105000001", "中长期保证贷款利息收入", "233887985.36"),
            ("50101000001", "短期信用贷款利息收入", "160372151.02"),
            ("55000000001", "当期所得税", "-566796492.18"),
            ("52104000001", "定期储蓄存款利息支出", "-284190113.44"),
            ("53101000002", "个人贷款减值损失", "-179668862.33"),
            ("52300030001", "发行同业存单利息支出", "-124797878.79"),
            ("51199999999", "非核心平衡分项", "43772484.38"),
        ]
    )
    facts.extend(
        _fact(code, "CNY", account_name=name, monthly_pnl=amount)
        for code, name, amount in [
            ("51603030006", "贵金属掉期近端公允价值变动", "337860000"),
            ("51701010001", "金融资产差价收益", "151806954.90"),
            ("51603030002", "贵金属掉期公允价值变动损益", "-343483174.92"),
            ("51490000001", "核心补充分项1", "120000000"),
            ("51490000002", "核心补充分项2", "120000000"),
            ("51490000003", "核心补充分项3", "120000000"),
            ("51490000004", "核心补充分项4", "100000000"),
            ("51490000005", "核心补充分项5", "7343161.73"),
            ("50106000001", "中长期抵押质押贷款利息收入", "299224980.96"),
            ("50105000001", "中长期保证贷款利息收入", "233887985.36"),
            ("50101000001", "短期信用贷款利息收入", "150345053.46"),
            ("55000000001", "当期所得税", "-566796492.18"),
            ("52104000001", "定期储蓄存款利息支出", "-283975997.4"),
            ("53101000002", "个人贷款减值损失", "-179668862.33"),
            ("52300030001", "发行同业存单利息支出", "-124797878.79"),
            ("51199999999", "非核心平衡分项", "51242114.05"),
        ]
    )
    return facts


def _previous_sample_facts() -> list[CanonicalFactRow]:
    previous_date = date(2026, 5, 31)
    return [
        _fact(
            "51400000001",
            "CNX",
            monthly_pnl="771628427.13",
            report_date=previous_date,
        ),
        _fact(
            "50100000001",
            "CNX",
            monthly_pnl="247452701.48",
            report_date=previous_date,
        ),
        _fact(
            "51400000001",
            "CNY",
            monthly_pnl="757005005.23",
            report_date=previous_date,
        ),
        _fact(
            "50100000001",
            "CNY",
            monthly_pnl="228010666.68",
            report_date=previous_date,
        ),
    ]


def _by_metric(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["metric_key"]): row for row in rows}


@pytest.mark.parametrize(
    (
        "account_code",
        "account_name",
        "current_beginning",
        "current_ending",
        "current_pnl",
        "previous_beginning",
        "previous_ending",
        "previous_pnl",
        "expected_change",
    ),
    [
        (
            "55000000001",
            "当期所得税",
            "427246908.11",
            "994043400.29",
            "-566796492.18",
            "427246908.11",
            "427246908.11",
            "0",
            "-566796492.18",
        ),
        (
            "51603030006",
            "贵金属-贵金属掉期近端交割公允价值变动-金-自营",
            "-184650000",
            "-522510000",
            "337860000",
            "31620000",
            "-184650000",
            "216270000",
            "121590000",
        ),
    ],
)
def test_build_ledger_pnl_account_detail_locks_202606_real_account_samples(
    account_code,
    account_name,
    current_beginning,
    current_ending,
    current_pnl,
    previous_beginning,
    previous_ending,
    previous_pnl,
    expected_change,
) -> None:
    current_date = date(2026, 6, 30)
    previous_date = date(2026, 5, 31)
    current_facts = [
        _fact(
            account_code,
            basis,
            account_name=account_name,
            beginning_balance=current_beginning,
            ending_balance=current_ending,
            monthly_pnl=current_pnl,
            report_date=current_date,
        )
        for basis in ("CNX", "CNY")
    ]
    previous_facts = [
        _fact(
            account_code,
            basis,
            account_name=account_name,
            beginning_balance=previous_beginning,
            ending_balance=previous_ending,
            monthly_pnl=previous_pnl,
            report_date=previous_date,
        )
        for basis in ("CNX", "CNY")
    ]

    result = ledger_pnl_analysis.build_ledger_pnl_account_detail(
        report_date=current_date,
        source_version="sv_product_category_4490cb62d9f5",
        account_code=account_code,
        currency_basis="CNX",
        current_facts=current_facts,
        previous_report_date=previous_date,
        previous_source_version="sv_product_category_3353b116b9a6",
        previous_facts=previous_facts,
    )

    period = result["period_comparison"]
    assert period["current_monthly_pnl"] == Decimal(current_pnl)
    assert period["previous_monthly_pnl"] == Decimal(previous_pnl)
    assert period["change"] == Decimal(expected_change)
    assert period["previous_source_version"] == "sv_product_category_3353b116b9a6"
    assert result["source_version"] == "sv_product_category_4490cb62d9f5"
    assert result["basis_comparison"]["current"]["cnx_minus_cny"] == Decimal("0")
    assert result["basis_comparison"]["previous"]["cnx_minus_cny"] == Decimal("0")

    evidence = result["canonical_evidence_rows"]
    assert len(evidence) == 4
    expected_by_period = {
        "current": (
            current_date.isoformat(),
            "sv_product_category_4490cb62d9f5",
            Decimal(current_beginning),
            Decimal(current_ending),
            Decimal(current_pnl),
            30,
        ),
        "previous": (
            previous_date.isoformat(),
            "sv_product_category_3353b116b9a6",
            Decimal(previous_beginning),
            Decimal(previous_ending),
            Decimal(previous_pnl),
            31,
        ),
    }
    for row in evidence:
        expected = expected_by_period[row["period"]]
        assert (
            row["report_date"],
            row["source_version"],
            row["beginning_balance"],
            row["ending_balance"],
            row["monthly_pnl"],
            row["days_in_period"],
        ) == expected
        assert row["currency"] in {"CNX", "CNY"}
        assert "daily_avg_balance" not in row
        assert "annual_avg_balance" not in row
    assert "not raw workbook rows" in result["calculation_basis"]["evidence_boundary"]


def test_build_ledger_pnl_account_detail_uses_exact_account_and_decimal_math() -> None:
    current = [
        _fact("55000000001", "CNX", account_name="当期所得税", monthly_pnl="-10.25"),
        _fact("55000000001", "CNY", account_name="当期所得税", monthly_pnl="-8.25"),
        _fact("550000000010", "CNX", monthly_pnl="999"),
    ]
    previous_date = date(2026, 5, 31)
    previous = [
        _fact(
            "55000000001",
            "CNX",
            account_name="当期所得税",
            monthly_pnl="-7.25",
            report_date=previous_date,
        ),
        _fact(
            "55000000001",
            "CNY",
            account_name="当期所得税",
            monthly_pnl="-6.25",
            report_date=previous_date,
        ),
    ]

    result = ledger_pnl_analysis.build_ledger_pnl_account_detail(
        report_date=date(2026, 6, 30),
        source_version="sv_current",
        account_code="55000000001",
        currency_basis="CNX",
        current_facts=current,
        previous_report_date=previous_date,
        previous_source_version="sv_previous",
        previous_facts=previous,
    )

    assert result["analysis_status"] == "ready"
    assert result["metric_status"] == "candidate"
    assert result["account"] == {
        "account_code": "55000000001",
        "account_name": "当期所得税",
    }
    assert result["period_comparison"] == {
        "status": "available",
        "previous_report_date": "2026-05-31",
        "previous_source_version": "sv_previous",
        "current_monthly_pnl": Decimal("-10.25"),
        "previous_monthly_pnl": Decimal("-7.25"),
        "change": Decimal("-3.00"),
        "current_evidence_rows": 1,
        "previous_evidence_rows": 1,
    }
    current_basis = result["basis_comparison"]["current"]
    assert current_basis["cnx"] == Decimal("-10.25")
    assert current_basis["cny"] == Decimal("-8.25")
    assert current_basis["cnx_minus_cny"] == Decimal("-2.00")
    assert current_basis["evidence_rows"] == {"CNX": 1, "CNY": 1}
    assert result["basis_comparison"]["previous"]["cnx_minus_cny"] == Decimal("-1.00")
    assert len(result["canonical_evidence_rows"]) == 4
    assert {
        row["account_code"] for row in result["canonical_evidence_rows"]
    } == {"55000000001"}
    assert isinstance(result["period_comparison"]["change"], Decimal)


def test_build_ledger_pnl_account_detail_distinguishes_true_zero_from_missing_basis() -> None:
    result = ledger_pnl_analysis.build_ledger_pnl_account_detail(
        report_date=date(2026, 6, 30),
        source_version="sv_current",
        account_code="55000000001",
        currency_basis="CNX",
        current_facts=[_fact("55000000001", "CNX", monthly_pnl="0")],
        previous_report_date=None,
        previous_source_version=None,
        previous_facts=[],
    )

    assert result["analysis_status"] == "ready"
    assert result["period_comparison"]["status"] == "no_previous_period"
    assert result["period_comparison"]["current_monthly_pnl"] == Decimal("0")
    assert result["period_comparison"]["previous_monthly_pnl"] is None
    assert result["period_comparison"]["change"] is None
    assert result["basis_comparison"]["current"]["availability"] == {
        "CNX": "ready",
        "CNY": "no_data",
    }
    assert result["basis_comparison"]["current"]["cnx_minus_cny"] is None
    assert result["basis_comparison"]["previous"] is None


def test_build_ledger_pnl_account_detail_reports_current_and_previous_missing_states() -> None:
    previous_date = date(2026, 5, 31)
    current_missing = ledger_pnl_analysis.build_ledger_pnl_account_detail(
        report_date=date(2026, 6, 30),
        source_version="sv_current",
        account_code="55000000001",
        currency_basis="CNX",
        current_facts=[_fact("55000000001", "CNY", monthly_pnl="2")],
        previous_report_date=previous_date,
        previous_source_version="sv_previous",
        previous_facts=[
            _fact(
                "55000000001",
                "CNX",
                monthly_pnl="1",
                report_date=previous_date,
            )
        ],
    )
    previous_missing = ledger_pnl_analysis.build_ledger_pnl_account_detail(
        report_date=date(2026, 6, 30),
        source_version="sv_current",
        account_code="55000000001",
        currency_basis="CNX",
        current_facts=[_fact("55000000001", "CNX", monthly_pnl="2")],
        previous_report_date=previous_date,
        previous_source_version="sv_previous",
        previous_facts=[
            _fact(
                "55000000002",
                "CNX",
                monthly_pnl="1",
                report_date=previous_date,
            )
        ],
    )

    assert current_missing["analysis_status"] == "no_data"
    assert current_missing["period_comparison"]["status"] == "current_account_no_data"
    assert current_missing["period_comparison"]["current_monthly_pnl"] is None
    assert current_missing["period_comparison"]["previous_monthly_pnl"] == Decimal("1")
    assert current_missing["period_comparison"]["change"] is None
    assert previous_missing["analysis_status"] == "ready"
    assert previous_missing["period_comparison"]["status"] == "previous_account_no_data"
    assert previous_missing["period_comparison"]["previous_monthly_pnl"] is None
    assert previous_missing["basis_comparison"]["previous"]["availability"] == {
        "CNX": "no_data",
        "CNY": "no_data",
    }


def test_build_ledger_pnl_analysis_locks_202606_exact_candidate_sample() -> None:
    current_facts = _current_sample_facts()
    previous_facts = _previous_sample_facts()

    cnx = build_ledger_pnl_analysis(
        report_date=date(2026, 6, 30),
        source_version="sv_product_category_4490cb62d9f5",
        currency_basis="CNX",
        current_facts=current_facts,
        previous_report_date=date(2026, 5, 31),
        previous_source_version="sv_product_category_3353b116b9a6",
        previous_facts=previous_facts,
    )
    cny = build_ledger_pnl_analysis(
        report_date=date(2026, 6, 30),
        source_version="sv_product_category_4490cb62d9f5",
        currency_basis="CNY",
        current_facts=current_facts,
        previous_report_date=date(2026, 5, 31),
        previous_source_version="sv_product_category_3353b116b9a6",
        previous_facts=previous_facts,
    )

    assert cnx["analysis_status"] == "ready"
    assert cnx["metric_status"] == "candidate"
    assert cnx["conclusion"] == {
        "direction": "positive",
        "other_effect": "drag",
        "core_pnl": Decimal("628626009.97"),
        "other_5_pnl": Decimal("-418195745.02"),
        "all_pnl": Decimal("210430264.95"),
    }
    assert cny["conclusion"] == {
        "direction": "positive",
        "other_effect": "drag",
        "core_pnl": Decimal("613526941.71"),
        "other_5_pnl": Decimal("-420539096.87"),
        "all_pnl": Decimal("192987844.84"),
    }

    assert cnx["pnl_bridge"]["components"] == [
        {
            "metric_key": "core_pnl",
            "metric_name": "核心损益",
            "amount": Decimal("628626009.97"),
        },
        {
            "metric_key": "other_5_pnl",
            "metric_name": "其他 5* 科目损益",
            "amount": Decimal("-418195745.02"),
        },
    ]
    assert cnx["pnl_bridge"]["total"] == Decimal("210430264.95")
    assert cnx["pnl_bridge"]["residual"] == Decimal("0.00")

    basis_rows = _by_metric(cnx["basis_comparison"])
    assert basis_rows["assets"] == {
        "metric_key": "assets",
        "metric_name": "总资产",
        "cnx": Decimal("1000"),
        "cny": Decimal("800"),
        "cnx_minus_cny": Decimal("200"),
        "availability": {"CNX": "ready", "CNY": "ready"},
        "evidence_rows": {"CNX": 1, "CNY": 1},
    }
    assert basis_rows["liabilities"]["cnx_minus_cny"] == Decimal("50")
    assert basis_rows["net_assets"]["cnx_minus_cny"] == Decimal("150")
    assert basis_rows["core_pnl"]["cnx_minus_cny"] == Decimal("15099068.26")
    assert basis_rows["all_pnl"]["cnx_minus_cny"] == Decimal("17442420.11")
    assert basis_rows["other_5_pnl"]["cnx_minus_cny"] == Decimal("2343351.85")
    assert cnx["basis_availability"] == {"CNX": "ready", "CNY": "ready"}

    assert cnx["contributors"]["positive_total"] == Decimal("1709366786.61")
    assert cnx["contributors"]["negative_total"] == Decimal("-1498936521.66")
    assert cnx["contributors"]["net_total"] == Decimal("210430264.95")
    assert [row["account_code"] for row in cnx["contributors"]["top_positive"]] == [
        "51603030006",
        "50106000001",
        "50105000001",
        "50101000001",
        "51701010001",
    ]
    assert [row["amount"] for row in cnx["contributors"]["top_negative"]] == [
        Decimal("-566796492.18"),
        Decimal("-343483174.92"),
        Decimal("-284190113.44"),
        Decimal("-179668862.33"),
        Decimal("-124797878.79"),
    ]
    assert [row["account_code"] for row in cny["contributors"]["top_positive"]] == [
        "51603030006",
        "50106000001",
        "50105000001",
        "51701010001",
        "50101000001",
    ]
    assert [row["amount"] for row in cny["contributors"]["top_negative"]] == [
        Decimal("-566796492.18"),
        Decimal("-343483174.92"),
        Decimal("-283975997.4"),
        Decimal("-179668862.33"),
        Decimal("-124797878.79"),
    ]

    period_rows = _by_metric(cnx["period_comparison"]["rows"])
    assert cnx["period_comparison"]["status"] == "available"
    assert cnx["period_comparison"]["previous_report_date"] == "2026-05-31"
    assert period_rows["core_pnl"] == {
        "metric_key": "core_pnl",
        "metric_name": "核心损益",
        "current": Decimal("628626009.97"),
        "previous": Decimal("771628427.13"),
        "change": Decimal("-143002417.16"),
    }
    assert period_rows["other_5_pnl"]["change"] == Decimal("-665648446.50")
    assert period_rows["all_pnl"]["change"] == Decimal("-808650863.66")

    assert cnx["calculation_basis"]["core_pnl_prefixes"] == ["514", "516", "517"]
    assert cnx["calculation_basis"]["all_pnl_prefixes"] == ["5"]
    assert "arithmetic residual" in cnx["calculation_basis"]["other_5_pnl_boundary"]
    assert cnx["calculation_basis"]["basis_difference_formula"] == "CNX - CNY"
    assert "not FX PnL" in cnx["calculation_basis"]["basis_boundary"]
    assert "candidate" in cnx["calculation_basis"]["metric_boundary"]


def test_build_ledger_pnl_analysis_uses_stable_account_code_tiebreaks() -> None:
    facts = [
        *[
            _fact(code, "CNX", monthly_pnl="10")
            for code in [
                "50100000006",
                "50100000004",
                "50100000002",
                "50100000005",
                "50100000001",
                "50100000003",
            ]
        ],
        *[
            _fact(code, "CNX", monthly_pnl="-10")
            for code in [
                "52100000006",
                "52100000004",
                "52100000002",
                "52100000005",
                "52100000001",
                "52100000003",
            ]
        ],
    ]

    result = build_ledger_pnl_analysis(
        report_date=date(2026, 6, 30),
        source_version="sv_ties",
        currency_basis="CNX",
        current_facts=facts,
        previous_report_date=None,
        previous_source_version=None,
        previous_facts=[],
    )

    assert [row["account_code"] for row in result["contributors"]["top_positive"]] == [
        "50100000001",
        "50100000002",
        "50100000003",
        "50100000004",
        "50100000005",
    ]
    assert [row["rank"] for row in result["contributors"]["top_positive"]] == [1, 2, 3, 4, 5]
    assert [row["account_code"] for row in result["contributors"]["top_negative"]] == [
        "52100000001",
        "52100000002",
        "52100000003",
        "52100000004",
        "52100000005",
    ]
    assert result["period_comparison"]["status"] == "no_previous_period"


def test_build_ledger_pnl_analysis_marks_selected_basis_no_data_explicitly() -> None:
    result = build_ledger_pnl_analysis(
        report_date=date(2026, 6, 30),
        source_version="sv_cny_only",
        currency_basis="CNX",
        current_facts=[_fact("50100000001", "CNY", monthly_pnl="25")],
        previous_report_date=date(2026, 5, 31),
        previous_source_version="sv_previous",
        previous_facts=_previous_sample_facts(),
    )

    assert result["analysis_status"] == "no_data"
    assert result["conclusion"] == {
        "direction": "unavailable",
        "other_effect": "unavailable",
        "core_pnl": None,
        "other_5_pnl": None,
        "all_pnl": None,
    }
    assert result["contributors"] == {
        "positive_total": None,
        "negative_total": None,
        "net_total": None,
        "top_positive": [],
        "top_negative": [],
    }
    assert result["pnl_bridge"] == {
        "components": [
            {
                "metric_key": "core_pnl",
                "metric_name": "核心损益",
                "amount": None,
            },
            {
                "metric_key": "other_5_pnl",
                "metric_name": "其他 5* 科目损益",
                "amount": None,
            },
        ],
        "total": None,
        "residual": None,
    }
    assert result["period_comparison"]["status"] == "current_basis_no_data"
    assert result["period_comparison"]["rows"] == []
    assert result["basis_availability"] == {"CNX": "no_data", "CNY": "ready"}
    all_pnl = _by_metric(result["basis_comparison"])["all_pnl"]
    assert all_pnl == {
        "metric_key": "all_pnl",
        "metric_name": "全量损益",
        "cnx": None,
        "cny": Decimal("25"),
        "cnx_minus_cny": None,
        "availability": {"CNX": "no_data", "CNY": "ready"},
        "evidence_rows": {"CNX": 0, "CNY": 1},
    }


def test_build_ledger_pnl_analysis_keeps_balance_metrics_when_selected_pnl_is_missing() -> None:
    result = build_ledger_pnl_analysis(
        report_date=date(2026, 6, 30),
        source_version="sv_balance_only",
        currency_basis="CNX",
        current_facts=[
            _fact("10100000001", "CNX", ending_balance="1000"),
            _fact("20100000001", "CNX", ending_balance="-400"),
        ],
        previous_report_date=None,
        previous_source_version=None,
        previous_facts=[],
    )

    rows = _by_metric(result["basis_comparison"])
    assert result["analysis_status"] == "no_data"
    assert result["basis_availability"] == {"CNX": "no_data", "CNY": "no_data"}
    assert rows["assets"] == {
        "metric_key": "assets",
        "metric_name": "总资产",
        "cnx": Decimal("1000"),
        "cny": None,
        "cnx_minus_cny": None,
        "availability": {"CNX": "ready", "CNY": "no_data"},
        "evidence_rows": {"CNX": 1, "CNY": 0},
    }
    assert rows["liabilities"]["cnx"] == Decimal("400")
    assert rows["liabilities"]["availability"] == {"CNX": "ready", "CNY": "no_data"}
    assert rows["net_assets"]["cnx"] == Decimal("600")
    assert rows["net_assets"]["evidence_rows"] == {"CNX": 2, "CNY": 0}
    assert rows["all_pnl"]["cnx"] is None
    assert rows["all_pnl"]["availability"] == {"CNX": "no_data", "CNY": "no_data"}


def test_build_ledger_pnl_analysis_does_not_invent_balance_zero_from_pnl_only_rows() -> None:
    result = build_ledger_pnl_analysis(
        report_date=date(2026, 6, 30),
        source_version="sv_pnl_only",
        currency_basis="CNX",
        current_facts=[
            _fact("51400000001", "CNX", monthly_pnl="10"),
            _fact("50100000001", "CNY", monthly_pnl="25"),
        ],
        previous_report_date=None,
        previous_source_version=None,
        previous_facts=[],
    )

    rows = _by_metric(result["basis_comparison"])
    assert result["analysis_status"] == "ready"
    assert result["basis_availability"] == {"CNX": "ready", "CNY": "ready"}
    assert rows["assets"] == {
        "metric_key": "assets",
        "metric_name": "总资产",
        "cnx": None,
        "cny": None,
        "cnx_minus_cny": None,
        "availability": {"CNX": "no_data", "CNY": "no_data"},
        "evidence_rows": {"CNX": 0, "CNY": 0},
    }
    assert rows["liabilities"]["cnx"] is None
    assert rows["net_assets"]["cnx"] is None
    assert rows["core_pnl"]["cnx"] == Decimal("10")
    assert rows["core_pnl"]["cny"] == Decimal("0")
    assert rows["core_pnl"]["cnx_minus_cny"] == Decimal("10")
    assert rows["core_pnl"]["availability"] == {"CNX": "ready", "CNY": "ready"}
    assert rows["core_pnl"]["evidence_rows"] == {"CNX": 1, "CNY": 1}
