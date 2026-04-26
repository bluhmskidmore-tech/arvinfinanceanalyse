from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_native_development_scripts_exist():
    expected = [
        ROOT / "scripts" / "dev-api.ps1",
        ROOT / "scripts" / "dev-worker.ps1",
        ROOT / "scripts" / "dev-env.ps1",
        ROOT / "scripts" / "dev-up.ps1",
        ROOT / "scripts" / "dev-down.ps1",
        ROOT / "scripts" / "dev-postgres-up.ps1",
        ROOT / "scripts" / "dev-postgres-down.ps1",
        ROOT / "scripts" / "dev-postgres-status.ps1",
        ROOT / "scripts" / "dev-python.ps1",
        ROOT / "scripts" / "dev-governance-maintenance.ps1",
        ROOT / "scripts" / "codex-verify-page.ps1",
        ROOT / "scripts" / "codex-page-smoke.ps1",
    ]

    missing = [str(path) for path in expected if not path.exists()]
    assert not missing, "Missing native development scripts:\n" + "\n".join(missing)


def run_powershell_script(script_name: str, *args: str) -> str:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / script_name),
            *args,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def test_codex_verify_page_defaults_to_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "product-category-pnl")

    assert "Codex verify page: product-category-pnl" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "ProductCategoryAdjustmentAuditPage.test.tsx" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_page_smoke_defaults_to_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "product-category-pnl")

    assert "Codex page smoke: product-category-pnl" in output
    assert "/product-category-pnl" in output
    assert "/ui/pnl/product-category" in output
    assert "Playwright MCP" in output
    assert "Live checks:" not in output
