from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.core_finance.product_category_pnl import (
    CanonicalFactRow,
    calculate_read_model,
    calculate_product_category_interest_spread_metrics,
    calculate_product_category_liability_cost_decomposition,
)
from backend.app.core_finance.config.product_category_mapping import (
    build_default_product_category_config,
)

ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
CORE_FILE = BACKEND_APP / "core_finance" / "product_category_pnl.py"
SERVICE_FILE = BACKEND_APP / "services" / "product_category_pnl_service.py"
SOURCE_SERVICE_FILE = BACKEND_APP / "services" / "product_category_source_service.py"
ANALYSIS_ADAPTERS_FILE = BACKEND_APP / "services" / "analysis_adapters.py"
TASK_FILE = BACKEND_APP / "tasks" / "product_category_pnl.py"
PRODUCT_CATEGORY_REPO_FILE = BACKEND_APP / "repositories" / "product_category_pnl_repo.py"

PRODUCT_CATEGORY_FORMAL_HELPERS = (
    "derive_monthly_pnl",
    "apply_manual_adjustments",
    "calculate_read_model",
    "apply_scenario_to_rows",
    "calculate_product_category_liability_cost_decomposition",
    "_build_report_rows",
    "_scale_field",
    "_days_for_view",
    "_calculate_ftp",
    "_calculate_weighted_yield",
    "_build_product_category_bp_metric_value",
)

SERVICE_FORBIDDEN_SNIPPETS = (
    "business_net_income =",
    "weighted_yield =",
    "cny_net =",
    "foreign_net =",
    "cnx_cash =",
    "cny_cash =",
    "foreign_cash =",
    "ftp_rate =",
    "cash_field =",
    "sign = Decimal(",
    "_calculate_ftp(",
    "_calculate_weighted_yield(",
)


def test_product_category_formal_helpers_are_defined_only_in_core_finance():
    py_files = list(BACKEND_APP.rglob("*.py"))
    assert CORE_FILE.exists(), f"Missing governed core file: {CORE_FILE}"

    violations: list[str] = []
    for helper in PRODUCT_CATEGORY_FORMAL_HELPERS:
        pattern = re.compile(rf"^\s*def\s+{re.escape(helper)}\s*\(", re.MULTILINE)
        matching_files = []
        for path in py_files:
            if pattern.search(path.read_text(encoding="utf-8")):
                matching_files.append(path.relative_to(ROOT).as_posix())
        if matching_files != [CORE_FILE.relative_to(ROOT).as_posix()]:
            violations.append(f"{helper}: {matching_files}")

    assert not violations, (
        "Product-category formal helpers must be defined exactly once in "
        "backend/app/core_finance/product_category_pnl.py:\n" + "\n".join(violations)
    )


def test_product_category_service_remains_orchestration_only():
    text = SERVICE_FILE.read_text(encoding="utf-8")

    violations = [snippet for snippet in SERVICE_FORBIDDEN_SNIPPETS if snippet in text]
    assert not violations, (
        "product_category_pnl_service.py should orchestrate only, without formal "
        "finance calculations:\n" + "\n".join(violations)
    )
    assert "backend.app.core_finance.product_category_pnl" not in text


def test_only_allowed_services_touch_product_category_core_module():
    source_service_text = SOURCE_SERVICE_FILE.read_text(encoding="utf-8")
    analysis_adapters_text = ANALYSIS_ADAPTERS_FILE.read_text(encoding="utf-8")

    assert "backend.app.core_finance.product_category_pnl" in source_service_text
    assert "backend.app.core_finance.product_category_pnl" in analysis_adapters_text

    allowed_files = {
        CORE_FILE.relative_to(ROOT).as_posix(),
        SOURCE_SERVICE_FILE.relative_to(ROOT).as_posix(),
        ANALYSIS_ADAPTERS_FILE.relative_to(ROOT).as_posix(),
        (BACKEND_APP / "tasks" / "product_category_pnl.py").relative_to(ROOT).as_posix(),
    }
    violations: list[str] = []
    for path in BACKEND_APP.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if "backend.app.core_finance.product_category_pnl" in text and rel not in allowed_files:
            violations.append(rel)

    assert not violations, (
        "Unexpected product-category core_finance imports outside the approved "
        "orchestration path:\n" + "\n".join(violations)
    )


