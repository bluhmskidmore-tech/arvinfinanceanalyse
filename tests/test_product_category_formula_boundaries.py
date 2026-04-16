from __future__ import annotations

import re
from pathlib import Path


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
    "_build_report_rows",
    "_scale_field",
    "_days_for_view",
    "_calculate_ftp",
    "_calculate_weighted_yield",
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
