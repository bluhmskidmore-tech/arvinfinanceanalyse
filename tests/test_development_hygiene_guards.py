from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.helpers import load_module


ROOT = Path(__file__).resolve().parents[1]


def test_worktree_scope_parser_and_audit_cover_renames_and_untracked_paths() -> None:
    module = load_module(
        "scripts.audit_worktree_scope",
        "scripts/audit_worktree_scope.py",
    )

    changes = module.parse_porcelain_z(
        b" M frontend/src/feature.ts\0"
        b"?? tests/new test.py\0"
        b"R  docs/new-name.md\0docs/old-name.md\0"
    )

    assert [change.path for change in changes] == [
        "frontend/src/feature.ts",
        "tests/new test.py",
        "docs/new-name.md",
    ]
    assert changes[-1].original_path == "docs/old-name.md"

    report = module.audit_worktree_scope(
        changes,
        allowed_paths=[r"frontend\src", "tests/new test.py"],
    )

    assert report["allowed_paths"] == ["frontend/src", "tests/new test.py"]
    assert report["changed_path_count"] == 4
    assert report["outside_paths"] == ["docs/new-name.md", "docs/old-name.md"]
    assert report["scope_ok"] is False


def test_worktree_scope_preserves_posix_backslash_filename_outside_allowed_directory() -> None:
    module = load_module(
        "scripts.audit_worktree_scope",
        "scripts/audit_worktree_scope.py",
    )

    changes = module.parse_porcelain_z(b"?? frontend\\outside.py\0")

    assert changes[0].path == r"frontend\outside.py"
    report = module.audit_worktree_scope(changes, allowed_paths=["frontend"])
    assert report["outside_paths"] == [r"frontend\outside.py"]
    assert report["scope_ok"] is False


def test_worktree_scope_cli_reports_by_default_and_only_blocks_in_strict_mode(
    capsys,
) -> None:
    module = load_module(
        "scripts.audit_worktree_scope",
        "scripts/audit_worktree_scope.py",
    )
    status = b" M frontend/src/feature.ts\0 M backend/app/main.py\0"

    assert module.main(
        ["--allow", "frontend/src"],
        status_bytes=status,
        repo_root=ROOT,
    ) == 0
    assert '"scope_ok": false' in capsys.readouterr().out

    assert module.main(
        ["--allow", "frontend/src", "--strict"],
        status_bytes=status,
        repo_root=ROOT,
    ) == 1


def test_frontend_debt_audit_protects_known_monoliths_and_self_tests() -> None:
    audit_script = ROOT / "scripts" / "audit_frontend_debt.mjs"
    script = audit_script.read_text(encoding="utf-8")

    assert "protectedMonolithFiles" in script
    for protected_path in (
        "scripts/mcp/moss_project_mcp.py",
        "tests/test_project_mcp_servers.py",
        "frontend/src/api/contracts.ts",
        "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
        "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts",
        "backend/app/services/pnl_service.py",
    ):
        assert protected_path in script

    completed = subprocess.run(
        ["node", str(audit_script), "--self-test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr



def test_full_mcp_governance_snapshot_is_static_and_versioned() -> None:
    fixture_path = (
        ROOT / "tests" / "fixtures" / "mcp" / "governance_snapshot_v1.jsonl"
    )
    assert fixture_path.is_file()

    records = [
        json.loads(line)
        for line in fixture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 16
    assert len({record["page_slug"] for record in records}) == 16

    mcp_test_source = (ROOT / "tests" / "test_project_mcp_servers.py").read_text(
        encoding="utf-8"
    )
    fixture_block = mcp_test_source.split("def frozen_governance_snapshot_dir", 1)[1]
    fixture_block = fixture_block.split("class McpProcess", 1)[0]
    for production_helper in (
        "product_page_trace_bundles",
        "page_governance_record_blueprint",
        "page_governance_record_preflight",
    ):
        assert production_helper not in fixture_block
