from __future__ import annotations

import json
import re

from tests.helpers import ROOT
from tests.test_golden_samples_capture_ready import CAPTURE_READY_CASES


DOCS_DIR = ROOT / "docs"
GOLDEN_ROOT = ROOT / "tests" / "golden_samples"
SAMPLE_ID_RE = re.compile(r"\bGS-[A-Z0-9-]+\b")


def _read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def _read_pnl_doc(name: str) -> str:
    return (DOCS_DIR / "pnl" / name).read_text(encoding="utf-8")


def _read_root_file(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _page_contract_section(current_heading: str, next_heading: str) -> str:
    page_contracts = _read_doc("page_contracts.md")
    return page_contracts.split(current_heading, maxsplit=1)[1].split(next_heading, maxsplit=1)[0]


def _sample_dirs() -> list[str]:
    return sorted(
        path.name
        for path in GOLDEN_ROOT.iterdir()
        if path.is_dir() and path.name.startswith("GS-")
    )


def _metric_dictionary_capture_ready_sample_ids() -> list[str]:
    metric_dictionary = _read_doc("metric_dictionary.md")
    section = metric_dictionary.split("### 12.4 Capture-ready `sample_scope` 绑定", maxsplit=1)[1].split(
        "### 12.5",
        maxsplit=1,
    )[0]
    return sorted({sample_id for sample_id in SAMPLE_ID_RE.findall(section)})


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


def test_spec_harness_governance_index_is_supporting_and_mcp_aligned():
    readme = _read_doc("README.md")
    index = _read_doc("SPEC_HARNESS_GOVERNANCE_INDEX.md")
    mcp_runbook = _read_doc("MCP_RUNBOOK.md")
    mcp_config = json.loads(_read_root_file(".mcp.json"))

    assert "Status label: supporting" in index
    assert "non-authorizing" in index
    assert "`AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`" in index
    assert (
        "`docs/SPEC_HARNESS_GOVERNANCE_INDEX.md`: supporting Spec + Harness workflow index; "
        "non-authorizing and does not change the authority chain."
    ) in readme

    for heading in (
        "## Two-Layer Model",
        "## Standard Read Path",
        "## Harness Rules For AI Execution",
        "## Before-Editing Checklist",
        "## Completion Checklist",
        "## Page Maturity Matrix",
        "## Evidence Tool Map",
    ):
        assert heading in index

    for page_slug in ("`dashboard-home`", "`product-category-pnl`", "`market-data`"):
        assert page_slug in index

    for server_name in mcp_config["mcpServers"]:
        assert f"`{server_name}`" in mcp_runbook
        assert f"`{server_name}`" in index


def test_live_route_maturity_registry_is_supporting_and_authority_safe():
    registry = _read_doc("live_route_maturity.md")
    readme = _read_doc("README.md")

    assert "Status label: supporting" in registry
    assert "does not authorize new metric definitions" in registry
    assert "`docs/live_route_maturity.md`" in readme

    for required in (
        "`nav_state` mirrors navigation",
        "`maturity_tier` is one of",
        "`page_contract` must be an existing `PAGE-*` id or an explicit `GAP-*` marker",
        "`temporary-exception` rows must carry a real owner",
    ):
        assert required in registry


def test_operations_analysis_contract_matches_current_product_category_headline_binding():
    ops_contract = _page_contract_section("## 13.5 PAGE-OPS-001", "## 13.6 PAGE-BOND-001")
    metric_dictionary = _read_doc("metric_dictionary.md")

    for required in (
        "`client.getProductCategoryDates()` -> `GET /ui/pnl/product-category/dates`",
        "`client.getProductCategoryPnl()` -> `GET /ui/pnl/product-category`",
        "`MTR-PCP-001`",
        "`MTR-PCP-002`",
        "`MTR-PCP-003`",
        "`GS-PROD-CAT-PNL-A`",
        "`GAP-OPS-MACRO-FX`",
        "Current implementation primary first-screen formal PnL evidence",
        "Balance overview is supplemental topic-entry evidence",
        "does not create `MTR-OPS-*`",
    ):
        assert required in ops_contract

    assert "`PAGE-OPS-001` 已对齐当前 product-category headline 实现" in metric_dictionary
    assert "PAGE-OPS-001` 仍记录 balance overview + macro / FX strip，已与当前实现不一致" not in metric_dictionary


def test_ledger_pnl_candidate_metrics_bind_existing_page_contract_without_formal_promotion():
    ledger_contract = _page_contract_section(
        "## 14.0 PAGE-LEDGER-PNL-001",
        "## 14. PAGE-PROD-CAT-PNL-001",
    )
    metric_dictionary = _read_doc("metric_dictionary.md")

    for required in (
        "`MTR-LPN-001`",
        "`MTR-LPN-002`",
        "`MTR-LPN-003`",
        "candidate display metrics",
        "remain `pending_confirmation=true`",
    ):
        assert required in ledger_contract

    for metric_id in ("MTR-LPN-001", "MTR-LPN-002", "MTR-LPN-003"):
        metric_line = next(
            line for line in metric_dictionary.splitlines() if line.startswith(f"- `{metric_id}`")
        )
        assert "status=candidate" in metric_line
        assert "bound_page_id=PAGE-LEDGER-PNL-001" in metric_line
        assert "pending_confirmation=true" in metric_line

    assert (
        "| `ledger-pnl` | 新增 3 条 `candidate`：`MTR-LPN-001`~`MTR-LPN-003` | "
        "`PAGE-LEDGER-PNL-001` | `none` | live 只读链路已有独立 PAGE 合同；"
        "三条 summary 卡仍为 candidate，不能替代 formal PnL 或 product-category PnL |"
    ) in metric_dictionary
    assert "PAGE-CONTRACT-PENDING:/ledger-pnl" not in metric_dictionary


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
        file_names = {path.name for path in sample_dir.iterdir() if path.is_file()}
        allowed_companion_files = {"scenario.request.json"} if sample_id == "GS-PROD-CAT-PNL-A" else set()
        assert required_files <= file_names
        assert file_names <= required_files | allowed_companion_files


def test_capture_ready_sample_count_stays_in_sync_across_docs_and_gate():
    sample_dirs = _sample_dirs()
    actual_count = len(sample_dirs)
    metric_dictionary_sample_ids = _metric_dictionary_capture_ready_sample_ids()
    golden_plan = _read_doc("golden_sample_plan.md")
    golden_catalog = _read_doc("golden_sample_catalog.md")
    metric_dictionary = _read_doc("metric_dictionary.md")
    golden_samples_readme = (GOLDEN_ROOT / "README.md").read_text(encoding="utf-8")

    assert actual_count == 13
    assert len(CAPTURE_READY_CASES) == actual_count
    assert metric_dictionary_sample_ids == sample_dirs

    assert f"`tests/golden_samples/` 已经存在 **{actual_count}** 个样本包" in golden_plan
    assert f"与 `tests/test_golden_samples_capture_ready.py` 中注册的 {actual_count} 个 `sample_id` 对齐" in golden_catalog
    assert f"覆盖当前 {actual_count} 个 capture-ready 样本包。" in metric_dictionary
    assert f"Current capture-ready sample packs ({actual_count} total):" in golden_samples_readme


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
        "three P0 headline metrics are active in `docs/metric_dictionary.md`",
        "decision 3C (2026-05-11) approves expanding detail rows into formal metrics for scale, FTP, net income, and yield fields",
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
        "This is a page-level field freeze for detail semantics. It is also the starting field set for the 2026-05-11 detail-metric expansion decision",
        "do not invent detail `metric_id` numbers from this table; add the approved field matrix and dictionary rows first",
        "do not treat liability sign normalization as backend truth",
        "do not use `available_views` to add first-screen controls",
        "do not recompute `grand_total` in frontend",
        "do not change row identity during scenario display",
    ):
        assert rule in field_freeze