def test_product_category_task_does_not_materialize_duplicate_rows_into_scenario_read_model():
    text = TASK_FILE.read_text(encoding="utf-8")
    assert "_insert_rows" in text
    assert (
        '_insert_rows(\n                        conn,\n                        "product_category_pnl_scenario_read_model"'
        not in text
    ), "Formal rows must not be written to product_category_pnl_scenario_read_model"


def test_product_category_repo_queries_formal_read_model_only():
    text = PRODUCT_CATEGORY_REPO_FILE.read_text(encoding="utf-8")
    assert "from product_category_pnl_formal_read_model" in text
    assert "product_category_pnl_scenario_read_model" not in text


def test_product_category_adapter_documents_overlay_without_second_storage_path():
    text = ANALYSIS_ADAPTERS_FILE.read_text(encoding="utf-8")
    assert "apply_scenario_to_rows" in text
    assert "Single storage path" in text or "formal read model" in text


def test_product_category_weighted_yield_is_decimal_core_finance_output():
    report_date = date(2026, 1, 31)
    facts = [
        CanonicalFactRow(
            report_date=report_date,
            account_code="120",
            currency="CNX",
            account_name="asset scale",
            beginning_balance=Decimal("0"),
            ending_balance=Decimal("100000000"),
            monthly_pnl=Decimal("0"),
            daily_avg_balance=Decimal("100000000"),
            annual_avg_balance=Decimal("100000000"),
            days_in_period=31,
        ),
        CanonicalFactRow(
            report_date=report_date,
            account_code="50204000001",
            currency="CNX",
            account_name="asset pnl",
            beginning_balance=Decimal("0"),
            ending_balance=Decimal("0"),
            monthly_pnl=Decimal("849315.0684931506849315068493"),
            daily_avg_balance=Decimal("0"),
            annual_avg_balance=Decimal("0"),
            days_in_period=31,
        ),
    ]

    result = calculate_read_model(
        {report_date: facts},
        report_date,
        "monthly",
        build_default_product_category_config(),
    )
    lending = next(
        row for row in result["rows"] if row["category_id"] == "interbank_lending_assets"
    )

    assert lending["weighted_yield"] == Decimal("10.00000000000000000000000000")


def test_product_category_interest_spread_metrics_are_decimal_core_finance_output():
    metrics = calculate_product_category_interest_spread_metrics(
        report_date="2026-02-28",
        view="monthly",
        asset_row={
            "weighted_yield": Decimal("2.55"),
            "cnx_cash": Decimal("10"),
            "cnx_scale": Decimal("100"),
            "cny_cash": Decimal("0.23"),
            "cny_scale": Decimal("100"),
        },
        liability_row={
            "weighted_yield": Decimal("1.70"),
            "cnx_cash": Decimal("8"),
            "cnx_scale": Decimal("80"),
            "cny_cash": Decimal("0.11"),
            "cny_scale": Decimal("80"),
        },
    )

    assert metrics.all_currency_spread_pct is not None
    assert metrics.all_currency_spread_pct.raw == Decimal("0.85")
    assert metrics.all_currency_spread_pct.unit == "percent"
    assert metrics.all_currency_spread_pct.display == "0.85%"
    assert metrics.cny_spread_pct is not None
    assert metrics.cny_spread_pct.raw == Decimal("1.20580357")
    assert metrics.cny_spread_pct.unit == "percent"
    assert metrics.cny_spread_pct.display == "1.21%"


def test_product_category_interest_spread_metrics_preserve_null_when_inputs_missing():
    metrics = calculate_product_category_interest_spread_metrics(
        report_date="2026-02-28",
        view="monthly",
        asset_row={
            "weighted_yield": None,
            "cnx_cash": Decimal("10"),
            "cnx_scale": Decimal("100"),
            "cny_cash": Decimal("0"),
            "cny_scale": Decimal("0"),
        },
        liability_row={
            "weighted_yield": Decimal("1.70"),
            "cnx_cash": Decimal("8"),
            "cnx_scale": Decimal("80"),
            "cny_cash": Decimal("0.11"),
            "cny_scale": Decimal("80"),
        },
    )

    assert metrics.all_currency_spread_pct is None
    assert metrics.cny_spread_pct is None


