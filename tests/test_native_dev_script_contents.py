from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dev_api_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-api.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "Assert-DevBootstrapStorageReady" in script
    assert "dev-python.ps1" in script
    assert "Resolve-DevPython" in script
    assert "uvicorn backend.app.main:app" in script


def test_dev_worker_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-worker.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "Assert-DevBootstrapStorageReady" in script
    assert "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS" in script
    assert "dev-python.ps1" in script
    assert "Resolve-DevPython" in script
    assert "dramatiq backend.app.tasks.worker_bootstrap" in script


def test_dev_env_script_sets_repo_relative_data_paths():
    script = (ROOT / "scripts" / "dev-env.ps1").read_text(encoding="utf-8")
    assert "Join-Path $root" in script
    assert 'Join-Path $root "data\\moss.duckdb"' in script
    assert 'Join-Path $root "data\\archive"' in script
    assert "dev_postgres_cluster.py" in script
    assert "print-env --repo-root $root" in script
    assert "function Assert-DevBootstrapStorageReady" in script
    assert "clusterDataDir" not in script
    assert "F:\\MOSS-V3" not in script


def test_dev_governance_maintenance_script_validates_storage_bootstrap():
    script = (ROOT / "scripts" / "dev-governance-maintenance.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "Assert-DevBootstrapStorageReady" in script


def test_dev_smoke_script_validates_storage_bootstrap():
    script = (ROOT / "scripts" / "dev-smoke.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "Assert-DevBootstrapStorageReady" in script
    assert "audit_governance_lineage.py" in script
    assert "AUDIT_OK" in script


def test_dev_up_script_bootstraps_local_postgres_and_starts_native_processes():
    script = (ROOT / "scripts" / "dev-up.ps1").read_text(encoding="utf-8")
    assert "dev-env.ps1" in script
    assert "dev-postgres-up.ps1" in script
    assert '$LASTEXITCODE -ne 0' in script
    assert "dev-api.ps1" in script
    assert "dev-worker.ps1" in script
    assert "dev-frontend.ps1" in script
    assert "Start-Process" in script
    assert "Wait-HttpEndpoint" in script
    assert "Wait-TcpPort" in script
    assert "Wait-FileReady" in script
    assert "Assert-NativeProcessRunning" in script
    assert "write_dev_worker_heartbeat" in script
    assert "55432" in script
    assert "/health" in script
    assert "/api/bond-analytics/dates" in script
    assert "audit_governance_lineage.py" in script
    assert "Governance lineage audit failed" in script
    assert "exit 0" in script


def test_dev_postgres_up_script_fails_when_cluster_is_not_running():
    script = (ROOT / "scripts" / "dev-postgres-up.ps1").read_text(encoding="utf-8")
    assert "dev_postgres_cluster.py" in script
    assert "dev-postgres-common.ps1" in script
    assert "Invoke-DevPostgresClusterCommand" in script
    assert '.running' in script or '["running"]' in script
    assert "throw" in script
    assert "exit 0" in script


def test_dev_postgres_status_script_parses_json_status_payload():
    script = (ROOT / "scripts" / "dev-postgres-status.ps1").read_text(encoding="utf-8")
    assert "dev_postgres_cluster.py" in script
    assert "dev-postgres-common.ps1" in script
    assert "Invoke-DevPostgresClusterCommand" in script
    assert "exit 0" in script


def test_dev_postgres_down_script_parses_json_status_payload():
    script = (ROOT / "scripts" / "dev-postgres-down.ps1").read_text(encoding="utf-8")
    assert "dev_postgres_cluster.py" in script
    assert "dev-postgres-common.ps1" in script
    assert "Invoke-DevPostgresClusterCommand" in script
    assert "exit 0" in script


def test_dev_postgres_common_script_runs_dev_cluster_helper_directly():
    script = (ROOT / "scripts" / "dev-postgres-common.ps1").read_text(encoding="utf-8")
    assert "& $python" in script
    assert "ConvertFrom-Json" in script
    assert "Start-Process" not in script


def test_dev_down_script_stops_native_processes_and_local_postgres():
    script = (ROOT / "scripts" / "dev-down.ps1").read_text(encoding="utf-8")
    assert "dev-postgres-down.ps1" in script
    assert "dev-postgres-status.ps1" in script
    assert "Wait-PortsClosed" in script
    assert "Wait-ProcessStopped" in script
    assert "backend.app.main:app" in script
    assert "backend.app.tasks.worker_bootstrap" in script
    assert "7888" in script
    assert "5888" in script


def test_dev_governance_maintenance_script_runs_compaction_and_layering():
    script = (ROOT / "scripts" / "dev-governance-maintenance.ps1").read_text(encoding="utf-8")
    assert "dev-env.ps1" in script
    assert "dev-python.ps1" in script
    assert "compact_source_preview_governance.py" in script
    assert "build_source_manifest_layers.py" in script


def test_codex_verify_page_script_plans_product_category_checks():
    script = (ROOT / "scripts" / "codex-verify-page.ps1").read_text(encoding="utf-8")
    assert "ValidateSet(\"product-category-pnl\")" in script
    assert "Run" in script
    assert "DryRun" in script
    assert "Pass -Run to execute checks" in script
    assert "Codex verify page" in script
    assert "tests/test_project_mcp_servers.py" in script
    assert "tests/test_product_category_pnl_flow.py" in script
    assert "tests/test_product_category_mapping_contract.py" in script
    assert "ProductCategoryPnlPage.test.tsx" in script
    assert "ProductCategoryBranchSwitcher.test.tsx" in script
    assert "ProductCategoryAdjustmentAuditPage.test.tsx" in script
    assert "productCategoryPnlPageModel.test.ts" in script
    assert "npm.cmd" in script
    assert "debt:audit" in script
    assert "typecheck" in script


def test_codex_page_smoke_script_emits_product_category_checklist():
    script = (ROOT / "scripts" / "codex-page-smoke.ps1").read_text(encoding="utf-8")
    assert "ValidateSet(\"product-category-pnl\")" in script
    assert "Codex page smoke" in script
    assert "/product-category-pnl" in script
    assert "/ui/pnl/product-category" in script
    assert "Playwright MCP" in script
    assert "no data" in script
    assert "stale data" in script
    assert "fallback" in script
    assert "loading failure" in script
    assert "ZQTZ holdings-side logic" in script
    assert "$primaryApi" in script
    assert "$supportingApis" in script
    assert "Page API reachable" in script
