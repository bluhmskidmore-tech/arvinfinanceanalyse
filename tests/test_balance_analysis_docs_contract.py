from __future__ import annotations

from pathlib import Path

from tests.helpers import ROOT


def _read_doc(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_balance_analysis_spec_mentions_registered_runtime_path():
    spec = _read_doc("docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md")

    assert "backend/app/core_finance/module_registry.py" in spec
    assert "backend/app/tasks/formal_compute_runtime.py" in spec
    assert "backend/app/services/formal_result_runtime.py" in spec
    assert "API 路由保持显式定义" in spec
    assert "不因为模块注册而自动暴露新路由" in spec


def test_cache_spec_mentions_balance_analysis_basis_scoped_runtime_identity():
    cache_spec = _read_doc("docs/CACHE_SPEC.md")

    assert "balance_analysis:materialize:formal" in cache_spec
    assert "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1" in cache_spec
    assert "不自动推广为其他 formal module 的默认公开接口" in cache_spec


def test_acceptance_tests_track_registry_runtime_and_result_meta_contract_regressions():
    acceptance = _read_doc("docs/acceptance_tests.md")

    assert "tests/test_formal_compute_module_registry.py" in acceptance
    assert "tests/test_formal_compute_runtime_contract.py" in acceptance
    assert "tests/test_formal_compute_result_meta_contract.py" in acceptance
    assert "不构成放宽架构约束的授权" in acceptance
    assert "不得把 snapshot 直读或更多未落地能力写成已完成" in acceptance


def test_balance_analysis_docs_distinguish_supported_workbook_sections_from_future_gap_sections():
    spec = _read_doc("docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md")
    reconciliation = _read_doc("docs/BALANCE_ANALYSIS_RECONCILIATION_2026-03-01.md")

    assert "当前 governed workbook 已支持的 section keys" in spec
    assert "`bond_business_types`" in spec
    assert "`maturity_gap`" in spec
    assert "`currency_split`" in spec
    assert "`cashflow_calendar`" in spec
    assert "`issuer_concentration`" in spec
    assert "`account_category_comparison`" in spec
    assert "`ifrs9_classification`" in spec
    assert "`rule_reference`" in spec
    assert "`regulatory_limits`" in spec
    assert "`portfolio_comparison`" in spec
    assert "当前尚未纳入 governed workbook 的 section keys" in spec
    assert "`advanced_attribution_bundle`" in spec

    assert "当前对账结论仅覆盖当前 governed workbook 已支持的 section" in reconciliation
    assert "不等于 `资产负债分析_20260301_4.xlsx` 全量 1:1 对齐完成" in reconciliation


def test_data_contracts_record_account_category_as_formal_zqtz_balance_field():
    contracts = _read_doc("docs/data_contracts.md")

    assert "### 4.3 fact_formal_zqtz_balance_daily" in contracts
    assert "- `account_category`" in contracts
    assert "- `overdue_principal_days`" in contracts
    assert "- `value_date`" in contracts


def test_balance_analysis_advanced_attribution_boundary_design_note_exists():
    doc = _read_doc("docs/plans/2026-04-12-balance-analysis-advanced-attribution-boundary.md")

    assert "advanced_attribution_bundle" in doc
    assert "bond_analytics_service" in doc
    assert "roll_down" in doc


def test_fx_source_runbook_freezes_official_drop_contract_and_standard_entrypoint():
    runbook = _read_doc("docs/BALANCE_ANALYSIS_FX_SOURCE_RUNBOOK.md")
    env_example = _read_doc("config/.env.example")

    assert "data_input/fx/fx_daily_mid.csv" in runbook
    assert "data_input/fx_daily_mid.csv" in runbook
    assert "trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward" in runbook
    assert "MOSS_FX_OFFICIAL_SOURCE_PATH" in runbook
    assert "MOSS_FX_OFFICIAL_SOURCE_PATH=" in env_example
    assert "python -m backend.app.tasks.formal_balance_pipeline" in runbook
    assert "raw official non-CSV sample" in runbook
