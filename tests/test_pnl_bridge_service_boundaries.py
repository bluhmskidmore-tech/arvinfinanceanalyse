from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE_FILE = ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py"


def _collect_imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                names.add(f"{module}.{alias.name}" if module else alias.name)
    return names


def test_pnl_bridge_service_imports_balance_repo_not_duckdb():
    tree = ast.parse(SERVICE_FILE.read_text(encoding="utf-8"), filename=str(SERVICE_FILE))
    imports = _collect_imports(tree)

    assert "duckdb" not in imports
    assert "backend.app.repositories.balance_analysis_repo.BalanceAnalysisRepository" in imports


def test_pnl_bridge_service_does_not_open_duckdb_or_query_fact_tables_directly():
    text = SERVICE_FILE.read_text(encoding="utf-8")

    assert "duckdb.connect(" not in text
    assert re.search(r"\bfrom\s+fact_formal_", text) is None
    assert re.search(r"\bselect\b.+\bfact_formal_", text, flags=re.IGNORECASE | re.DOTALL) is None


def test_pnl_bridge_service_uses_shared_formal_lineage_helpers():
    text = SERVICE_FILE.read_text(encoding="utf-8")

    assert "resolve_formal_manifest_lineage" in text
    assert "resolve_completed_formal_build_lineage" in text
    assert "read_latest_manifest(" not in text
    assert "read_latest_completed_run(" not in text
