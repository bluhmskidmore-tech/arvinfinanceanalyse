# -*- coding: utf-8 -*-
"""合成版组件明细回放：CI 可跑，对应 test_finance_metric_component_detail.py 的真实源
skipif 用例（精确对账 / top 科目源定位 / 抵消户可见但不入脚）。

经 candidate_financial_indicator_component_detail_envelope 服务路径触达
core_finance.build_finance_metric_component_detail（比原 core 层用例更外一层，
同时覆盖 parent 幂等键校验与 schema 收口）；数据源为
tests/synthetic_ledger_pnl_fixture.py 的编造工作簿，期望值均可手算复核。
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from backend.app.services.candidate_financial_indicator_period_comparison_service import (
    candidate_financial_indicator_component_detail_envelope,
    candidate_financial_indicator_period_comparison_envelope,
)
from tests.synthetic_ledger_pnl_fixture import (
    SYNTHETIC_REPORT_MONTH,
    write_synthetic_ledger_source_dir,
)


@pytest.fixture(scope="module")
def synthetic_source_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_synthetic_ledger_source_dir(
        tmp_path_factory.mktemp("synthetic_component_detail")
    )


@pytest.fixture(scope="module")
def parent_payload(synthetic_source_dir: Path) -> dict[str, Any]:
    return candidate_financial_indicator_period_comparison_envelope(
        source_dir=str(synthetic_source_dir),
        report_month=SYNTHETIC_REPORT_MONTH,
    )


def _detail(
    source_dir: Path,
    parent: dict[str, Any],
    metric_id: str,
) -> dict[str, Any]:
    return candidate_financial_indicator_component_detail_envelope(
        source_dir=str(source_dir),
        report_month=SYNTHETIC_REPORT_MONTH,
        metric_id=metric_id,
        parent_idempotency_key=str(parent["idempotency_key"]),
    )


def test_synthetic_investment_detail_reconciles_and_locates_source_cells(
    synthetic_source_dir: Path,
    parent_payload: dict[str, Any],
) -> None:
    detail = _detail(
        synthetic_source_dir, parent_payload, "income.interest.investment"
    )

    assert detail["status"] == "available"
    assert detail["quality_status"] == "degraded_candidate"
    assert detail["foot_status"] == "passed"
    assert detail["formula_weight"] == 1
    # 手算：514 累计 0.05/0.1/0.19 亿 → 本月 0.09、上月 0.05、delta/贡献 +0.04。
    assert detail["parent_current_value_yi"] == "0.09"
    assert detail["parent_previous_value_yi"] == "0.05"
    assert detail["parent_component_delta_yi"] == "0.04"
    assert detail["parent_contribution_to_net_delta_yi"] == "0.04"
    assert detail["account_current_total_yi"] == "0.09"
    assert detail["account_previous_total_yi"] == "0.05"
    assert detail["account_component_delta_total_yi"] == "0.04"
    assert detail["account_contribution_total_yi"] == "0.04"
    # 科目层合计与父层组件值必须精确闭合（四路对账全为 0）。
    assert detail["current_reconciliation_yi"] == "0"
    assert detail["previous_reconciliation_yi"] == "0"
    assert detail["component_delta_reconciliation_yi"] == "0"
    assert detail["contribution_reconciliation_yi"] == "0"
    assert detail["reasons"] == []

    assert len(detail["rows"]) == 1
    top = detail["rows"][0]
    assert top["row_status"] == "contributing"
    assert top["account_code"] == "51402010003"
    assert top["currency"] == "CNX"
    assert top["effective_component_weight"] == "-1"
    assert top["effective_net_weight"] == "-1"
    assert top["matched_terms"] == [
        {"source": "ledger", "level": "l1", "code": "514", "weight": "-1"}
    ]
    # 期末余额为编造的贷方累计（-5M/-10M/-19M），月度化后经 l1 514 权重 -1 转正。
    assert top["current_ending_yuan"] == "-19000000"
    assert top["previous_ending_yuan"] == "-10000000"
    assert top["two_month_prior_ending_yuan"] == "-5000000"
    assert top["current_value_yi"] == "0.09"
    assert top["previous_value_yi"] == "0.05"
    assert top["component_delta_yi"] == "0.04"
    assert top["contribution_to_net_delta_yi"] == "0.04"

    # 源证据：三期均定位到固定写入行（51402010003 恒为综本第 12 行）。
    assert [item["month"] for item in top["source_evidence"]] == [
        "202503",
        "202502",
        "202501",
    ]
    assert [item["report_date"] for item in top["source_evidence"]] == [
        "2025-03-31",
        "2025-02-28",
        "2025-01-31",
    ]
    current_evidence = top["source_evidence"][0]
    assert current_evidence["ledger_file_name"] == "总账对账202503.xlsx"
    assert current_evidence["sheet"] == "综本"
    assert current_evidence["row"] == 12
    assert current_evidence["account_code_cell"] == "A12"
    assert current_evidence["ending_cell"] == "G12"
    assert current_evidence["lock_status"] == "unlocked"
    assert current_evidence["locked_sha256"] is None
    assert current_evidence["ending_yuan"] == "-19000000"
    # 明细源身份必须与父层期间契约一致（同一磁盘文件、同一 sha256）。
    assert [item["ledger_sha256"] for item in top["source_evidence"]] == [
        item["ledger_sha256"] for item in parent_payload["source_periods"]
    ]


def test_synthetic_interbank_offset_term_is_visible_but_excluded_from_foot(
    synthetic_source_dir: Path,
    parent_payload: dict[str, Any],
) -> None:
    detail = _detail(
        synthetic_source_dir, parent_payload, "income.interest.interbank_net"
    )

    assert detail["status"] == "available"
    assert detail["foot_status"] == "passed"
    # 手算：贡献 = 50201000001 +0.003、52201000001 +0.002、52301000001 +0.001，
    # 合计 +0.006 = 父层组件贡献；抵消户 50206000001 不入脚。
    assert detail["account_contribution_total_yi"] == "0.006"
    assert detail["contribution_reconciliation_yi"] == "0"

    assert [item["account_code"] for item in detail["rows"]] == [
        "50201000001",
        "52201000001",
        "52301000001",
        "50206000001",
    ]
    contributing = [
        item for item in detail["rows"] if item["row_status"] == "contributing"
    ]
    assert [item["contribution_to_net_delta_yi"] for item in contributing] == [
        "0.003",
        "0.002",
        "0.001",
    ]

    offset = detail["rows"][-1]
    assert offset["account_code"] == "50206000001"
    assert offset["row_status"] == "excluded_offset"
    # l1 502 权重 -1 与 l2 50206 权重 +1 相互抵消：可见但权重与贡献均为 0。
    assert offset["effective_component_weight"] == "0"
    assert offset["effective_net_weight"] == "0"
    assert offset["matched_terms"] == [
        {"source": "ledger", "level": "l1", "code": "502", "weight": "-1"},
        {"source": "ledger", "level": "l2", "code": "50206", "weight": "1"},
    ]
    assert offset["contribution_to_net_delta_yi"] == "0"
    assert offset["current_ending_yuan"] == "3500000"


def test_synthetic_loan_detail_applies_negative_l2_offset_weight(
    synthetic_source_dir: Path,
    parent_payload: dict[str, Any],
) -> None:
    detail = _detail(
        synthetic_source_dir, parent_payload, "income.interest.loan.total"
    )

    assert detail["status"] == "available"
    assert detail["foot_status"] == "passed"
    # 手算：50101000001 贡献 +0.01；共享抵消户 50206000001 在贷款组件按
    # l2 50206 权重 -1 计入，贡献 -0.005；合计 +0.005 = 父层组件贡献。
    assert detail["account_contribution_total_yi"] == "0.005"
    assert detail["contribution_reconciliation_yi"] == "0"

    assert [item["account_code"] for item in detail["rows"]] == [
        "50101000001",
        "50206000001",
    ]
    loan_income, shared_offset = detail["rows"]
    assert loan_income["row_status"] == "contributing"
    assert loan_income["matched_terms"] == [
        {"source": "ledger", "level": "l1", "code": "501", "weight": "-1"}
    ]
    assert loan_income["contribution_to_net_delta_yi"] == "0.01"

    assert shared_offset["row_status"] == "contributing"
    assert shared_offset["effective_component_weight"] == "-1"
    assert shared_offset["matched_terms"] == [
        {"source": "ledger", "level": "l2", "code": "50206", "weight": "-1"}
    ]
    assert shared_offset["contribution_to_net_delta_yi"] == "-0.005"
    # 同一抵消户在 interbank 组件中权重归零、在贷款组件中权重 -1：
    # 两条腿合计等于其对净利息的真实净效应（此处 -0.005 + 0 = -0.005）。
    assert Decimal(loan_income["contribution_to_net_delta_yi"]) + Decimal(
        shared_offset["contribution_to_net_delta_yi"]
    ) == Decimal(detail["account_contribution_total_yi"])
