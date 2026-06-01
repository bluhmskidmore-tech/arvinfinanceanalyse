from __future__ import annotations

from tests.helpers import ROOT


DOCS_DIR = ROOT / "docs"


def _read_pnl_doc(name: str) -> str:
    return (DOCS_DIR / "pnl" / name).read_text(encoding="utf-8")


def test_product_category_remaining_blockers_do_not_relist_completed_p0_evidence():
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    completed = blocker_triage.split("## Completed cursor-safe P0 evidence", maxsplit=1)[1].split(
        "## Blockers that need user/product decision",
        maxsplit=1,
    )[0]
    next_tasks = blocker_triage.split("## Next cursor-safe tasks", maxsplit=1)[1]

    for required in (
        "readiness baseline",
        "headline sample metric assertions",
        "stale/fallback/refresh matrix skeleton",
        "Unit 5/7 surface ownership",
        "Unit 7 field-level edit policy",
        "Unit 10 page-to-helper traceability",
        "Unit 6 fixture-scoped UI-to-CSV parity",
        "Unit 9 GS-backed row/field matrix",
        "Unit 4 backend validation error-shape evidence",
        "governance regression tests",
    ):
        assert required in completed

    for stale_task in (
        "Evidence baseline + Unit 10 scenario assertions",
        "Unit 3 / Unit 8 state matrix skeleton",
        "Unit 5 / Unit 7 / Unit 10 documentation links",
        "Unit 7 field-level edit policy",
        "Unit 10 page-to-helper traceability",
        "Unit 8 stale/refresh cross-surface refinement",
        "Unit 9 fixture-driven row matrix",
        "Unit 6 UI-to-CSV every-cell comparison",
        "Unit 9 broader fixture expansion",
        "Unit 4 backend validation error-shape evidence",
        "Unit 10 traceability table expansion",
    ):
        assert stale_task not in next_tasks

    for decision_required_task in (
        "fallback-date semantics",
        "outward `as_of_date`",
        "detail `metric_id` expansion",
        "refresh timeout/stale copy",
        "Unit 4 extended validation copy",
        "dual-sort rationale",
        "revoke confirmation policy",
    ):
        assert decision_required_task in next_tasks


def test_product_category_unit4_backend_validation_error_shapes_are_documented():
    checklist = _read_pnl_doc("product-category-closure-checklist.md")
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    unit4 = checklist.split("## Unit 4: Manual Adjustment Create", maxsplit=1)[1].split(
        "## Unit 5: Manual Adjustment List",
        maxsplit=1,
    )[0]

    for required in (
        "`test_manual_adjustment_create_contract_returns_422_for_backend_validation_errors`",
        "missing all amount fields returns HTTP 422",
        '`loc: ["body"]`',
        '`type: "value_error"`',
        "`At least one adjustment value is required.`",
        'blank `account_code` returns `loc: ["body", "account_code"]` / `type: "string_too_short"`',
        'invalid `currency` returns `loc: ["body", "currency"]` / `type: "literal_error"`',
    ):
        assert required in unit4

    assert "Unit 4 backend validation error-shape evidence" not in blocker_triage.split(
        "## Next cursor-safe tasks",
        maxsplit=1,
    )[1]