# Certified liability-side inputs and CLN decomposition outputs, captured from the
# formal read model (see docs contract for the 2026-06-30 / 2026-07-31 sign-off).
LIABILITY_COST_DECOMPOSITION_CERTIFIED_CASES = (
    (
        "2026-06-30",
        "ytd",
        {
            "weighted_yield": Decimal("1.58812752"),
            "cnx_cash": Decimal("-1384392573.11000000"),
            "cnx_scale": Decimal("-175787577060.21204420"),
        },
        {
            "weighted_yield": Decimal("2.81427057"),
            "cnx_cash": Decimal("-27000446.32000000"),
            "cnx_scale": Decimal("-1934725622.00187845"),
        },
        {
            "liability_yield": ("1.58812752", "1.59%"),
            "liability_yield_ex_cln": ("1.57448235", "1.57%"),
            "cln_yield": ("2.81427057", "2.81%"),
            "cln_drag_bp": ("1.36451673", "1.4 bp"),
            "cln_drag_bp_rounded": "1.4",
            "cln_scale": "-1934725622.00187845",
        },
    ),
    (
        "2026-07-31",
        "ytd",
        {
            "weighted_yield": Decimal("1.57977226"),
            "cnx_cash": Decimal("-1613238850.09000000"),
            "cnx_scale": Decimal("-175817132324.90113208"),
        },
        {
            "weighted_yield": Decimal("2.79229043"),
            "cnx_cash": Decimal("-31581712.60000000"),
            "cnx_scale": Decimal("-1947296544.69391509"),
        },
        {
            "liability_yield": ("1.57977226", "1.58%"),
            "liability_yield_ex_cln": ("1.56619237", "1.57%"),
            "cln_yield": ("2.79229043", "2.79%"),
            "cln_drag_bp": ("1.35798856", "1.4 bp"),
            "cln_drag_bp_rounded": "1.4",
            "cln_scale": "-1947296544.69391509",
        },
    ),
    (
        "2026-07-31",
        "monthly",
        {
            "weighted_yield": Decimal("1.53104438"),
            "cnx_cash": Decimal("-228846276.98000000"),
            "cnx_scale": Decimal("-175989696934.86000000"),
        },
        {
            "weighted_yield": Decimal("2.66941468"),
            "cnx_cash": Decimal("-4581266.28000000"),
            "cnx_scale": Decimal("-2020694512.67000000"),
        },
        {
            "liability_yield": ("1.53104438", "1.53%"),
            "liability_yield_ex_cln": ("1.51782191", "1.52%"),
            "cln_yield": ("2.66941468", "2.67%"),
            "cln_drag_bp": ("1.32224661", "1.3 bp"),
            "cln_drag_bp_rounded": "1.3",
            "cln_scale": "-2020694512.67000000",
        },
    ),
)


