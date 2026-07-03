import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _extract_validate_set_values(script: str) -> set[str]:
    marker = "[ValidateSet("
    start = script.index(marker) + len(marker)
    end = script.index(")]", start)
    values = script[start:end]
    return {
        value.strip().strip('"')
        for value in values.split(",")
        if value.strip()
    }


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
    assert "dev-postgres-up.ps1" in script
    assert "dev-postgres-up.ps1 failed; aborting dev-api startup." in script
    assert "Assert-DevBootstrapStorageReady" in script
    assert "dev-python.ps1" in script
    assert "Resolve-DevPython" in script
    assert "Get-DevListeningPortOwner" in script
    assert "netstat -ano" in script
    assert "Port $port already has a listener" in script
    assert "MOSS_HOME_SNAPSHOT_PREWARM_ENABLED" in script
    assert "uvicorn backend.app.main:app" in script


def test_dev_api_enables_home_snapshot_prewarm_by_default():
    script = (ROOT / "scripts" / "dev-api.ps1").read_text(encoding="utf-8")

    assert '$env:MOSS_HOME_SNAPSHOT_PREWARM_ENABLED = "1"' in script
    assert '$env:MOSS_HOME_SNAPSHOT_PREWARM_ENABLED = "0"' not in script


def test_dev_api_enables_market_home_prewarm_by_default():
    script = (ROOT / "scripts" / "dev-api.ps1").read_text(encoding="utf-8")

    assert "MOSS_MARKET_HOME_PREWARM_ENABLED" in script
    assert '$env:MOSS_MARKET_HOME_PREWARM_ENABLED = "1"' in script


def test_dev_agent_api_uses_short_hermes_timeout_for_local_responsiveness():
    ps1 = (ROOT / "scripts" / "dev-agent-api.ps1").read_text(encoding="utf-8")
    cmd = (ROOT / "scripts" / "dev-agent-api.cmd").read_text(encoding="utf-8")

    assert '$env:MOSS_AGENT_HERMES_TIMEOUT_SECONDS = "12"' in ps1
    assert "MOSS_AGENT_HERMES_TIMEOUT_SECONDS=$($env:MOSS_AGENT_HERMES_TIMEOUT_SECONDS)" in ps1
    assert "set MOSS_AGENT_HERMES_TIMEOUT_SECONDS=12" in cmd
    assert "MOSS_AGENT_HERMES_TIMEOUT_SECONDS=%MOSS_AGENT_HERMES_TIMEOUT_SECONDS%" in cmd


def test_dev_worker_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-worker.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "Assert-DevBootstrapStorageReady" in script
    assert "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS" in script
    assert "dev-python.ps1" in script
    assert "Resolve-DevPython" in script
    assert "MOSS_DEV_WORKER_PROCESSES" in script
    assert "MOSS_DEV_WORKER_THREADS" in script
    assert "MOSS_DEV_WORKER_USE_CLI" in script
    assert "backend.app.tasks.dev_worker_runner" in script
    assert "--processes" in script
    assert "--threads" in script
    assert "backend.app.tasks.worker_bootstrap" in script


def test_dev_worker_runner_uses_in_process_dramatiq_worker():
    script = (ROOT / "backend" / "app" / "tasks" / "dev_worker_runner.py").read_text(encoding="utf-8")
    assert "backend.app.tasks.worker_bootstrap" in script
    assert "from dramatiq import Worker" in script
    assert "Worker(broker" in script
    assert "worker_threads=worker_threads" in script
    assert "multiprocessing.Pipe" not in script


def test_dev_worker_heartbeat_actor_writes_file_without_result_payload():
    script = (ROOT / "backend" / "app" / "tasks" / "dev_health.py").read_text(encoding="utf-8")
    assert "target.write_text" in script
    assert "return payload" not in script
    assert "return None" in script


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


