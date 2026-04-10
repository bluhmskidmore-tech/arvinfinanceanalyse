from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
PNL_CORE_FILE = BACKEND_APP / "core_finance" / "pnl.py"

FORBIDDEN_IMPORT_ROOTS = (
    BACKEND_APP / "api",
    BACKEND_APP / "services",
    BACKEND_APP / "repositories",
)

PNL_CORE_MODULE = "backend.app.core_finance.pnl"
PNL_REEXPORTED_FROM_PACKAGE_INIT = frozenset(
    {
        "AccountingBasis",
        "CurrencyBasis",
        "FiPnlRecord",
        "FormalPnlFiFactRow",
        "InvestTypeStd",
        "JournalType",
        "NonStdJournalEntry",
        "NonStdPnlBridgeRow",
        "build_formal_pnl_fi_fact_rows",
        "build_nonstd_pnl_bridge_rows",
        "normalize_fi_pnl_records",
        "normalize_nonstd_journal_entries",
    }
)

# PnL-specific private helpers must not be duplicated outside the core module.
PNL_PRIVATE_HELPER_NAMES = (
    "_normalize_fi_invest_type",
    "_normalize_nonstd_signed_amount",
    "_entry_in_scope",
)


def _py_files_under(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


def _read_py_source(path: Path) -> str:
    # utf-8-sig strips a leading BOM if present (some editors add U+FEFF).
    return path.read_text(encoding="utf-8-sig")


def _violations_for_imports(path: Path) -> list[str]:
    text = _read_py_source(path)
    tree = ast.parse(text, filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == PNL_CORE_MODULE or name.startswith(f"{PNL_CORE_MODULE}."):
                    out.append(f"{path}: forbidden import of {name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.module == PNL_CORE_MODULE:
                out.append(f"{path}: forbidden ImportFrom {node.module}")
            if node.module == "backend.app.core_finance":
                imported = {alias.name for alias in node.names}
                bad = imported & PNL_REEXPORTED_FROM_PACKAGE_INIT
                if bad:
                    out.append(f"{path}: forbidden core_finance imports {sorted(bad)}")
    return out


def test_pnl_core_module_file_exists():
    assert PNL_CORE_FILE.is_file(), f"Missing formal PnL core module: {PNL_CORE_FILE}"


def test_api_services_repositories_do_not_import_core_finance_pnl():
    violations: list[str] = []
    for base in FORBIDDEN_IMPORT_ROOTS:
        for path in _py_files_under(base):
            violations.extend(_violations_for_imports(path))
    assert not violations, "PnL core_finance imports leaked into thin layers:\n" + "\n".join(violations)


def test_pnl_private_helpers_are_not_redefined_outside_core_pnl_module():
    """Formal PnL normalization helpers must stay centralized in core_finance/pnl.py."""
    offenders: list[str] = []
    for path in _py_files_under(BACKEND_APP):
        if path.resolve() == PNL_CORE_FILE.resolve():
            continue
        tree = ast.parse(_read_py_source(path), filename=str(path))
        defined = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef)
        }
        for name in PNL_PRIVATE_HELPER_NAMES:
            if name in defined:
                offenders.append(f"{path}: redefines {name}")
    assert not offenders, "PnL private helpers duplicated outside core module:\n" + "\n".join(offenders)


def test_pnl_service_module_does_not_reference_core_finance_package():
    """Orchestration-only: formal PnL math must enter via tasks/materialize, not service imports."""
    path = BACKEND_APP / "services" / "pnl_service.py"
    text = _read_py_source(path)
    assert "core_finance" not in text, f"{path} must not import or mention core_finance"