@pytest.mark.parametrize(
    ("report_date", "view", "liability_row", "cln_row", "expected"),
    LIABILITY_COST_DECOMPOSITION_CERTIFIED_CASES,
    ids=["2026-06-30-ytd", "2026-07-31-ytd", "2026-07-31-monthly"],
)
def test_product_category_liability_cost_decomposition_matches_certified_values(
    report_date, view, liability_row, cln_row, expected
):
    decomposition = calculate_product_category_liability_cost_decomposition(
        report_date=report_date,
        view=view,
        liability_row=liability_row,
        credit_linked_notes_row=cln_row,
    )

    assert decomposition.liability_yield_pct is not None
    assert decomposition.liability_yield_pct.raw == Decimal(expected["liability_yield"][0])
    assert decomposition.liability_yield_pct.display == expected["liability_yield"][1]
    assert decomposition.liability_yield_pct.unit == "percent"

    assert decomposition.liability_yield_ex_cln_pct is not None
    assert decomposition.liability_yield_ex_cln_pct.raw == Decimal(
        expected["liability_yield_ex_cln"][0]
    )
    assert decomposition.liability_yield_ex_cln_pct.display == expected["liability_yield_ex_cln"][1]
    assert decomposition.liability_yield_ex_cln_pct.unit == "percent"

    assert decomposition.cln_yield_pct is not None
    assert decomposition.cln_yield_pct.raw == Decimal(expected["cln_yield"][0])
    assert decomposition.cln_yield_pct.display == expected["cln_yield"][1]
    assert decomposition.cln_yield_pct.unit == "percent"

    assert decomposition.cln_drag_bp is not None
    # The 8-decimal raw stays available for audit even though the display rounds hard.
    assert decomposition.cln_drag_bp.raw == Decimal(expected["cln_drag_bp"][0])
    assert decomposition.cln_drag_bp.display == expected["cln_drag_bp"][1]
    assert decomposition.cln_drag_bp.unit == "bp"
    # bp displays stop at 1 decimal: the percent rates they derive from only resolve to
    # 1bp, so a 2-decimal bp display would claim precision the inputs do not have.
    assert decomposition.cln_drag_bp.display == f"{expected['cln_drag_bp_rounded']} bp"
    assert str(decomposition.cln_drag_bp.raw.quantize(Decimal("0.1"))) == (
        expected["cln_drag_bp_rounded"]
    )
    # Lowercase, space-separated `bp`, matching the shared `Numeric` bp convention used by
    # bond analytics / executive / yield curve rather than the local `%` suffix style.
    assert decomposition.cln_drag_bp.display.endswith(" bp")
    assert len(decomposition.cln_drag_bp.display.removesuffix(" bp").split(".")[1]) == 1
    # Percent fields keep 2 decimals; the two units must not share a quantum.
    assert len(decomposition.liability_yield_pct.display.removesuffix("%").split(".")[1]) == 2

    assert decomposition.cln_scale == Decimal(expected["cln_scale"])


def test_product_category_liability_cost_decomposition_reuses_days_for_view_annualization():
    """The ex-CLN rate must come from the same days_for_view / 365 basis as weighted_yield."""
    liability_row = {
        "weighted_yield": Decimal("1.58812752"),
        "cnx_cash": Decimal("-1384392573.11000000"),
        "cnx_scale": Decimal("-175787577060.21204420"),
    }
    cln_row = {
        "weighted_yield": Decimal("2.81427057"),
        "cnx_cash": Decimal("-27000446.32000000"),
        "cnx_scale": Decimal("-1934725622.00187845"),
    }
    # 2026-01-01..2026-06-30 inclusive.
    days_for_view = Decimal("181")
    expected_ex_cln = (
        (liability_row["cnx_cash"] - cln_row["cnx_cash"])
        / days_for_view
        * Decimal("365")
        / (liability_row["cnx_scale"] - cln_row["cnx_scale"])
        * Decimal("100")
    ).quantize(Decimal("0.00000001"))

    decomposition = calculate_product_category_liability_cost_decomposition(
        report_date="2026-06-30",
        view="ytd",
        liability_row=liability_row,
        credit_linked_notes_row=cln_row,
    )

    assert decomposition.liability_yield_ex_cln_pct is not None
    assert decomposition.liability_yield_ex_cln_pct.raw == expected_ex_cln