def test_product_category_p0_closure_gate_stays_decision_safe():
    page_contract = _read_pnl_doc("product-category-page-truth-contract.md")
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    p0_gate = page_contract.split("## 15. P0 Closure Gate", maxsplit=1)[1]

    for required in (
        "P0 is a closure gate, not a new feature lane.",
        "P0-approved active formal metric ids are currently `MTR-PCP-001`, `MTR-PCP-002`, and `MTR-PCP-003`.",
        "detail `metric_id` expansion is approved directionally by decision 3C",
        "standalone outward `as_of_date` is a no-field product/API decision for this page",
        "do not add additional `MTR-*` rows for product-category fields from sample evidence alone",
        "do not infer `as_of_date` from `report_date` or `generated_at`",
        "P0 evidence can lock known stale/fallback behavior, but cannot choose unresolved product copy or API shape",
    ):
        assert required in p0_gate

    for required in (
        "## P0 execution boundary",
        "Decision-required P0 items",
        "Cursor-safe P0 items",
        "`MTR-PCP-001`",
        "detail metric expansion",
        "1B no standalone `as_of_date`",
        "stale/fallback/refresh matrix",
    ):
        assert required in blocker_triage


def test_product_category_metric_dictionary_does_not_promote_unapproved_fields():
    metric_dictionary = _read_doc("metric_dictionary.md")

    assert "Product-category metric promotion guard" in metric_dictionary
    assert "GS-PROD-CAT-PNL-A" in metric_dictionary
    assert "MTR-PCP-001" in metric_dictionary
    assert "MTR-PCP-002" in metric_dictionary
    assert "MTR-PCP-003" in metric_dictionary
    assert "category_id / side / view / report_date are dimensions, not separate metrics" in metric_dictionary
    assert "scenario outputs remain analytical scenario payloads, not formal dictionary metrics" in metric_dictionary

    forbidden_promotions = (
        "| `MTR-PROD",
        "| `MTR-PCA",
        "| `MTR-PCP-101",
        "| `MTR-PCP-201",
    )
    for forbidden in forbidden_promotions:
        assert forbidden not in metric_dictionary

    for field_name in (
        "`business_net_income`",
        "`weighted_yield`",
        "`cnx_scale`",
    ):
        assert field_name in metric_dictionary


