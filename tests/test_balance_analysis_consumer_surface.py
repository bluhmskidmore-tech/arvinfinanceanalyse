from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROUTES_DIR = ROOT / "backend" / "app" / "api" / "routes"
SERVICES_DIR = ROOT / "backend" / "app" / "services"

BALANCE_ANALYSIS_ROUTE = API_ROUTES_DIR / "balance_analysis.py"
BALANCE_ANALYSIS_SERVICE_MODULE = "backend.app.services.balance_analysis_service"
BALANCE_ANALYSIS_REPO_MODULE = "backend.app.repositories.balance_analysis_repo"

# pnl.bridge reads formal zqtz balance facts for reconciliation; keep imports explicit here.
_SERVICES_ALLOWED_TO_IMPORT_BALANCE_ANALYSIS_REPO = frozenset(
    {
        "balance_analysis_service.py",
        "pnl_bridge_service.py",
    }
)


def _imports_for(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.add(f"{module}.{alias.name}" if module else alias.name)
    return imports


def test_balance_analysis_route_is_the_only_api_route_that_imports_balance_analysis_service():
    offenders: list[str] = []
    for path in API_ROUTES_DIR.glob("*.py"):
        if path.name == "balance_analysis.py":
            continue
        imports = _imports_for(path)
        if (
            BALANCE_ANALYSIS_SERVICE_MODULE in imports
            or f"{BALANCE_ANALYSIS_SERVICE_MODULE}.balance_analysis_detail_envelope" in imports
            or f"{BALANCE_ANALYSIS_SERVICE_MODULE}.balance_analysis_overview_envelope" in imports
            or f"{BALANCE_ANALYSIS_SERVICE_MODULE}.balance_analysis_summary_envelope" in imports
            or f"{BALANCE_ANALYSIS_SERVICE_MODULE}.balance_analysis_workbook_envelope" in imports
            or f"{BALANCE_ANALYSIS_SERVICE_MODULE}.balance_analysis_basis_breakdown_envelope" in imports
        ):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, (
        "Current consumer surface should not expand beyond the governed balance_analysis route:\n"
        + "\n".join(offenders)
    )


def test_balance_analysis_repo_is_not_imported_by_other_services():
    offenders: list[str] = []
    for path in SERVICES_DIR.glob("*.py"):
        if path.name in _SERVICES_ALLOWED_TO_IMPORT_BALANCE_ANALYSIS_REPO:
            continue
        imports = _imports_for(path)
        if (
            BALANCE_ANALYSIS_REPO_MODULE in imports
            or f"{BALANCE_ANALYSIS_REPO_MODULE}.BalanceAnalysisRepository" in imports
            or BALANCE_ANALYSIS_SERVICE_MODULE in imports
        ):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, (
        "Current balance_analysis consumer surface should remain isolated to its governed service path:\n"
        + "\n".join(offenders)
    )