def test_dev_hermes_webui_script_uses_wsl_webui_and_moss_defaults():
    script = (ROOT / "scripts" / "dev-hermes-webui.ps1").read_text(encoding="utf-8")
    assert 'ValidateSet("start", "stop", "restart", "status", "logs")' in script
    assert "$WslDistro = \"HermesUbuntu\"" in script
    assert "$HermesWebuiDir = \"/home/hermes/hermes-webui\"" in script
    assert "$HermesAgentDir = \"/home/hermes/hermes-agent\"" in script
    assert "$HermesHome = \"/home/hermes/.hermes-moss\"" in script
    assert "$Port = 8787" in script
    assert "$BindHost = \"127.0.0.1\"" in script
    assert "ConvertTo-WslPath" in script
    assert "HERMES_WEBUI_DEFAULT_WORKSPACE='$workspaceWsl'" in script
    assert "HERMES_WEBUI_AGENT_DIR='$HermesAgentDir'" in script
    assert "HERMES_WEBUI_PYTHON='$HermesPython'" in script
    assert "Start-Process" in script
    assert "-WindowStyle Hidden" in script
    assert "hermes-webui-start.sh" in script
    assert "Set-Content -Path $startScriptPath" in script
    assert "bootstrap.py --no-browser --foreground" in script
    assert "Wait-HermesWebuiHealth" in script
    assert "Get-HermesWebuiLog" in script
    assert "http://127.0.0.1:$Port" in script


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
    assert "System.Net.Sockets.TcpClient" in script
    assert "Get-DevListeningPortOwner -Port $Port" in script
    assert "Get-NetTCPConnection -State Listen" not in script
    assert "$script:ProcessInspectionAvailable" in script
    assert "process lookup failed for ${ScriptName}" in script
    assert "process verification unavailable" in script
    assert "Find-DevScriptLaunch" in script
    assert "PortVerifiedOnly" in script
    assert (
        '$postgresPort = Wait-TcpPort -ListenHost "127.0.0.1" -Port 55432 '
        '-TimeoutSeconds 120 -Description "local Postgres dev cluster"'
    ) in script
    assert "Wait-FileReady" in script
    assert '-TimeoutSeconds 120 -Description "worker heartbeat"' in script
    assert "Assert-PortAvailableForScriptStart" in script
    assert "Get-DevListeningPortOwner" in script
    assert "netstat -ano" in script
    assert "Assert-NativeProcessRunning" in script
    assert "Invoke-ConcurrentHttpSmoke" in script
    assert "write_dev_worker_heartbeat" in script
    assert "55432" in script
    assert "/health" in script
    assert "/health/ready" in script
    assert "/ui/home/snapshot" in script
    assert "home snapshot warm cache" in script
    assert "Home cache:" in script
    assert "Home prewarm:" in script
    assert "home_snapshot_prewarm" in script
    assert "API readiness after home snapshot warm cache" in script
    assert "did not expose checks.home_snapshot_prewarm" in script
    assert 'status -ne "ready"' in script
    assert "Home snapshot prewarm is not ready" in script
    assert "snapshot warmed" in script
    assert "/api/bond-analytics/dates" in script
    assert "/api/risk/tensor/dates" in script
    assert "/api/risk/tensor?report_date=$riskReportDate" in script
    assert "risk tensor detail concurrent smoke" in script
    assert "/src/api/clientContext.ts" in script
    assert "/src/api/client.ts" not in script
    assert "frontend Vite API client context module" in script
    assert "audit_governance_lineage.py" in script
    assert "Governance lineage audit failed" in script
    assert "exit 0" in script
    assert script.index('http://127.0.0.1:7888/ui/home/snapshot') < script.index(
        '$frontendLaunch = Start-DevScriptDetached -ScriptName "dev-frontend.ps1"'
    )
    assert script.index('$homeSnapshotWarm = Wait-HttpEndpointWithLogs') < script.index(
        '$apiReadyAfterHomeWarm = Wait-JsonStatusOkEndpointWithLogs'
    )


def test_dev_frontend_defaults_to_real_data_source():
    script = (ROOT / "scripts" / "dev-frontend.ps1").read_text(encoding="utf-8")
    assert '$env:VITE_DATA_SOURCE = "real"' in script
    assert "Frontend data source:" in script


def test_dev_frontend_repairs_missing_wsl_rolldown_binding():
    script = (ROOT / "scripts" / "dev-frontend.ps1").read_text(encoding="utf-8")
    assert "Ensure-FrontendOptionalNativeDependencies" in script
    assert "@rolldown/binding-linux-x64-gnu" in script
    assert "npm install" in script
    assert "require.resolve($packageName)" in script
    assert "WSL/Linux Vite native dependency missing" in script


def test_dev_keepalive_checks_vite_source_module_not_only_frontend_root():
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    assert "Test-FrontendReady" in script
    assert "/src/api/clientContext.ts" in script
    assert "/src/api/client.ts" not in script
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


