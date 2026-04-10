"""Guard: snapshot materialization must not use preview tables or data_input direct scan."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module_source_lines(relative: str) -> list[str]:
    path = ROOT / relative
    return path.read_text(encoding="utf-8").splitlines()


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


def test_snapshot_materialize_does_not_import_direct_source_rows():
    path = ROOT / "backend" / "app" / "tasks" / "snapshot_materialize.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = _collect_imports(tree)
    banned = "backend.app.repositories.source_preview_repo._direct_source_rows"
    assert banned not in imports
    src = path.read_text(encoding="utf-8")
    assert "_direct_source_rows" not in src


def test_snapshot_materialize_does_not_reference_preview_tables_as_input():
    path = ROOT / "backend" / "app" / "tasks" / "snapshot_materialize.py"
    src = path.read_text(encoding="utf-8")
    for banned in (
        "phase1_zqtz_preview_rows",
        "phase1_tyw_preview_rows",
        "from phase1_",
        "read_sql preview",
    ):
        assert banned not in src


def test_snapshot_row_parse_does_not_touch_preview_repo():
    path = ROOT / "backend" / "app" / "repositories" / "snapshot_row_parse.py"
    assert path.exists()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = _collect_imports(tree)
    assert "backend.app.repositories.source_preview_repo" not in imports
