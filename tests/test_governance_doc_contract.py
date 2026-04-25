from __future__ import annotations


from tests.helpers import ROOT


DOCS_DIR = ROOT / "docs"
GOLDEN_ROOT = ROOT / "tests" / "golden_samples"


def _read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def _read_pnl_doc(name: str) -> str:
    return (DOCS_DIR / "pnl" / name).read_text(encoding="utf-8")


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
    product_category_page_contract = _read_pnl_doc("product-category-page-truth-contract.md")

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

    assert "PAGE-PROD-CAT-001" in product_category_page_contract


def test_golden_sample_docs_match_current_sample_directories():
    golden_plan = _read_doc("golden_sample_plan.md")
    golden_catalog = _read_doc("golden_sample_catalog.md")
    product_category_sample_doc = _read_pnl_doc("product-category-golden-sample-a.md")
    sample_dirs = _sample_dirs()

    assert sample_dirs, "expected at least one golden sample directory"

    for sample_id in sample_dirs:
        if sample_id == "GS-PROD-CAT-PNL-A":
            assert sample_id in product_category_sample_doc
            continue
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
    product_category_page_contract = _read_pnl_doc("product-category-page-truth-contract.md")

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

    assert "GS-PROD-CAT-PNL-A" in product_category_page_contract


def test_product_category_closure_checklist_is_ascii_and_unit_scoped():
    checklist = _read_pnl_doc("product-category-closure-checklist.md")

    assert checklist.isascii()
    for state in ("CLOSED", "PARTIAL", "NOT_TRUSTED", "EXCLUDED"):
        assert f"`{state}`" in checklist
    for forbidden in ("\U00002705", "\U0001f7e1", "\U0001f534", "\U00002b1c"):
        assert forbidden not in checklist

    matrix_rows = [
        line
        for line in checklist.splitlines()
        if any(line.startswith(f"| {index}. ") for index in range(1, 11))
    ]
    unit_headings = [
        line
        for line in checklist.splitlines()
        if line.startswith("## Unit ")
    ]

    assert len(matrix_rows) == 10
    assert len(unit_headings) == 10
    assert "- `PARTIAL`: 10" in checklist

    for required in (
        "Future product-category-pnl work must start from this checklist, not from a broad page rewrite.",
        "pick exactly one unit before editing code",
        "read that unit's `Why not CLOSED` list first",
        "do not change `PARTIAL` to `CLOSED` until every blocker for that unit is removed or reclassified with evidence",
        "after changing a status, update the status matrix, unit details, and targeted tests in the same change",
    ):
        assert required in checklist


def test_product_category_detail_unit_stays_partial_until_closure_evidence_exists():
    checklist = _read_pnl_doc("product-category-closure-checklist.md")
    page_contract = _read_pnl_doc("product-category-page-truth-contract.md")

    assert "| 2. Detail | `PARTIAL` | `P0` |" in checklist
    unit_2 = checklist.split("## Unit 2: Detail", maxsplit=1)[1].split("## Unit 3:", maxsplit=1)[0]
    boundary_section = page_contract.split("## 6. Page Basis and Boundaries", maxsplit=1)[1].split(
        "## 7. Row Authority",
        maxsplit=1,
    )[0]

    for required in (
        "- Main page view selector:",
        "  - `monthly`",
        "  - `ytd`",
        "`qtd` and `year_to_report_month_end` are governed API/detail sample surfaces, not current first-screen UI requirements.",
    ):
        assert required in boundary_section

    for required in (
        "the main page selector scope is explicitly frozen as `monthly` and `ytd`",
        "`qtd` and `year_to_report_month_end` are governed API/detail sample surfaces, not current first-screen UI requirements",
        "first-stage field freeze exists in `docs/pnl/product-category-page-truth-contract.md` section 9.1",
        "formal `metric_id` approval is still missing",
        "core detail row/scenario/view-scope semantics now have isolated selector tests, but full field freeze and exhaustive detail semantics remain partially covered by page tests only",
        "productCategoryPnlPageModel.test.ts",
    ):
        assert required in unit_2

    assert "the page UI itself currently exposes `monthly` and `ytd`, but not the full four-view surface" not in unit_2


def test_product_category_first_stage_field_freeze_is_explicitly_bounded():
    page_contract = _read_pnl_doc("product-category-page-truth-contract.md")
    field_freeze = page_contract.split("### 9.1 First-Stage Field Freeze", maxsplit=1)[1].split(
        "## 10. Time Semantics",
        maxsplit=1,
    )[0]

    for field_path in (
        "`result.view`",
        "`result.available_views`",
        "`result.rows[].category_id`",
        "`result.rows[].side`",
        "`result.rows[].business_net_income`",
        "`result.asset_total.business_net_income`",
        "`result.liability_total.business_net_income`",
        "`result.grand_total.business_net_income`",
        "`result.scenario_rate_pct`",
        "`result_meta.basis`",
        "`result_meta.scenario_flag`",
    ):
        assert field_path in field_freeze

    for rule in (
        "This is a page-level field freeze, not a formal `metric_id` approval.",
        "do not invent `metric_id` bindings from this table",
        "do not treat liability sign normalization as backend truth",
        "do not use `available_views` to add first-screen controls",
        "do not recompute `grand_total` in frontend",
        "do not change row identity during scenario display",
    ):
        assert rule in field_freeze