def test_dev_postgres_cluster_cleans_stale_postmaster_pid_before_start():
    script = (ROOT / "scripts" / "dev_postgres_cluster.py").read_text(encoding="utf-8")
    assert "_remove_stale_postmaster_pid" in script
    assert "postmaster.pid" in script
    assert "pg_ctl.exe" in script
    assert "check=True" in script
    assert "capture_output=True" in script
    assert "stderr=subprocess.STDOUT" in script


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
    assert _extract_validate_set_values(script) >= {
        "dashboard-home",
        "product-category-pnl",
        "balance-analysis",
        "average-balance",
        "pnl",
        "pnl-bridge",
        "risk-tensor",
        "bond-dashboard",
        "bond-analysis",
        "balance-movement-analysis",
        "ledger-pnl",
        "positions",
        "operations-analysis",
        "liability-analytics",
        "market-data",
        "macro-toolkit",
        "stock-analysis",
        "pnl-attribution",
        "cashflow-projection",
        "concentration-monitor",
        "team-performance",
        "platform-config",
        "news-events",
    }
    assert "Run" in script
    assert "DryRun" in script
    assert "SkipMcpContracts" in script
    assert "SkipBrowserSmoke" in script
    assert "Pass -Run to execute checks" in script
    assert "codex-verify-pytest-basetemp" in script
    assert "--basetemp=" in script
    assert "$PID" in script
    assert "Resolve-CodexPytestTempRoot" in script
    assert "CODEX_PYTEST_BASETEMP_ROOT" in script
    assert ".codex-tmp\\pytest-basetemp" in script
    assert "Get-CodexPytestBaseTemp -Label $check.Label -Index $checkIndex" in script
    assert "Use-CodexPytestCommand" in script
    assert '$Check.Command = "pytest"' not in script
    assert '$Check.Command -eq "python"' in script
    assert "Set-CodexPlaywrightOutputDir" in script
    assert "MOSS_PLAYWRIGHT_OUTPUT_DIR" in script
    assert "playwright-page-results" in script
    assert "Test-CodexBrowserSmokeCheck" in script
    assert "Codex verify page" in script
    assert "dashboard-home" in script
    assert "tests/test_project_mcp_servers.py" in script
    assert "tests/test_home_snapshot_endpoint.py" in script
    assert "tests/test_dashboard_api_contract.py" in script
    assert "DashboardPage.test.tsx" in script
    assert "useDashboardSnapshotBoundary.test.tsx" in script
    assert "dashboardHomeModel.test.ts" in script
    assert "dashboardCockpitHomeModel.test.ts" in script
    assert "tests/test_product_category_pnl_flow.py" in script
    assert "tests/test_product_category_mapping_contract.py" in script
    assert "ProductCategoryPnlPage.test.tsx" in script
    assert "ProductCategoryBranchSwitcher.test.tsx" in script
    assert "ProductCategoryAdjustmentAuditPage.test.tsx" in script
    assert "productCategoryPnlPageModel.test.ts" in script
    assert "Product-category browser a11y smoke" in script
    assert "test:a11y-smoke" in script
    assert "@product-category-pnl" in script
    assert "Balance-analysis backend API and surface tests" in script

    assert "tests/test_balance_analysis_api.py" in script
    assert "tests/test_balance_analysis_consumer_surface.py" in script
    assert "Balance-analysis frontend tests" in script
    assert "BalanceAnalysisPage.test.tsx" in script
    assert "Balance-analysis browser a11y smoke" in script
    assert "@balance-analysis" in script
    assert "Average Balance backend ADB API and governance tests" in script
    assert "tests/test_adb_analysis_api.py" in script
    assert "tests/test_average_balance_governance_record.py" in script
    assert "tests/test_average_balance_owner_evidence_packet.py" in script
    assert "tests/test_average_balance_live_smoke_evidence.py" in script
    assert "tests/test_average_balance_business_owner_approval_status.py" in script
    assert "Average Balance frontend tests" in script
    assert "AverageBalancePage.test.tsx" in script
    assert "AverageBalanceView.test.tsx" in script
    assert "Average Balance browser a11y smoke" in script
    assert "@average-balance" in script
    assert "PnL backend API contract tests" in script
    assert "tests/test_pnl_api_contract.py" in script
    assert "PnL frontend route tests" in script
    assert "PnlRoutesSmoke.test.tsx" in script
    assert "PnL browser a11y smoke" in script
    assert "@pnl" in script
    assert "PnL Bridge backend contract and boundary tests" in script
    assert "tests/test_pnl_bridge_core.py" in script
    assert "tests/test_pnl_bridge_curve_effects.py" in script
    assert "tests/test_pnl_bridge_numeric_migration.py" in script
    assert "tests/test_pnl_bridge_service_boundaries.py" in script
    assert "PnL Bridge frontend tests" in script
    assert "PnlBridgePage.test.tsx" in script
    assert "PnL Bridge browser a11y smoke" in script
    assert "@pnl-bridge" in script
    assert "Risk Tensor backend API, service, materialize, and numeric tests" in script
    assert "tests/test_risk_tensor_api.py" in script
    assert "tests/test_risk_tensor_service.py" in script
    assert "tests/test_risk_tensor_materialize.py" in script
    assert "tests/test_risk_tensor_numeric_migration.py" in script
    assert "Risk Tensor frontend tests" in script
    assert "RiskTensorPage.test.tsx" in script
    assert "Risk Tensor browser a11y smoke" in script
    assert "@risk-tensor" in script
    assert "Bond Dashboard backend API, headline, source-surface, and golden-sample tests" in script
    assert "tests/test_bond_dashboard_api_contract.py" in script
    assert "tests/test_bond_dashboard_headlines_contract.py" in script
    assert "tests/test_bond_analytics_api.py" in script
    assert "tests/test_golden_samples_capture_ready.py" in script
    assert "Bond Dashboard frontend tests" in script
    assert "BondDashboardPage.test.tsx" in script
    assert "Bond Dashboard browser a11y smoke" in script
    assert "@bond-dashboard" in script
    assert "Balance Movement backend API, service, core, materialize, and result-meta tests" in script
    assert "tests/test_accounting_asset_movement_api.py" in script
    assert "tests/test_accounting_asset_movement_service.py" in script
    assert "tests/test_accounting_asset_movement_core.py" in script
    assert "tests/test_accounting_asset_movement_materialize.py" in script
    assert "Balance Movement frontend tests" in script
    assert "BalanceMovementAnalysisPage.test.tsx" in script
    assert "Balance Movement browser a11y smoke" in script
    assert "@balance-movement-analysis" in script
    assert "Ledger PnL backend service and source-contract tests" in script
    assert "tests/test_ledger_pnl_service.py" in script
    assert "tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py" in script
    assert "Ledger PnL frontend page tests" in script
    assert "LedgerPnlPage.test.tsx" in script
    assert "Ledger PnL frontend route smoke tests" in script
    assert "LedgerPnlRoutesSmoke.test.tsx" in script
    assert "Ledger PnL browser a11y smoke" in script
    assert "@ledger-pnl" in script
    assert "Positions backend API contract tests" in script
    assert "tests/test_positions_api_contract.py" in script
    assert "Positions frontend tests" in script
    assert "PositionsView.test.tsx" in script
    assert "RouteRegistry.test.tsx" in script
    assert "CustomerDetailModal.test.tsx" in script
    assert "Positions browser a11y smoke" in script
    assert "@positions" in script
    assert "Operations Analysis backend product-category, balance, and golden-sample tests" in script
    assert "tests/test_product_category_pnl_flow.py" in script
    assert "tests/test_balance_analysis_api.py" in script
    assert "Operations Analysis frontend tests" in script
    assert "OperationsAnalysisPage.test.tsx" in script
    assert "OperationsAnalysisPage.governed.test.tsx" in script
    assert "Operations Analysis browser a11y smoke" in script
    assert "@operations-analysis" in script
    assert "Liability Analytics backend compatibility, envelope, unit, and numeric tests" in script
    assert "tests/test_liability_analytics_api.py" in script
    assert "tests/test_liability_analytics_envelope_contract.py" in script
    assert "tests/test_liability_analytics_compat_contract.py" in script
    assert "tests/test_liability_analytics_unit_semantics.py" in script
    assert "tests/test_liability_analytics_numeric_migration.py" in script
    assert "Liability Analytics frontend tests" in script
    assert "LiabilityAnalyticsPage.test.tsx" in script
    assert "liabilityAdapter.test.ts" in script
    assert "liabilityAnalyticsPageModel.test.ts" in script
    assert "Liability Analytics browser a11y smoke" in script
    assert "@liability-analytics" in script
    assert "Market Data backend macro, FX, NCD proxy, Livermore, and result-meta tests" in script
    assert "tests/test_result_meta_on_all_ui_endpoints.py" in script
    assert "tests/test_market_data_ncd_proxy_api.py" in script
    assert "tests/test_market_data_livermore_api.py" in script
    assert "tests/test_market_data_livermore_risk_exit_source.py" in script
    assert "tests/test_macro_bond_linkage.py" in script
    assert "tests/test_fx_analytical_view_api.py" in script
    assert "Market Data frontend tests" in script
    assert "MarketDataPage.test.tsx" in script
    assert "marketDataPageModel.test.ts" in script
    assert "Market Data browser a11y smoke" in script
    assert "@market-data" in script
    assert "Macro Toolkit backend read, strategy, refresh, auth, and result-meta tests" in script
    assert "tests/test_macro_toolkit_scripts.py" in script
    assert "tests/test_macro_toolkit_choice_stock_refresh_overview.py" in script
    assert "tests/test_macro_toolkit_factor_snapshot_dates.py" in script
    assert "tests/test_macro_toolkit_a_share_risk.py" in script
    assert "tests/test_macro_toolkit_shadow_portfolio_report.py" in script
    assert "tests/test_macro_query_contract_smoke.py" in script
    assert "tests/test_write_route_auth_contract.py" in script
    assert "Macro Toolkit frontend tests" in script
    assert "MacroToolkitPage.test.tsx" in script
    assert "macroToolkitClient.test.ts" in script
    assert "Macro Toolkit browser a11y smoke" in script
    assert "@macro-toolkit" in script
    assert "Stock Analysis backend Livermore observation and diagnostics tests" in script
    assert "test_stock_analysis_trace_bundle_preserves_observational_livermore_boundaries" in script
    assert "test_lineage_evidence_mcp_maps_stock_analysis_gap_to_observational_livermore_records" in script
    assert "test_stock_analysis_readiness_exposes_run_commands_without_formal_promotion" in script
    assert "tests/test_stock_analysis_governance_record.py" in script
    assert "tests/test_stock_analysis_owner_evidence_packet.py" in script
    assert "tests/test_stock_analysis_business_owner_approval_status.py" in script
    assert "tests/test_market_data_livermore_candidate_history.py" in script
    assert "tests/test_market_data_livermore_stock_detail.py" in script
    assert "tests/test_market_data_livermore_sector_rank_series.py" in script
    assert "tests/test_livermore_signal_confluence.py" in script
    assert "Stock Analysis frontend tests" in script
    assert "StockAnalysisPage.test.tsx" in script
    assert "StockAnalysisPageModel.test.ts" in script
    assert "StockDetailDrawer.test.tsx" in script
    assert "buildConsensusSummary.test.ts" in script
    assert "Stock Analysis browser a11y smoke" in script
    assert "@stock-analysis" in script
    assert "PnL Attribution backend workbench, numeric, and Campisi tests" in script
    assert "tests/test_pnl_attribution_api_contract.py" in script
    assert "tests/test_pnl_attribution_workbench_contract.py" in script
    assert "tests/test_pnl_attribution_service_explicit_numeric.py" in script
    assert "tests/test_campisi_attribution_service.py" in script
    assert "tests/test_campisi_formula_golden.py" in script
    assert "PnL Attribution frontend tests" in script
    assert "PnlAttributionPage.test.tsx" in script
    assert "pnlAttributionAdapter.test.ts" in script
    assert "PnlAttributionView.test.ts" in script
    assert "PnL Attribution browser a11y smoke" in script
    assert "@pnl-attribution" in script
    assert "Cashflow Projection backend API and result-meta tests" in script
    assert "tests/test_cashflow_projection.py" in script
    assert "tests/test_cashflow_projection_numeric_migration.py" in script
    assert "tests/test_result_meta_source_surface_followup.py" in script
    assert "tests/test_wave5_service_explicit_numeric.py" in script
    assert "Cashflow Projection frontend tests" in script
    assert "CashflowProjectionPage.test.tsx" in script
    assert "cashflowProjectionAdapter.test.ts" in script
    assert "cashflowProjectionPageModel.test.ts" in script
    assert "Cashflow Projection browser a11y smoke" in script
    assert "@cashflow-projection" in script
    assert "Concentration Monitor backend credit-spread and result-meta tests" in script
    assert "tests/test_bond_analytics_api.py" in script
    assert "tests/test_bond_analytics_service.py" in script
    assert "Concentration Monitor frontend tests" in script
    assert "ConcentrationMonitorPage.test.tsx" in script
    assert "BondAnalyticsClient.test.ts" in script
    assert "Concentration Monitor browser a11y smoke" in script
    assert "@concentration-monitor" in script
    assert "Team Performance backend PnL and product-category context tests" in script
    assert "Team Performance frontend tests" in script
    assert "TeamPerformancePage.test.tsx" in script
    assert "LiveRouteRealPageSmoke.test.tsx" in script
    assert "Team Performance browser a11y smoke" in script
    assert "@team-performance" in script
    assert "Platform Config backend health and source-preview tests" in script
    assert "tests/test_health_endpoints.py" in script
    assert "tests/test_source_preview_flow.py" in script
    assert "Platform Config frontend tests" in script
    assert "PlatformConfigPage.test.tsx" in script
    assert "Platform Config browser a11y smoke" in script
    assert "@platform-config" in script
    assert "News Events backend Choice news route and result-meta tests" in script
    assert "tests/test_choice_news_routes.py" in script
    assert "News Events frontend tests" in script
    assert "NewsEventsPage.test.tsx" in script
    assert "News Events browser a11y smoke" in script
    assert "@news-events" in script
    assert "MOSS_PLAYWRIGHT_USE_WEB_SERVER" in script
    assert "npm.cmd" in script
    assert "debt:audit" in script
    assert "typecheck" in script
    assert "Frontend production build" in script
    assert "build" in script


