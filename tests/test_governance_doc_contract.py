from __future__ import annotations

from pathlib import Path

from tests.helpers import ROOT


DOCS_DIR = ROOT / "docs"
GOLDEN_ROOT = ROOT / "tests" / "golden_samples"


def _read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def _sample_dirs() -> list[str]:
    return sorted(
        path.name
        for path in GOLDEN_ROOT.iterdir()
        if path.is_dir() and path.name.startswith("GS-")
    )


def test_governance_doc_pack_exists_with_required_sections():
    system_gap = _read_doc("system_gap_plan.md")
    metric_template = _read_doc("metric_dictionary_template.md")
    page_template = _read_doc("page_contract_template.md")
    golden_plan = _read_doc("golden_sample_plan.md")

    for heading in (
        "## 4.1 业务指标口径",
        "## 4.2 API / DTO / 前后端契约",
        "## 4.3 页面级产品定义与信息架构",
        "## 4.4 前端设计系统与数值展示规范",
        "## 4.5 数据质量、追溯、as_of_date、fallback 可见性",
        "## 4.6 对账与黄金样本",
        "## 4.7 自动化回归测试",
        "## 4.8 监控、日志、错误追踪",
        "## 4.9 文档与交接",
        "## 5. 未来两周最小可执行路线图",
    ):
        assert heading in system_gap

    for token in (
        "### H. 时间与 freshness",
        "### I. 数据质量与 fallback",
        "### K. 黄金样本与测试",
        "`metric_id`",
        "`sample_id`",
    ):
        assert token in metric_template

    for token in (
        "## H. freshness / 数据质量 / fallback 可见性",
        "## J. 黄金样本与对账",
        "## 4. 页面契约检查清单",
        "`page_id`",
        "`metric_id`",
    ):
        assert token in page_template

    for token in (
        "## 4. 当前 Batch A 覆盖范围",
        "## 5. 当前明确不纳入首批的面",
        "## 9. 与 release gate 的关系",
        "`tests/test_golden_samples_capture_ready.py`",
    ):
        assert token in golden_plan


def test_metric_dictionary_and_page_contracts_cover_current_governed_scope():
    metric_dictionary = _read_doc("metric_dictionary.md")
    page_contracts = _read_doc("page_contracts.md")

    for metric_id in (
        "MTR-BAL-001",
        "MTR-PNL-005",
        "MTR-BRG-011",
        "MTR-RSK-001",
        "MTR-EXEC-001",
        "MTR-PAT-001",
    ):
        assert metric_id in metric_dictionary

    for page_id in (
        "PAGE-DASH-001",
        "PAGE-BALANCE-001",
        "PAGE-PNL-001",
        "PAGE-BRIDGE-001",
        "PAGE-RISK-001",
        "PAGE-EXEC-OVERVIEW-001",
        "PAGE-EXEC-SUMMARY-001",
        "PAGE-EXEC-PNL-ATTR-001",
        "PAGE-PNL-ATTR-WB-001",
    ):
        assert page_id in page_contracts


def test_golden_sample_docs_match_current_sample_directories():
    golden_plan = _read_doc("golden_sample_plan.md")
    golden_catalog = _read_doc("golden_sample_catalog.md")
    sample_dirs = _sample_dirs()

    assert sample_dirs, "expected at least one golden sample directory"

    for sample_id in sample_dirs:
        assert sample_id in golden_plan
        assert sample_id in golden_catalog

    assert "GS-BOND-HEADLINE-A" in golden_plan
    assert "GS-BOND-HEADLINE-A" in golden_catalog


def test_golden_sample_dirs_keep_required_four_file_structure():
    required_files = {"request.json", "response.json", "assertions.md", "approval.md"}

    for sample_id in _sample_dirs():
        sample_dir = GOLDEN_ROOT / sample_id
        assert {path.name for path in sample_dir.iterdir() if path.is_file()} == required_files


def test_page_contracts_bind_sample_backed_governed_pages_to_golden_samples():
    page_contracts = _read_doc("page_contracts.md")

    for sample_id in (
        "GS-BAL-OVERVIEW-A",
        "GS-BAL-WORKBOOK-A",
        "GS-PNL-OVERVIEW-A",
        "GS-PNL-DATA-A",
        "GS-BRIDGE-A",
        "GS-RISK-A",
        "GS-EXEC-OVERVIEW-A",
        "GS-EXEC-SUMMARY-A",
        "GS-EXEC-PNL-ATTR-A",
    ):
        assert sample_id in page_contracts
