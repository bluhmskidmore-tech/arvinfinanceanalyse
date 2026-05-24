from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from tests.helpers import ROOT, load_module
from tests.test_qdb_gl_monthly_analysis_core import (
    _real_month_source,
    _real_qdb_gl_source_dir,
)

SAMPLE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "formal_financial_indicators"
    / "ledger_pnl_202603_financial_indicator_golden.json"
)


def _load_sample() -> dict[str, Any]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def _metrics_by_key(sample: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(metric["metric_key"]): metric for metric in sample["metrics"]}


def test_ledger_pnl_202603_golden_sample_freezes_excel_values_units_and_source_statuses():
    sample = _load_sample()

    assert sample["sample_id"] == "GS-LEDGER-PNL-FIN-IND-202603-B"
    assert sample["sample_status"] == "contract_fixture"
    assert sample["report_month"] == "202603"
    assert sample["source_workbook"].endswith("2026年财务指标表-3月最终(1).xlsx")

    metrics = _metrics_by_key(sample)
    assert metrics["group.operating_revenue"] == {
        "metric_key": "group.operating_revenue",
        "metric_name": "集团营业收入",
        "scope": "group_consolidated",
        "excel_value": "43.4194731314",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K5 -> 财务指标-计算表!K5",
        "formula": "=4341947313.14/100000000",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    }
    assert metrics["group.cost_income_ratio"]["excel_value"] == "22.4174363027"
    assert metrics["group.cost_income_ratio"]["unit"] == "%"
    assert metrics["group.cost_income_ratio"]["formula"] == "财务指标-汇总!K31 = K10 / K5"
    assert metrics["parent.loan_balance"]["source_status"] == "candidate_qdb_aligned"
    assert metrics["parent.loan_balance"]["system_metric"] == "qdb.loan_spot"
    assert metrics["parent.loan_balance"]["system_value"] == "4189.47"
    assert metrics["parent.deposit_balance"]["source_status"] == "needs_reconciliation"
    assert metrics["parent.deposit_balance"]["system_value"] == "5115.96"
    assert metrics["parent.deposit_balance"]["reconciliation_gap"] == "4.6780974646"

    formal_pending = [
        metric
        for metric in metrics.values()
        if metric["source_status"] == "formal_pending"
    ]
    assert formal_pending
    assert all(metric["system_value"] is None for metric in formal_pending)


def test_formal_financial_indicator_registry_exposes_202603_contract_without_promoting_values():
    sample = _load_sample()
    registry = load_module(
        "backend.app.core_finance.formal_financial_indicators",
        "backend/app/core_finance/formal_financial_indicators.py",
    )

    contract = registry.build_formal_financial_indicator_contract(report_month="202603")

    assert contract["sample_id"] == sample["sample_id"]
    assert contract["report_month"] == "202603"
    assert contract["source_version"] == "sv_formal_financial_indicators_excel_202603_contract"
    assert contract["rule_version"] == "rv_formal_financial_indicators_source_status_v1"
    assert contract["formal_use_allowed"] is False

    contract_metrics = _metrics_by_key(contract)
    sample_metrics = _metrics_by_key(sample)
    assert contract_metrics.keys() == sample_metrics.keys()

    pending = [
        metric
        for metric in contract_metrics.values()
        if metric["source_status"] == "formal_pending"
    ]
    assert pending
    assert all(metric["value"] is None for metric in pending)
    assert all(metric["system_value"] is None for metric in pending)
    assert all(metric["formal_use_allowed"] is False for metric in contract_metrics.values())
    assert contract_metrics["parent.loan_balance"]["source_status"] == "candidate_qdb_aligned"
    assert contract_metrics["parent.loan_balance"]["value"] is None
    assert contract_metrics["parent.loan_balance"]["consolidation_scope"] == "parent_company"
    assert contract_metrics["parent.loan_balance"]["cell_ref"] == "财务指标-汇总!K39 -> 财务指标-计算表!K76"
    assert contract_metrics["parent.loan_balance"]["golden_sample_ref"].endswith("#parent.loan_balance")


def test_ledger_pnl_service_wraps_financial_indicator_contract_as_non_formal_envelope():
    service = load_module(
        "backend.app.services.ledger_pnl_service",
        "backend/app/services/ledger_pnl_service.py",
    )

    envelope = service.ledger_pnl_formal_financial_indicator_contract_envelope(
        report_month="202603",
    )

    assert envelope["result_meta"]["basis"] == "ledger"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["source_version"] == "sv_formal_financial_indicators_excel_202603_contract"
    assert envelope["result"]["sample_id"] == "GS-LEDGER-PNL-FIN-IND-202603-B"
    metrics = _metrics_by_key(envelope["result"])
    assert metrics["group.operating_revenue"]["value"] is None
    assert metrics["group.operating_revenue"]["missing_reason"].startswith("正式财务指标来源未接入")
    assert metrics["parent.deposit_balance"]["source_status"] == "needs_reconciliation"
    assert metrics["parent.deposit_balance"]["value"] is None


def test_real_202603_qdb_algorithm_matches_golden_probe_without_promoting_formal_metrics():
    sample = _load_sample()
    service = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    source_dir = _real_qdb_gl_source_dir()

    envelope = service.qdb_gl_monthly_analysis_workbook_envelope(
        source_dir=str(source_dir),
        report_month="202603",
    )

    assert envelope["result_meta"]["basis"] == "analytical"
    assert envelope["result_meta"]["formal_use_allowed"] is False

    status_sheet = next(
        sheet
        for sheet in envelope["result"]["sheets"]
        if sheet["key"] == "financial_indicator_status"
    )
    rows_by_name = {row["指标"]: row for row in status_sheet["rows"]}
    for probe in sample["qdb_probe"]:
        row = rows_by_name[probe["status_row_name"]]
        assert Decimal(str(row["当前值"])) == Decimal(probe["system_value"])
        assert row["单位"] == probe["unit"]
        assert row["口径状态"] == "QDB源可复算"

    for metric in sample["formal_pending_status_probe"]:
        row = rows_by_name[metric["status_row_name"]]
        assert row["当前值"] is None
        assert row["口径状态"] == "正式口径待接入"
        assert str(row["口径来源"]).startswith("formal_pending:")


def test_real_202603_qdb_source_files_are_the_same_report_month_bound_by_sample():
    sample = _load_sample()
    source_dir = _real_qdb_gl_source_dir()

    avg_path = _real_month_source(source_dir, "日均", sample["report_month"])
    ledger_path = _real_month_source(source_dir, "总账对账", sample["report_month"])

    assert avg_path.name == sample["qdb_source_files"]["daily_average"]
    assert ledger_path.name == sample["qdb_source_files"]["general_ledger"]