def test_codex_dev_flow_adapts_development_loop_to_existing_page_harnesses():
    script = (ROOT / "scripts" / "codex-dev-flow.ps1").read_text(encoding="utf-8")

    assert "codex-page-readiness.ps1" in script
    assert "codex-verify-page.ps1" in script
    assert "Mode: $Mode" in script
    assert 'ValidateSet("plan", "preflight", "verify", "readiness", "approval", "all")' in script
    assert "Development flow plan complete. Pass -Run with -Mode verify/readiness/approval/all to execute." in script
    assert "Invoke-Preflight" in script
    assert "Invoke-Verify" in script
    assert "Invoke-Readiness" in script
    assert "Invoke-Approval" in script
    assert "-RequireApprovalCaptured" in script
    assert "Development flow adapter finished." in script


def test_codex_page_smoke_script_emits_product_category_checklist():
    script = (ROOT / "scripts" / "codex-page-smoke.ps1").read_text(encoding="utf-8")
    assert _extract_validate_set_values(script) >= {
        "dashboard-home",
        "product-category-pnl",
        "balance-analysis",
        "average-balance",
        "pnl",
        "pnl-bridge",
        "risk-tensor",
        "bond-dashboard",
        "bond-analysis",
        "balance-movement-analysis",
        "ledger-pnl",
        "positions",
        "operations-analysis",
        "liability-analytics",
        "market-data",
        "macro-toolkit",
        "stock-analysis",
        "pnl-attribution",
        "cashflow-projection",
        "concentration-monitor",
        "team-performance",
        "platform-config",
        "news-events",
    }
    assert "Codex page smoke" in script
    assert "dashboard-home" in script
    assert "routeAliases" in script
    assert "/dashboard" in script
    assert "Supplemental API probe" in script
    assert "/ui/home/snapshot" in script
    assert "/api/dashboard/core_metrics" in script
    assert "formal metric truth" in script
    assert "/product-category-pnl" in script
    assert "/ui/pnl/product-category" in script
    assert "/balance-analysis" in script
    assert "/ui/balance-analysis/overview" in script
    assert "/ui/balance-analysis/dates" in script
    assert "formal balance truth" in script
    assert "/average-balance" in script
    assert "/adb" in script
    assert "/api/analysis/adb" in script
    assert "/api/analysis/adb/comparison" in script
    assert "/api/analysis/adb/monthly" in script
    assert "/api/analysis/adb/coverage" in script
    assert "candidate average-balance ADB analysis question" in script
    assert "GAP-AVERAGE-BALANCE-PAGE" in script
    assert "formal_use_allowed=false" in script
    assert "MTR-ADB-003 stays tied only to GS-AVERAGE-BALANCE-MONTHLY-A candidate monthly ADB/NIM DTO evidence" in script
    assert "/pnl" in script
    assert "/api/pnl/overview" in script
    assert "/api/pnl/dates" in script
    assert "/api/pnl/v1-data" in script
    assert "formal PnL truth" in script
    assert "/pnl-bridge" in script
    assert "/api/pnl/bridge" in script
    assert "PnL Bridge" in script
    assert "bridge warnings" in script
    assert "/risk-tensor" in script
    assert "/api/risk/tensor" in script
    assert "/api/risk/tensor/dates" in script
    assert "Risk Tensor" in script
    assert "regulatory_dv01" in script
    assert "/bond-dashboard" in script
    assert "/api/bond-dashboard/headline-kpis" in script
    assert "/api/bond-dashboard/dates" in script
    assert "/api/bond-dashboard/risk-indicators" in script
    assert "candidate bond-dashboard headline question" in script
    assert "MTR-BOND candidate metrics" in script
    assert "/balance-movement-analysis" in script
    assert "/ui/balance-movement-analysis" in script
    assert "/ui/balance-movement-analysis/dates" in script
    assert "balance movement explanation question" in script
    assert "Balance Movement freshness gate passed" in script
    assert "freshness_status" in script
    assert "latest_read_model_report_date" in script
    assert "latest_upstream_control_report_date" in script
    assert "product_category_pnl_canonical_fact" in script
    assert "MTR-BMV candidate metrics" in script
    assert "/ledger-pnl" in script
    assert "/api/ledger-pnl/summary" in script
    assert "/api/ledger-pnl/dates" in script
    assert "/api/ledger-pnl/formal-financial-indicators" in script
    assert "ledger-account PnL candidate display question" in script
    assert "MTR-LPN candidate display metrics" in script
    assert "/positions" in script
    assert "/api/positions/bonds" in script
    assert "/api/positions/interbank" in script
    assert "/api/positions/stats/rating" in script
    assert "positions list candidate display question" in script
    assert "MTR-POS candidate display metrics" in script
    assert "/operations-analysis" in script
    assert "/ui/pnl/product-category" in script
    assert "/ui/balance-analysis/overview" in script
    assert "/ui/market-data/fx/formal-status" in script
    assert "operations mixed-source entry question" in script
    assert "MTR-OPS" in script
    assert "/liability-analytics" in script
    assert "/api/risk/buckets" in script
    assert "/api/analysis/yield_metrics" in script
    assert "/api/analysis/yield-by-period" in script
    assert "/api/analysis/liabilities/counterparty" in script
    assert "/api/liabilities/monthly" in script
    assert "/ui/liability/business-context" in script
    assert "/api/analysis/liabilities/cockpit-warnings" in script
    assert "/api/analysis/liabilities/contribution-split" in script
    assert "/api/analysis/adb/monthly" in script
    assert "liability compatibility analytics question" in script
    assert "MTR-LIAB" in script
    assert "governed-mixed-source" in script
    assert "compatibility analytical" in script
    assert "formal balance/PnL truth" in script
    assert "frontend recomputation" in script
    assert "result_meta/no-data/fallback/stale boundaries" in script
    assert "/market-data" in script
    assert "/ui/preview/macro-foundation" in script
    assert "/ui/market-data/rates" in script
    assert "/ui/macro/choice-series/latest" in script
    assert "/ui/market-data/fx/formal-status" in script
    assert "/ui/market-data/fx/analytical" in script
    assert "/ui/market-data/ncd-funding-proxy" in script
    assert "/api/macro-bond-linkage" in script
    assert "/ui/market-data/livermore" in script
    assert "market-data mixed-source question" in script
    assert "MTR-MKT-001" in script
    assert "macro preview" in script
    assert "formal rates fragment" in script
    assert "NCD proxy" in script
    assert "Livermore analytical" in script
    assert "full-page formal truth" in script
    assert "/macro-toolkit" in script
    assert "/ui/macro/toolkit/analysis" in script
    assert "/ui/macro/toolkit/analysis/strategy-summaries" in script
    assert "/ui/macro/toolkit/scripts" in script
    assert "/ui/macro/toolkit/adversarial-signal" in script
    assert "/ui/macro/toolkit/choice-stock/refresh-status" in script
    assert "macro-toolkit tooling observation question" in script
    assert "operation/script outputs" in script
    assert "investment recommendations" in script
    assert "MTR-MACRO" in script
    assert "/stock-analysis" in script
    assert "/ui/market-data/livermore/signal-confluence" in script
    assert "/ui/market-data/livermore/stock-detail" in script
    assert "/ui/market-data/livermore/candidate-history" in script
    assert "/ui/market-data/livermore/strategy-score" in script
    assert "/ui/market-data/livermore/strategy-optimization" in script
    assert "/ui/market-data/livermore/cycle-proxy-backtest" in script
    assert "/ui/market-data/livermore/candidate-history-portfolio-backtest" in script
    assert "/ui/market-data/livermore/sector-rank-series" in script
    assert "stock-analysis observational review question" in script
    assert "PAGE-STOCK" in script
    assert "trading instructions" in script
    assert "/pnl-attribution" in script
    assert "/api/pnl-attribution/volume-rate" in script
    assert "/api/pnl-attribution/tpl-market" in script
    assert "/api/pnl-attribution/composition" in script
    assert "/cashflow-projection" in script
    assert "/api/cashflow-projection" in script
    cashflow_checklist = script.split('$PageSlug -eq "cashflow-projection"', 1)[1].split(
        '$PageSlug -eq "team-performance"',
        1,
    )[0]
    cashflow_live_probe = script.split('$PageSlug -eq "cashflow-projection"', 2)[2].split(
        '$PageSlug -eq "team-performance"',
        1,
    )[0]
    assert "$primaryApi`?report_date=$reportDate" in cashflow_live_probe
    assert "$primaryApi`?date=$reportDate" not in cashflow_live_probe
    assert "candidate cashflow projection question" in cashflow_checklist
    assert "MTR-CFP" in cashflow_checklist
    assert "formal liquidity truth" in cashflow_checklist
    assert "certified risk-limit approval" in cashflow_checklist
    assert "/concentration-monitor" in script
    assert "/api/bond-analytics/credit-spread-migration" in script
    assert "/api/bond-analytics/dates" in script
    assert "concentration-monitor candidate risk question" in script
    assert "MTR-CON" in script
    assert "certified concentration-limit approval" in script
    assert "/team-performance" in script
    assert "/api/pnl/by-business-ytd" in script
    assert "candidate team-performance mapping question" in script
    assert "MTR-TEAM-001" in script
    assert "owner-approved performance allocation" in script
    assert "/platform-config" in script
    assert "/ui/preview/source-foundation" in script
    assert "/health/ready" in script
    assert "/health/live" in script
    assert "diagnostic platform/source question" in script
    assert "MTR-PLT-001" in script
    assert "MTR-PLT-003" in script
    assert "data-quality approval" in script
    assert "/news-events" in script
    assert "/ui/news/choice-events/latest" in script
    assert "analytical news/event context question" in script
    assert "PAGE-CONTRACT-PENDING:/news-events" in script
    assert "GAP-NEWS-EVENTS-PAGE" in script
    assert "trading instruction" in script
    assert "source data-quality approval" in script
    assert "/api/pnl-attribution/summary" in script
    assert "/api/pnl-attribution/advanced/summary" in script
    assert "/api/pnl-attribution/campisi/four-effects" in script
    assert "PnL Attribution Workbench candidate closure question" in script
    assert "MTR-PAT" in script
    assert "formal PnL overview" in script
    assert "executive analytical overlay" in script
    assert "Playwright MCP" in script
    assert "no data" in script
    assert "stale data" in script
    assert "fallback" in script
    assert "loading failure" in script
    assert "ZQTZ holdings-side logic" in script
    assert "$primaryApi" in script
    assert "$supportingApis" in script
    assert "Page API reachable" in script


def test_codex_page_readiness_script_composes_static_evidence_and_page_checks():
    script = (ROOT / "scripts" / "codex-page-readiness.ps1").read_text(encoding="utf-8")

    assert "PageSlug" in script
    assert "codex_page_readiness.py" in script
    assert "--page-slug" in script
    assert "[switch]$All" in script
    assert "--all" in script
    assert "all seeded pages" in script
    assert "Page readiness rows" in script
    assert 'Where-Object { $_.name -eq "golden_sample_boundary" }' in script
    assert "Batch dry run complete" in script
    assert "codex-page-smoke.ps1" in script
    assert "codex-verify-page.ps1" in script
    assert "MOSS page readiness gate" in script
    assert "Dry run complete. Pass -Run to execute page checks." in script
    assert "Page readiness gate passed." in script
    assert "ConvertFrom-Json" in script
    assert "blocking_gates" in script
    assert "-Run" in script
    assert "-CheckLive" in script