def test_market_data_page_contract_documents_blocked_formal_use_visibility():
    page_contracts = _read_doc("page_contracts.md")
    market_section = page_contracts.split("## 13.8 PAGE-MKT-001", maxsplit=1)[1].split(
        "## 13.9",
        maxsplit=1,
    )[0]

    for required in (
        "`formal_use_allowed=false`",
        "`formal · blocked`",
        "`禁止作为正式口径`",
        "`分析/候选`",
        "`frontend/src/features/market-data/pages/marketDataPageModel.ts`",
        "`frontend/src/features/market-data/pages/MarketDataPage.tsx`",
        "`frontend/src/test/MarketDataPage.test.tsx`",
        "`frontend/src/features/market-data/pages/marketDataPageModel.test.ts`",
    ):
        assert required in market_section


def test_macro_toolkit_page_contract_closes_tooling_route_without_metric_promotion():
    macro_contract = _page_contract_section(
        "## 13.9 PAGE-MACRO-TOOLKIT-001",
        "## 14.0 PAGE-LEDGER-PNL-001",
    )
    metric_dictionary = _read_doc("metric_dictionary.md")
    maturity_registry = _read_doc("live_route_maturity.md")

    for required in (
        "页面 ID：`PAGE-MACRO-TOOLKIT-001`",
        "路由：前端 `/macro-toolkit`",
        "`MacroToolkitContractBoundary`",
        "`formal_use_allowed=false`",
        "`非正式口径`",
        "`GET /ui/macro/toolkit/analysis?detail=core`",
        "`GET /ui/macro/toolkit/analysis/strategy-summaries`",
        "`GET /ui/macro/toolkit/scripts`",
        "`POST /ui/macro/toolkit/scripts/{name}/run`",
        "`POST /ui/macro/toolkit/cffex-member-rank/refresh`",
        "`POST /ui/macro/toolkit/choice-stock/refresh`",
        "不新增 `MTR-MACRO-*`",
        "`frontend/src/test/MacroToolkitPage.test.tsx`",
        "`tests/test_macro_toolkit_scripts.py`",
    ):
        assert required in macro_contract

    assert (
        "| `/macro-toolkit` | `PAGE-MACRO-TOOLKIT-001` | "
        "`MacroToolkitPage.tsx` -> `getMacroToolkitAnalysis` / "
        "`getMacroToolkitStrategySummaries` / `getMacroToolkitScripts` | "
        "**无 `MTR-*`**：工具/分析口径，不升格为正式指标 | — | "
        "`frontend/src/test/MacroToolkitPage.test.tsx`；`tests/test_macro_toolkit_scripts.py` |"
    ) in metric_dictionary
    assert "`macro-toolkit`: 页面已有 `PAGE-MACRO-TOOLKIT-001`" in metric_dictionary
    assert "GAP-MACRO-TOOLKIT-PAGE" not in maturity_registry
    assert (
        "| `/macro-toolkit` | live | candidate | PAGE-MACRO-TOOLKIT-001 |"
    ) in maturity_registry