def test_product_category_unit10_traceability_table_remains_non_exhaustive():
    checklist = _read_pnl_doc("product-category-closure-checklist.md")
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    traceability = checklist.split("### Unit 10 page-to-helper traceability", maxsplit=1)[1].split(
        "- Why not `CLOSED`:",
        maxsplit=1,
    )[0]

    for required in (
        "This table links already-covered page assertions to pure helpers; it is not an exhaustive per-field proof.",
        "`Unit 1: first report_dates entry drives baseline PnL, manual adjustments list, and ledger link`",
        "`nextDefaultReportDateIfUnset`; `buildLedgerPnlHrefForReportDate`",
        "`Unit 2: formal detail table renders frozen backend fields in column order without metric_id invention`",
        "`selectProductCategoryDetailRows`; `PRODUCT_CATEGORY_MAIN_PAGE_VIEWS`; `PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS`",
        "`Unit 3: refresh shows in-flight status (queued",
        "`runPollingTask`; `formatProductCategoryRefreshStatusLine`",
        "`Unit 9: table",
        "`formatProductCategoryRowDisplayValue`; `formatProductCategoryYieldValue`; `selectDisplayedProductCategoryGrandTotal`",
        "`surfaces degraded result_meta",
        "`PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY`; `collectProductCategoryGovernanceNotices`; `formatProductCategoryDualMetaDistinctLine`",
        "`keeps current and event sort controls independent and resets pagination on time-range apply/reset`",
        "`CURRENT_QUERY_FILTER_KEYS`; `EVENT_QUERY_FILTER_KEYS`; `didFiltersChange`",
        "`CSV export uses the same applied filter+sort as the list request (omits only pagination options)`",
        "`buildProductCategoryAuditListExportQuery`",
        "`Unit 6: a rendered audit row stays consistent with the exported CSV row for the same fixture`",
        "`buildProductCategoryAuditListExportQuery`; `downloadAuditCsv`",
        "`freezes the Unit 9 fixture-driven row/field matrix for asset, liability, and grand_total authority`",
        "`selectProductCategoryDetailRows`; `formatProductCategoryRowDisplayValue`; `formatProductCategoryYieldValue`; `selectDisplayedProductCategoryGrandTotal`",
    ):
        assert required in traceability

    assert "Unit 10 page-to-helper traceability" not in blocker_triage.split(
        "## Next cursor-safe tasks",
        maxsplit=1,
    )[1]
    assert "Unit 10 traceability table expansion" not in blocker_triage.split(
        "## Next cursor-safe tasks",
        maxsplit=1,
    )[1]


def test_product_category_unit9_fixture_row_matrix_stays_narrow():
    checklist = _read_pnl_doc("product-category-closure-checklist.md")
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    unit9 = checklist.split("### Unit 9 fixture-driven row matrix", maxsplit=1)[1].split(
        "- Why not `CLOSED`:",
        maxsplit=1,
    )[0]

    for required in (
        "This matrix documents only rows already exercised by page/model tests; it does not infer broader category catalog behavior.",
        "`repo_liabilities`",
        "liability row",
        "absolute display for `business_net_income`; yield is not money-scaled",
        "`repo_assets`",
        "asset row",
        "signed display for `business_net_income`; yield is not money-scaled",
        "`grand_total`",
        "footer-only total",
        "not rendered in table body; total uses backend grand total",
    ):
        assert required in unit9

    assert "Unit 9 fixture-driven row matrix" not in blocker_triage.split(
        "## Next cursor-safe tasks",
        maxsplit=1,
    )[1]


def test_product_category_unit6_csv_scope_note_does_not_overclaim():
    checklist = _read_pnl_doc("product-category-closure-checklist.md")
    blocker_triage = _read_pnl_doc("product-category-remaining-blockers.md")

    unit6 = checklist.split("### Unit 6 CSV precision scope note", maxsplit=1)[1].split(
        "- **BOM policy",
        maxsplit=1,
    )[0]

    for required in (
        "This note documents exactly what existing tests prove; it does not claim every-cell UI/CSV parity.",
        "query symmetry",
        "`CSV export uses the same applied filter+sort as the list request (omits only pagination options)`",
        "API CSV string pass-through",
        "`Unit 6: export pipes API CSV into the download Blob without rewriting numbers or a BOM`",
        "real-mode client pass-through",
        "`uses real mode to export filtered product-category manual adjustments as csv`",
        "Not proved here: backend BOM policy, large-export limits, streaming behavior, or rendered UI money strings equaling every CSV cell.",
    ):
        assert required in unit6

    assert "Unit 6 CSV precision scope note" not in blocker_triage.split(
        "## Next cursor-safe tasks",
        maxsplit=1,
    )[1]
