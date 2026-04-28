import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _extract_powershell_function(script: str, name: str) -> str:
    start = script.index(f"function {name} ")
    brace_start = script.index("{", start)
    depth = 0
    for index in range(brace_start, len(script)):
        char = script[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[start : index + 1]
    raise AssertionError(f"Could not extract PowerShell function {name}")


def _single_quote_powershell(value: Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_powershell_harness(harness_path: Path, output_path: Path) -> int:
    command = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{harness_path}" > "{output_path}" 2>&1'
    previous_cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        return os.system(command)
    finally:
        os.chdir(previous_cwd)


def test_dev_api_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-api.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "Assert-DevBootstrapStorageReady" in script
    assert "dev-python.ps1" in script
    assert "Resolve-DevPython" in script
    assert "Get-DevListeningPortOwner" in script
    assert "netstat -ano" in script
    assert "Port $port already has a listener" in script
    assert "uvicorn backend.app.main:app" in script


def test_dev_worker_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-worker.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "Assert-DevBootstrapStorageReady" in script
    assert "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS" in script
    assert "dev-python.ps1" in script
    assert "Resolve-DevPython" in script
    assert "MOSS_DEV_WORKER_PROCESSES" in script
    assert "MOSS_DEV_WORKER_THREADS" in script
    assert "--processes" in script
    assert "--threads" in script
    assert "backend.app.tasks.worker_bootstrap" in script


def test_dev_python_prefers_repo_virtualenv_before_system_python():
    script = (ROOT / "scripts" / "dev-python.ps1").read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in script
    assert "Get-Command python -ErrorAction SilentlyContinue" in script
    assert script.index("$candidates += $venvPython") < script.index("$candidates += $systemPythonCommand.Source")


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
    assert "Start-Process" not in script
    assert "Start-DevScriptDetached" in script
    assert "WScript.Shell" in script
    assert "runtime-clean\\logs" in script
    assert ".out.log" in script
    assert ".err.log" in script
    assert "stdout=$stdoutPath stderr=$stderrPath" in script
    assert "Add-LogContext" in script
    assert "Wait-HttpEndpointWithLogs" in script
    assert "Wait-JsonStatusOkEndpointWithLogs" in script
    assert "Wait-HttpEndpoint" in script
    assert "Wait-TcpPort" in script
    assert "Wait-FileReady" in script
    assert "Assert-PortAvailableForScriptStart" in script
    assert "Get-DevListeningPortOwner" in script
    assert "netstat -ano" in script
    assert "Assert-NativeProcessRunning" in script
    assert "Invoke-ConcurrentHttpSmoke" in script
    assert "write_dev_worker_heartbeat" in script
    assert "55432" in script
    assert "/health" in script
    assert "/health/ready" in script
    assert "/api/bond-analytics/dates" in script
    assert "/api/risk/tensor/dates" in script
    assert "/api/risk/tensor?report_date=$riskReportDate" in script
    assert "risk tensor detail concurrent smoke" in script
    assert "/src/api/client.ts" in script
    assert "frontend Vite API client module" in script
    assert "audit_governance_lineage.py" in script
    assert "Governance lineage audit failed" in script
    assert "exit 0" in script


def test_dev_keepalive_checks_vite_source_module_not_only_frontend_root():
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    assert "Test-FrontendReady" in script
    assert "/src/api/client.ts" in script
    assert "http://127.0.0.1:5888" in script


def test_dev_up_http_failure_wrapper_includes_recent_logs(tmp_path):
    script = (ROOT / "scripts" / "dev-up.ps1").read_text(encoding="utf-8")
    log_path = tmp_path / "service.err.log"
    log_path.write_text("old line\nrecent failure line\n", encoding="utf-8")
    harness = "\n\n".join(
        [
            _extract_powershell_function(script, "Get-RecentLogLines"),
            _extract_powershell_function(script, "Format-RecentLogSnippet"),
            _extract_powershell_function(script, "Add-LogContext"),
            _extract_powershell_function(script, "Wait-HttpEndpointWithLogs"),
            """
function Wait-HttpEndpoint {
  throw "probe failed"
}

try {
  Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:1" -Description "test endpoint" -LogPaths @(__LOG_PATH__) | Out-Null
  throw "expected Wait-HttpEndpointWithLogs to fail"
} catch {
  $message = $_.Exception.Message
  if ($message -notlike "*probe failed*") { throw "missing probe error: $message" }
  if ($message -notlike "*Recent logs:*") { throw "missing log header: $message" }
  if ($message -notlike "*service.err.log*") { throw "missing log path: $message" }
  if ($message -notlike "*recent failure line*") { throw "missing log body: $message" }
}
""".replace("__LOG_PATH__", _single_quote_powershell(log_path)),
        ]
    )
    harness_path = tmp_path / "dev-up-log-wrapper-test.ps1"
    harness_path.write_text(harness, encoding="utf-8")

    output_path = tmp_path / "dev-up-log-wrapper-test.out"
    exit_code = _run_powershell_harness(harness_path, output_path)

    assert exit_code == 0, output_path.read_text(encoding="utf-8", errors="replace")


def test_dev_up_json_ready_failure_wrapper_includes_recent_logs(tmp_path):
    script = (ROOT / "scripts" / "dev-up.ps1").read_text(encoding="utf-8")
    log_path = tmp_path / "api.err.log"
    log_path.write_text("startup migration failed\n", encoding="utf-8")
    harness = "\n\n".join(
        [
            _extract_powershell_function(script, "Get-RecentLogLines"),
            _extract_powershell_function(script, "Format-RecentLogSnippet"),
            _extract_powershell_function(script, "Add-LogContext"),
            _extract_powershell_function(script, "Wait-JsonStatusOkEndpointWithLogs"),
            """
function Invoke-WebRequest {
  return [pscustomobject]@{
    StatusCode = 200
    Content = '{"status":"degraded","checks":{"postgresql":{"ok":false}}}'
  }
}

try {
  Wait-JsonStatusOkEndpointWithLogs -Url "http://127.0.0.1:7888/health/ready" -TimeoutSeconds 0 -Description "API readiness" -LogPaths @(__LOG_PATH__) | Out-Null
  throw "expected Wait-JsonStatusOkEndpointWithLogs to fail"
} catch {
  $message = $_.Exception.Message
  if ($message -notlike "*status=degraded*") { throw "missing degraded status: $message" }
  if ($message -notlike "*Recent logs:*") { throw "missing log header: $message" }
  if ($message -notlike "*startup migration failed*") { throw "missing log body: $message" }
}
""".replace("__LOG_PATH__", _single_quote_powershell(log_path)),
        ]
    )
    harness_path = tmp_path / "dev-up-ready-wrapper-test.ps1"
    harness_path.write_text(harness, encoding="utf-8")

    output_path = tmp_path / "dev-up-ready-wrapper-test.out"
    exit_code = _run_powershell_harness(harness_path, output_path)

    assert exit_code == 0, output_path.read_text(encoding="utf-8", errors="replace")


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
