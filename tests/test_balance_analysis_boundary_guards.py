from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _collect_imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                names.add(f"{mod}.{alias.name}" if mod else alias.name)
    return names


def test_balance_analysis_materialize_does_not_import_preview_repo():
    path = ROOT / "backend" / "app" / "tasks" / "balance_analysis_materialize.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = _collect_imports(tree)
    assert "backend.app.repositories.source_preview_repo" not in imports
    assert "backend.app.services.source_preview_service" not in imports


def test_balance_analysis_materialize_does_not_reference_preview_tables():
    path = ROOT / "backend" / "app" / "tasks" / "balance_analysis_materialize.py"
    src = path.read_text(encoding="utf-8")
    for banned in (
        "phase1_zqtz_preview_rows",
        "phase1_tyw_preview_rows",
        "phase1_source_preview_summary",
        "from phase1_",
    ):
        assert banned not in src


def test_worker_bootstrap_includes_fx_mid_materialize_module():
    path = ROOT / "backend" / "app" / "tasks" / "worker_bootstrap.py"
    src = path.read_text(encoding="utf-8")
    assert "backend.app.tasks.fx_mid_materialize" in src