def test_product_category_as_of_date_decision_has_no_standalone_field():
    page_contract = _read_pnl_doc("product-category-page-truth-contract.md")

    time_semantics = page_contract.split("## 10. Time Semantics", maxsplit=1)[1].split(
        "## 11. Result Meta Visibility",
        maxsplit=1,
    )[0]

    for required in (
        "`requested_report_date`: user-requested report date",
        "`resolved_report_date`: backend-returned report date",
        "`as_of_date`: intentionally not a standalone outward field for product-category PnL",
        "`generated_at`: system generation timestamp",
        "Decision 1B (2026-05-11): do not add a standalone outward `as_of_date` field for this page.",
        "must not present either as a replacement `as_of_date`",
    ):
        assert required in time_semantics


def test_product_category_manual_adjustment_surface_ownership_is_bounded():
    page_contract = _read_pnl_doc("product-category-page-truth-contract.md")
    checklist = _read_pnl_doc("product-category-closure-checklist.md")
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    surface_section = page_contract.split("### 9.3 Manual Adjustment Surface Ownership", maxsplit=1)[
        1
    ].split("## 10. Time Semantics", maxsplit=1)[0]

    for required in (
        "This section documents existing tested surfaces; it does not add lifecycle friction or change endpoint policy.",
        "`/product-category-pnl`: canonical first-screen summary and quick-action surface.",
        "`/product-category-pnl/audit`: canonical full audit surface for current-state list, event timeline, filters, dual sort, pagination, retry, and CSV export.",
        "Full event-timeline evidence belongs to the audit page; the main page may show only a summary count and audit link.",
        "Lifecycle actions (`edit`, `revoke`, `restore`) are allowed on both surfaces only as already tested; the source-of-truth behavior is the shared manual-adjustment API plus PnL refresh path.",
        "No confirmation modal, dual-sort rationale, or export policy is approved by this surface note.",
    ):
        assert required in surface_section

    for required in (
        "surface ownership is frozen in `docs/pnl/product-category-page-truth-contract.md` section 9.3",
        "Unit 5/7 surface cross-link note is now recorded",
    ):
        assert required in checklist or required in blocker_triage


