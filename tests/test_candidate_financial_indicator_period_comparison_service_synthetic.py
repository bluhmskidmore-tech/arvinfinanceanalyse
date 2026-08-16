# -*- coding: utf-8 -*-
"""合成版期间比较回放：CI 可跑，对应 test_candidate_financial_indicator_period_comparison_service.py
的真实源 skipif 用例 test_real_202606_period_comparison_is_partial_with_controlled_full_scope_gap。

与真实回放走完全相同的服务路径（磁盘 xlsx -> 安全解析器 -> 规则引擎 -> 组件桥 -> schema），
仅数据源换成 tests/synthetic_ledger_pnl_fixture.py 生成的编造工作簿；
全部期望值可按 fixture 模块 docstring 中的推导手算复核。
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.services.candidate_financial_indicator_period_comparison_service import (
    candidate_financial_indicator_period_comparison_envelope,
)
from tests.synthetic_ledger_pnl_fixture import (
    SYNTHETIC_REPORT_MONTH,
    write_synthetic_ledger_source_dir,
)


@pytest.fixture(scope="module")
def synthetic_source_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_synthetic_ledger_source_dir(
        tmp_path_factory.mktemp("synthetic_ledger_pnl")
    )


def test_synthetic_period_comparison_reconciles_with_hand_computed_expectations(
    synthetic_source_dir: Path,
) -> None:
    payload = candidate_financial_indicator_period_comparison_envelope(
        source_dir=str(synthetic_source_dir),
        report_month=SYNTHETIC_REPORT_MONTH,
    )

    assert payload["contract_version"] == (
        "candidate-financial-indicator-period-comparison-v2"
    )
    assert payload["report_month"] == "202503"
    assert payload["comparison_month"] == "202502"
    assert payload["two_month_prior"] == "202501"
    assert payload["comparison_scope"] == "ledger_only_key_metrics"
    assert payload["overall_status"] == "partial"
    # 合成目录刻意不提供 日均202502.xlsx，走 missing_source_file 受控缺口分支。
    assert payload["full_scope_status"] == "unavailable"
    assert payload["full_scope_reason_code"] == "missing_source_file"
    assert payload["full_scope_gaps"] == [
        {
            "reason_code": "missing_source_file",
            "source_kind": "daily",
            "month": "202502",
            "required_sheet": None,
        }
    ]

    # 合成月份不在治理锁清单（202604-202606）内：走真实的 unlocked 分支，
    # 质量口径整体降为 degraded_candidate；ledger_sha256 必须与磁盘文件一致。
    assert [item["month"] for item in payload["source_periods"]] == [
        "202503",
        "202502",
        "202501",
    ]
    assert [item["lock_status"] for item in payload["source_periods"]] == [
        "unlocked",
        "unlocked",
        "unlocked",
    ]
    assert all(item["locked_sha256"] is None for item in payload["source_periods"])
    for item in payload["source_periods"]:
        workbook_bytes = (synthetic_source_dir / item["ledger_file_name"]).read_bytes()
        assert item["ledger_sha256"] == hashlib.sha256(workbook_bytes).hexdigest()

    by_id = {item["metric_id"]: item for item in payload["metrics"]}
    assert (
        sum(item["comparison_status"] == "comparable" for item in payload["metrics"])
        == 5
    )
    assert (
        sum(
            item["comparison_status"] == "not_comparable" for item in payload["metrics"]
        )
        == 2
    )
    assert by_id["income.noninterest.total"]["quality_status"] == "not_comparable"
    assert by_id["income.operating.mother_bank"]["quality_status"] == "not_comparable"

    # 净利息（手算：累计 0.07 / 0.140 / 0.256 → 本月 0.116、上月 0.070、delta +0.046）。
    interest = by_id["income.interest.net"]
    assert interest["comparison_status"] == "comparable"
    assert interest["quality_status"] == "degraded_candidate"
    assert interest["current_source_value_yi"] == "0.256"
    assert interest["previous_source_value_yi"] == "0.140"
    assert interest["two_month_prior_source_value_yi"] == "0.070"
    assert interest["current_value_yi"] == "0.116"
    assert interest["previous_value_yi"] == "0.070"
    assert interest["delta_yi"] == "0.046"
    assert Decimal(interest["change_rate"]) == Decimal("0.046") / Decimal("0.070")
    assert interest["rate_reason"] is None

    # 四个点位余额指标（手算见 fixture docstring 的余额类推导）。
    corporate_deposit = by_id["balance.deposit.corporate.total::point"]
    assert corporate_deposit["comparison_status"] == "comparable"
    assert corporate_deposit["current_value_yi"] == "11.04"
    assert corporate_deposit["previous_value_yi"] == "10.12"
    assert corporate_deposit["delta_yi"] == "0.92"
    assert corporate_deposit["two_month_prior_source_value_yi"] is None
    retail_deposit = by_id["balance.deposit.retail.total::point"]
    assert retail_deposit["current_value_yi"] == "3.36"
    assert retail_deposit["previous_value_yi"] == "3.08"
    assert retail_deposit["delta_yi"] == "0.28"
    corporate_loan = by_id["balance.loan.corporate.total::point"]
    assert corporate_loan["current_value_yi"] == "5.72"
    assert corporate_loan["previous_value_yi"] == "5.56"
    assert corporate_loan["delta_yi"] == "0.16"
    retail_loan = by_id["balance.loan.retail.total::point"]
    assert retail_loan["current_value_yi"] == "3.58"
    assert retail_loan["previous_value_yi"] == "3.44"
    assert retail_loan["delta_yi"] == "0.14"

    # 组件桥：贡献合计必须精确闭合到净利息 delta（0.005-0.005+0.04+0.006=0.046）。
    bridge = payload["net_interest_component_bridge"]
    assert bridge["analysis_kind"] == "accounting_component_bridge"
    assert bridge["status"] == "available"
    assert bridge["metric_id"] == "income.interest.net"
    assert bridge["basis"] == "calendar_month_from_cumulative"
    assert bridge["method"] == "finance_metric_component_contribution"
    assert bridge["unit"] == "亿元"
    assert bridge["quality_status"] == "degraded_candidate"
    assert bridge["foot_status"] == "passed"
    assert bridge["net_delta_yi"] == "0.046"
    assert bridge["component_contribution_total_yi"] == "0.046"
    assert bridge["reconciliation_delta_yi"] == "0"
    assert bridge["reasons"] == []
    assert [item["metric_id"] for item in bridge["components"]] == [
        "income.interest.loan.total",
        "expense.interest.deposit.total",
        "income.interest.investment",
        "income.interest.interbank_net",
    ]
    assert [item["formula_weight"] for item in bridge["components"]] == [1, -1, 1, 1]
    assert [item["current_value_yi"] for item in bridge["components"]] == [
        "0.025",
        "0.025",
        "0.09",
        "0.026",
    ]
    assert [item["previous_value_yi"] for item in bridge["components"]] == [
        "0.02",
        "0.02",
        "0.05",
        "0.020",
    ]
    assert [item["component_delta_yi"] for item in bridge["components"]] == [
        "0.005",
        "0.005",
        "0.04",
        "0.006",
    ]
    assert [item["contribution_to_net_delta_yi"] for item in bridge["components"]] == [
        "0.005",
        "-0.005",
        "0.04",
        "0.006",
    ]
    # 桥闭合性的显式代数复核（存款利息支出 delta 为正、经权重 -1 转为负贡献）。
    assert sum(
        Decimal(item["contribution_to_net_delta_yi"]) for item in bridge["components"]
    ) == Decimal(bridge["net_delta_yi"])