def test_product_category_liability_cost_decomposition_negative_drag_display():
    """A CLN leg cheaper than the rest of the book must surface as a negative drag.

    Removing the cheap CLN leg raises the ex-CLN cost rate above the blended total,
    so drag = liability_yield - ex_cln_yield goes negative. The display keeps the
    shared bp convention (1 decimal, lowercase, space-separated) and renders the
    sign as the ASCII hyphen-minus (U+002D) that Decimal f-string formatting emits,
    matching the shared ``Numeric`` bp formatter in
    backend/app/schemas/common_numeric.py.
    """
    # days_for_view = 31 (monthly view of 2026-07-31). Scales are multiples of 365e6
    # so every rate is exact: ex-CLN 1.60%, CLN 1.30%, and with CLN at 1% of total
    # scale the blended total is 0.99 * 1.6 + 0.01 * 1.3 = 1.597% -> drag -0.3 bp.
    decomposition = calculate_product_category_liability_cost_decomposition(
        report_date="2026-07-31",
        view="monthly",
        liability_row={
            "weighted_yield": Decimal("1.597"),
            "cnx_cash": Decimal("-49507000"),
            "cnx_scale": Decimal("-36500000000"),
        },
        credit_linked_notes_row={
            "weighted_yield": Decimal("1.30"),
            "cnx_cash": Decimal("-403000"),
            "cnx_scale": Decimal("-365000000"),
        },
    )

    assert decomposition.liability_yield_ex_cln_pct is not None
    assert decomposition.liability_yield_ex_cln_pct.raw == Decimal("1.60000000")
    assert decomposition.cln_yield_pct is not None
    assert decomposition.cln_yield_pct.raw < decomposition.liability_yield_ex_cln_pct.raw

    assert decomposition.cln_drag_bp is not None
    assert decomposition.cln_drag_bp.raw == Decimal("-0.30000000")
    assert decomposition.cln_drag_bp.raw < 0
    assert decomposition.cln_drag_bp.unit == "bp"
    assert decomposition.cln_drag_bp.display == "-0.3 bp"
    # Sign symbol pinned to ASCII hyphen-minus; the typographic minus must not appear.
    assert decomposition.cln_drag_bp.display[0] == "\u002d"
    assert "\u2212" not in decomposition.cln_drag_bp.display


def test_product_category_liability_cost_decomposition_returns_none_when_cln_row_missing():
    decomposition = calculate_product_category_liability_cost_decomposition(
        report_date="2026-06-30",
        view="ytd",
        liability_row={
            "weighted_yield": Decimal("1.58812752"),
            "cnx_cash": Decimal("-1384392573.11000000"),
            "cnx_scale": Decimal("-175787577060.21204420"),
        },
        credit_linked_notes_row=None,
    )

    assert decomposition.liability_yield_pct is None
    assert decomposition.liability_yield_ex_cln_pct is None
    assert decomposition.cln_yield_pct is None
    assert decomposition.cln_drag_bp is None
    assert decomposition.cln_scale is None


def test_product_category_liability_cost_decomposition_returns_none_when_ex_cln_scale_is_zero():
    """CLN scale equal to the liability total leaves a zero denominator; never fall back to 0."""
    decomposition = calculate_product_category_liability_cost_decomposition(
        report_date="2026-06-30",
        view="ytd",
        liability_row={
            "weighted_yield": Decimal("1.58812752"),
            "cnx_cash": Decimal("-1384392573.11000000"),
            "cnx_scale": Decimal("-1934725622.00187845"),
        },
        credit_linked_notes_row={
            "weighted_yield": Decimal("2.81427057"),
            "cnx_cash": Decimal("-27000446.32000000"),
            "cnx_scale": Decimal("-1934725622.00187845"),
        },
    )

    assert decomposition.liability_yield_pct is None
    assert decomposition.liability_yield_ex_cln_pct is None
    assert decomposition.cln_yield_pct is None
    assert decomposition.cln_drag_bp is None
    assert decomposition.cln_scale is None


def test_product_category_liability_cost_decomposition_preserves_none_weighted_yield():
    decomposition = calculate_product_category_liability_cost_decomposition(
        report_date="2026-06-30",
        view="ytd",
        liability_row={
            "weighted_yield": None,
            "cnx_cash": Decimal("-1384392573.11000000"),
            "cnx_scale": Decimal("-175787577060.21204420"),
        },
        credit_linked_notes_row={
            "weighted_yield": None,
            "cnx_cash": Decimal("-27000446.32000000"),
            "cnx_scale": Decimal("-1934725622.00187845"),
        },
    )

    assert decomposition.liability_yield_pct is None
    assert decomposition.cln_yield_pct is None
    assert decomposition.cln_drag_bp is None
    # The ex-CLN rate is computed from cash/scale, so it survives a missing weighted_yield.
    assert decomposition.liability_yield_ex_cln_pct is not None
    assert decomposition.cln_scale == Decimal("-1934725622.00187845")