def test_product_category_p0_metric_approval_is_consistent_across_docs():
    metric_dictionary = _read_doc("metric_dictionary.md")
    page_contracts = _read_doc("page_contracts.md")
    readiness = _read_pnl_doc("product-category-development-data-readiness.md")

    for doc in (metric_dictionary, page_contracts, readiness):
        assert "MTR-PCP-001" in doc
        assert "MTR-PCP-002" in doc
        assert "MTR-PCP-003" in doc

    for stale_statement in (
        "formal product-category `metric_id` approval is still missing",
        "本页 `metric_id` 主表绑定**尚未**在 `docs/metric_dictionary.md` 中完备案",
        "产品分类 PnL 只有页面 truth contract 与样本 truth；正式字典级 `metric_id` 待审批后再补。",
        "对 `GS-PROD-CAT-PNL-A` 另走业务审批，批准后再补字典级 `metric_id`",
        "Field-level truth only; no approved `metric_id` freeze",
        "Explicitly forbids inventing product-category metric IDs before approval",
    ):
        assert stale_statement not in "\n".join((metric_dictionary, page_contracts, readiness))

    for required in (
        "P0 keeps only `MTR-PCP-001`, `MTR-PCP-002`, and `MTR-PCP-003` active; decision 3C approves detail expansion directionally pending matrix / numbering / tests.",
        "Decision 3C approves detail metric expansion directionally, but only the three headline product-category metrics are dictionary-active until the detail field matrix, numbering, dictionary rows, and tests land.",
        "Keep `GS-PROD-CAT-PNL-A` bound to the three headline `MTR-PCP-*` metrics and carry decision 3C into a detail field matrix before adding any new detail `MTR-PCP-*` rows.",
    ):
        assert required in "\n".join((metric_dictionary, page_contracts, readiness))


def test_product_category_manual_adjustment_edit_policy_is_documented_without_new_friction():
    page_contract = _read_pnl_doc("product-category-page-truth-contract.md")
    checklist = _read_pnl_doc("product-category-closure-checklist.md")
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    edit_policy = page_contract.split("### 9.4 Manual Adjustment Edit Field Policy", maxsplit=1)[
        1
    ].split("## 10. Time Semantics", maxsplit=1)[0]

    for required in (
        "This is a documentation freeze of existing tested behavior, not a new product approval.",
        "`report_date` is carried from the selected/current row and stays read-only in the form.",
        "`operator`, `approval_status`, `account_code`, `currency`, `account_name`, `beginning_balance`, `ending_balance`, `monthly_pnl`, `daily_avg_balance`, and `annual_avg_balance` are the current editable draft fields.",
        "`approval_status` controls revoke/restore availability only as already tested: approved -> revoke enabled, pending -> neither, rejected -> restore enabled.",
        "Edit remains enabled for approved, pending, and rejected rows in the existing tests; do not infer this as final product policy for every edge case.",
        "No confirmation modal or additional revoke friction is approved here.",
    ):
        assert required in edit_policy

    assert "field-level edit policy is now documented" in checklist
    assert "Unit 7 field-level edit policy" not in blocker_triage.split("## Next cursor-safe tasks", maxsplit=1)[1]


def test_product_category_stale_refresh_cross_surface_matrix_is_evidence_only():
    page_contract = _read_pnl_doc("product-category-page-truth-contract.md")
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    matrix = page_contract.split("### 11.2 Evidence-Only Cross-Surface State Matrix", maxsplit=1)[
        1
    ].split("## 12. Minimum Reconciliation Rules", maxsplit=1)[0]

    for required in (
        "This matrix records only states already covered by tests plus the 2026-05-11 no-silent-date-switch / no-standalone-as_of_date decisions; it does not define timeout copy.",
        "`/product-category-pnl` formal table",
        "`Unit 9: formal baseline refetch failure shows AsyncSection error; no stale table, summary, or footer`",
        "`/product-category-pnl` refresh control",
        "`Unit 3: refresh shows in-flight status (queued",
        "`surfaces refresh conflict (409) with explicit copy",
        "`surfaces sync-fallback service failure (503) with explicit copy",
        "`surfaces terminal failed refresh status as an error (not silent success)`",
        "`/product-category-pnl/audit` list/timeline",
        "`Unit 5: list/timeline failure surfaces AsyncSection error, hides current+event bodies, and retry refetches`",
        "`GET /ui/pnl/product-category` backend detail",
        "`test_product_category_detail_returns_503_when_read_model_is_locked`",
    ):
        assert required in matrix

    assert "Unit 8 stale/refresh cross-surface refinement" not in blocker_triage.split(
        "## Next cursor-safe tasks",
        maxsplit=1,
    )[1]
