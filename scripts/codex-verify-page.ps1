param(
  [ValidateSet("dashboard-home", "product-category-pnl", "balance-analysis", "decision-items", "pnl", "pnl-bridge", "risk-tensor", "bond-dashboard", "bond-analysis", "balance-movement-analysis", "ledger-pnl", "positions", "operations-analysis", "liability-analytics", "market-data", "macro-toolkit", "stock-analysis", "pnl-attribution", "cashflow-projection", "concentration-monitor", "team-performance", "platform-config", "news-events", "kpi-performance")]
  [string]$PageSlug = "product-category-pnl",

  [switch]$Run,
  [switch]$DryRun,
  [switch]$SkipMcpContracts,
  [switch]$SkipBrowserSmoke
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $root "frontend"
$playwrightOutputRoot = Join-Path $root ".codex-tmp\playwright-page-results"

function Resolve-CodexPytestTempRoot {
  if (-not [string]::IsNullOrWhiteSpace($env:CODEX_PYTEST_BASETEMP_ROOT)) {
    return $env:CODEX_PYTEST_BASETEMP_ROOT
  }

  return (Join-Path $root ".codex-tmp\pytest-basetemp\codex-verify-pytest-basetemp")
}

function ConvertTo-CodexSafePathSegment {
  param(
    [string]$Value
  )

  $safe = ($Value.ToLowerInvariant() -replace "[^a-z0-9]+", "-").Trim("-")
  if ([string]::IsNullOrWhiteSpace($safe)) {
    return "pytest"
  }
  return $safe
}

function Get-CodexPytestBaseTemp {
  param(
    [string]$Label,
    [int]$Index
  )

  $safePage = ConvertTo-CodexSafePathSegment -Value $PageSlug
  $basePrefix = $codexPytestTempRoot -replace "[\\/]+$", ""
  return "$basePrefix-cvp-$safePage-$PID-$Index"
}

function Use-CodexPytestCommand {
  param(
    [hashtable]$Check
  )

  return (
    $Check.Command -eq "python" -and
    $Check.Args.Count -ge 3 -and
    $Check.Args[0] -eq "-m" -and
    $Check.Args[1] -eq "pytest"
  )
}

function Set-CodexPlaywrightOutputDir {
  param(
    [hashtable]$Check
  )

  if (-not $Check.ContainsKey("Env")) {
    return
  }
  if (-not $Check.Env.ContainsKey("MOSS_PLAYWRIGHT_USE_WEB_SERVER")) {
    return
  }
  if ($Check.Env.ContainsKey("MOSS_PLAYWRIGHT_OUTPUT_DIR")) {
    return
  }

  $safeLabel = ConvertTo-CodexSafePathSegment -Value $Check.Label
  $port = $Check.Env["MOSS_PLAYWRIGHT_PORT"]
  $runId = Get-Date -Format "yyyyMMddHHmmssfff"
  $Check.Env["MOSS_PLAYWRIGHT_OUTPUT_DIR"] = Join-Path $playwrightOutputRoot "$PageSlug-$port-$safeLabel-$PID-$runId"
}

function Test-CodexBrowserSmokeCheck {
  param(
    [hashtable]$Check
  )

  return (
    $Check.Command -eq "npm.cmd" -and
    @($Check.Args) -contains "test:a11y-smoke"
  )
}

$codexPytestTempRoot = Resolve-CodexPytestTempRoot

Set-Location $root

Write-Output "Codex verify page: $PageSlug"

$planOnly = $DryRun -or -not $Run

$checks = @()

if (-not $SkipMcpContracts) {
  $mcpContractArgs = @("-m", "pytest", "tests/test_project_mcp_servers.py", "-q")
  if ($PageSlug -eq "risk-tensor") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_metric_contracts_mcp_exposes_seeded_page_trace_bundles[risk-tensor-/risk-tensor-/api/risk/tensor-RiskTensorPayload-backend/app/services/risk_tensor_service.py-frontend/src/features/risk-tensor/RiskTensorPage.tsx-tests/test_risk_tensor_api.py-tests/golden_samples/GS-RISK-A-warning quality-/risk-tensor]",
      "tests/test_project_mcp_servers.py::test_risk_tensor_trace_bundle_preserves_formal_warning_boundaries",
      "tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_page_risk_contract_to_risk_tensor_records",
      "tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_coverage_configures_formal_seeded_pages",
      "-q"
    )
  } elseif ($PageSlug -eq "product-category-pnl") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_metric_contracts_mcp_exposes_seeded_page_trace_bundles[product-category-pnl-/product-category-pnl-/ui/pnl/product-category-product_category_pnl_formal_read_model-backend/app/services/product_category_source_service.py-frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx-tests/test_product_category_pnl_flow.py-tests/golden_samples/GS-PROD-CAT-PNL-A-zqtz holdings-side logic-/product-category-pnl]",
      "tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_product_category_page_aliases_to_formal_model_records",
      "tests/test_codex_page_readiness_gate.py::test_product_category_readiness_static_gates_surface_contract_evidence",
      "tests/test_product_category_governance_doc_contract.py",
      "-q"
    )
  } elseif ($PageSlug -eq "cashflow-projection") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_cashflow_projection_trace_bundle_preserves_candidate_liquidity_boundary",
      "tests/test_codex_page_readiness_gate.py::test_cashflow_projection_readiness_exposes_candidate_record_path_without_formal_promotion",
      "tests/test_cashflow_projection_governance_record.py",
      "-q"
    )
  } elseif ($PageSlug -eq "concentration-monitor") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_concentration_monitor_trace_bundle_preserves_candidate_concentration_boundary",
      "tests/test_codex_page_readiness_gate.py::test_concentration_monitor_readiness_exposes_candidate_record_path_without_formal_promotion",
      "tests/test_concentration_monitor_governance_record.py",
      "-q"
    )
  } elseif ($PageSlug -eq "decision-items") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_decision_items_trace_bundle_preserves_read_write_governance_boundaries",
      "tests/test_codex_page_readiness_gate.py::test_decision_items_readiness_exposes_read_write_boundary_without_formal_promotion",
      "tests/test_decision_items_governance_record.py",
      "-q"
    )
  } elseif ($PageSlug -eq "kpi-performance") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_kpi_performance_trace_bundle_preserves_scoring_write_boundaries",
      "tests/test_codex_page_readiness_gate.py::test_kpi_performance_readiness_exposes_scoring_write_boundary_without_formal_promotion",
      "tests/test_kpi_performance_governance_record.py",
      "-q"
    )
  } elseif ($PageSlug -eq "news-events") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_news_events_trace_bundle_preserves_analytical_event_boundary",
      "tests/test_codex_page_readiness_gate.py::test_news_events_readiness_exposes_analytical_record_path_without_formal_promotion",
      "tests/test_news_events_governance_record.py",
      "-q"
    )
  } elseif ($PageSlug -eq "platform-config") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_platform_config_trace_bundle_preserves_diagnostic_boundary",
      "tests/test_codex_page_readiness_gate.py::test_platform_config_readiness_exposes_diagnostics_record_path_without_formal_promotion",
      "tests/test_platform_config_governance_record.py",
      "-q"
    )
  } elseif ($PageSlug -eq "team-performance") {
    $mcpContractArgs = @(
      "-m",
      "pytest",
      "tests/test_project_mcp_servers.py::test_team_performance_trace_bundle_preserves_candidate_performance_boundary",
      "tests/test_codex_page_readiness_gate.py::test_team_performance_readiness_exposes_candidate_direct_evidence_without_formal_promotion",
      "tests/test_team_performance_governance_record.py",
      "-q"
    )
  }
  $checks += @(
    @{
      Label = "MCP contract tests"
      WorkingDirectory = $root
      Command = "python"
      Args = $mcpContractArgs
    }
  )
}

if ($PageSlug -eq "dashboard-home") {
  $checks += @(
    @{
      Label = "Dashboard backend snapshot and API contract tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @("-m", "pytest", "tests/test_home_snapshot_endpoint.py", "tests/test_dashboard_api_contract.py", "tests/test_executive_dashboard_endpoints.py", "tests/test_executive_service_contract.py", "-q")
    },
    @{
      Label = "Dashboard frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/DashboardPage.test.tsx",
        "src/features/workbench/pages/useDashboardSnapshotBoundary.test.tsx",
        "src/features/workbench/dashboard/dashboardHomeModel.test.ts",
        "src/features/workbench/dashboard/dashboardCockpitHomeModel.test.ts",
        "src/features/workbench/dashboard/sections/DashboardCockpitHeader.test.tsx"
      )
    }
  )
} elseif ($PageSlug -eq "product-category-pnl") {
  $checks += @(
    @{
      Label = "Product-category backend flow and mapping tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @("-m", "pytest", "tests/test_product_category_pnl_flow.py", "tests/test_product_category_mapping_contract.py", "tests/test_product_category_formula_boundaries.py", "-q")
    },
    @{
      Label = "Product-category frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/ProductCategoryPnlPage.test.tsx",
        "src/test/ProductCategoryBranchSwitcher.test.tsx",
        "src/test/ProductCategoryAdjustmentAuditPage.test.tsx",
        "src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts"
      )
    },
    @{
      Label = "Product-category browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@product-category-pnl"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5891"
      }
    }
  )
} elseif ($PageSlug -eq "balance-analysis") {
  $checks += @(
    @{
      Label = "Balance-analysis backend API and surface tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_balance_analysis_api.py",
        "tests/test_balance_analysis_consumer_surface.py",
        "-q"
      )
    },
    @{
      Label = "Balance-analysis frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/BalanceAnalysisPage.test.tsx"
      )
    },
    @{
      Label = "Balance-analysis browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@balance-analysis"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5892"
      }
    }
  )
} elseif ($PageSlug -eq "decision-items") {
  $checks += @(
    @{
      Label = "Decision Items backend API and write-route auth tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_balance_analysis_api.py",
        "tests/test_balance_analysis_service.py",
        "tests/test_write_route_auth_contract.py",
        "-q"
      )
    },
    @{
      Label = "Decision Items frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/DecisionItemsPage.test.tsx",
        "src/test/DecisionItemsRoute.test.tsx",
        "src/test/decisionItemsPageModel.test.ts"
      )
    },
    @{
      Label = "Decision Items browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@decision-items"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5911"
      }
    }
  )
} elseif ($PageSlug -eq "pnl") {
  $checks += @(
    @{
      Label = "PnL backend API contract tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_pnl_api_contract.py",
        "-q"
      )
    },
    @{
      Label = "PnL frontend route tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/PnlRoutesSmoke.test.tsx"
      )
    },
    @{
      Label = "PnL browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@pnl$"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5893"
      }
    }
  )
} elseif ($PageSlug -eq "pnl-bridge") {
  $checks += @(
    @{
      Label = "PnL Bridge backend contract and boundary tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_pnl_bridge_core.py",
        "tests/test_pnl_bridge_with_curve.py",
        "tests/test_pnl_bridge_fx_translation.py",
        "tests/test_pnl_bridge_roll_down_sign.py",
        "tests/test_pnl_bridge_curve_effects.py",
        "tests/test_pnl_bridge_numeric_migration.py",
        "tests/test_pnl_bridge_service_boundaries.py",
        "-q"
      )
    },
    @{
      Label = "PnL Bridge frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/PnlBridgePage.test.tsx",
        "src/test/PnlRoutesSmoke.test.tsx"
      )
    },
    @{
      Label = "PnL Bridge browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@pnl-bridge"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5894"
      }
    }
  )
} elseif ($PageSlug -eq "risk-tensor") {
  $checks += @(
    @{
      Label = "Risk Tensor backend API, service, materialize, and numeric tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_risk_tensor_api.py",
        "tests/test_risk_tensor_service.py",
        "tests/test_risk_tensor_materialize.py",
        "tests/test_risk_tensor_core.py",
        "tests/test_risk_tensor_numeric_migration.py",
        "tests/test_risk_tensor_repo.py",
        "tests/test_risk_tensor_liquidity.py",
        "-q"
      )
    },
    @{
      Label = "Risk Tensor frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/RiskTensorPage.test.tsx"
      )
    },
    @{
      Label = "Risk Tensor browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@risk-tensor"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5895"
        "VITE_DATA_SOURCE" = "mock"
      }
    }
  )
} elseif ($PageSlug -eq "bond-dashboard") {
  $checks += @(
    @{
      Label = "Bond Dashboard backend API, headline, source-surface, and golden-sample tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_bond_dashboard_api_contract.py",
        "tests/test_bond_dashboard_headlines_contract.py",
        "tests/test_bond_analytics_api.py",
        "tests/test_result_meta_source_surface_followup.py",
        "tests/test_golden_samples_capture_ready.py",
        "-q"
      )
    },
    @{
      Label = "Bond Dashboard frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/BondDashboardPage.test.tsx"
      )
    },
    @{
      Label = "Bond Dashboard browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@bond-dashboard"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5896"
      }
    }
  )
} elseif ($PageSlug -eq "bond-analysis") {
  $checks += @(
    @{
      Label = "Bond Analysis backend analytics, action-attribution, and credit-spread tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_bond_analytics_api.py",
        "tests/test_bond_analytics_service.py",
        "tests/test_bond_analytics_core.py",
        "tests/test_bond_analytics_curve_effects.py",
        "tests/core_finance/test_action_attribution.py",
        "tests/test_credit_spread_analysis.py",
        "-q"
      )
    },
    @{
      Label = "Bond Analysis frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/BondAnalyticsViewContent.test.tsx",
        "src/test/BondAnalyticsView.test.tsx"
      )
    },
    @{
      Label = "Bond Analysis browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@bond-analysis"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5906"
      }
    }
  )
} elseif ($PageSlug -eq "concentration-monitor") {
  $checks += @(
    @{
      Label = "Concentration Monitor backend credit-spread and result-meta tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_bond_analytics_api.py",
        "tests/test_bond_analytics_service.py",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "-q"
      )
    },
    @{
      Label = "Concentration Monitor frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/ConcentrationMonitorPage.test.tsx",
        "src/test/BondAnalyticsClient.test.ts"
      )
    },
    @{
      Label = "Concentration Monitor browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@concentration-monitor"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5907"
      }
    }
  )
} elseif ($PageSlug -eq "cashflow-projection") {
  $checks += @(
    @{
      Label = "Cashflow Projection backend API and result-meta tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_cashflow_projection.py",
        "tests/test_cashflow_projection_numeric_migration.py",
        "tests/test_result_meta_source_surface_followup.py",
        "tests/test_wave5_service_explicit_numeric.py",
        "-q"
      )
    },
    @{
      Label = "Cashflow Projection frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/CashflowProjectionPage.test.tsx",
        "src/features/cashflow-projection/adapters/cashflowProjectionAdapter.test.ts",
        "src/features/cashflow-projection/pages/cashflowProjectionPageModel.test.ts"
      )
    },
    @{
      Label = "Cashflow Projection browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@cashflow-projection"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5908"
      }
    }
  )
} elseif ($PageSlug -eq "team-performance") {
  $checks += @(
    @{
      Label = "Team Performance backend PnL and product-category context tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_pnl_api_contract.py",
        "tests/test_product_category_pnl_flow.py",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "-q"
      )
    },
    @{
      Label = "Team Performance frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/features/team-performance/teamPerformancePageModel.test.ts",
        "src/test/TeamPerformancePage.test.tsx",
        "src/test/LiveRouteRealPageSmoke.test.tsx"
      )
    },
    @{
      Label = "Team Performance route registry test"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/RouteRegistry.test.tsx",
        "-t",
        "renders the team-performance route"
      )
    },
    @{
      Label = "Team Performance browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@team-performance"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5908"
      }
    }
  )
} elseif ($PageSlug -eq "kpi-performance") {
  $checks += @(
    @{
      Label = "KPI Performance backend API, service, and write-route auth tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_kpi_api.py",
        "tests/test_kpi_service.py",
        "tests/test_write_route_auth_contract.py",
        "-q"
      )
    },
    @{
      Label = "KPI Performance frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/KpiPerformancePage.test.tsx",
        "src/test/LiveRouteRealPageSmoke.test.tsx"
      )
    },
    @{
      Label = "KPI Performance browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@kpi-performance"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5912"
      }
    }
  )
} elseif ($PageSlug -eq "platform-config") {
  $checks += @(
    @{
      Label = "Platform Config backend health and source-preview tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_health_endpoints.py",
        "tests/test_source_preview_flow.py",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "-q"
      )
    },
    @{
      Label = "Platform Config frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/PlatformConfigPage.test.tsx",
        "src/test/LiveRouteRealPageSmoke.test.tsx"
      )
    },
    @{
      Label = "Platform Config route registry test"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/RouteRegistry.test.tsx",
        "-t",
        "renders the platform-config route"
      )
    },
    @{
      Label = "Platform Config browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@platform-config"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5909"
      }
    }
  )
} elseif ($PageSlug -eq "news-events") {
  $checks += @(
    @{
      Label = "News Events backend Choice news route and result-meta tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_choice_news_routes.py",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "-q"
      )
    },
    @{
      Label = "News Events frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/NewsEventsPage.test.tsx",
        "src/test/LiveRouteRealPageSmoke.test.tsx"
      )
    },
    @{
      Label = "News Events route registry test"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/RouteRegistry.test.tsx",
        "-t",
        "renders the news-events route"
      )
    },
    @{
      Label = "News Events browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@news-events"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5910"
      }
    }
  )
} elseif ($PageSlug -eq "balance-movement-analysis") {
  $checks += @(
    @{
      Label = "Balance Movement backend API, service, core, materialize, and result-meta tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_accounting_asset_movement_api.py",
        "tests/test_accounting_asset_movement_service.py",
        "tests/test_accounting_asset_movement_core.py",
        "tests/test_accounting_asset_movement_materialize.py",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "-q"
      )
    },
    @{
      Label = "Balance Movement frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/BalanceMovementAnalysisPage.test.tsx"
      )
    },
    @{
      Label = "Balance Movement browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@balance-movement-analysis"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5897"
      }
    }
  )
} elseif ($PageSlug -eq "ledger-pnl") {
  $checks += @(
    @{
      Label = "Ledger PnL backend service and source-contract tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_ledger_pnl_service.py",
        "tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py",
        "-q"
      )
    },
    @{
      Label = "Ledger PnL frontend page tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/LedgerPnlPage.test.tsx"
      )
    },
    @{
      Label = "Ledger PnL frontend route smoke tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/LedgerPnlRoutesSmoke.test.tsx"
      )
    },
    @{
      Label = "Ledger PnL browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@ledger-pnl"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5898"
      }
    }
  )
} elseif ($PageSlug -eq "positions") {
  $checks += @(
    @{
      Label = "Positions backend API contract tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_positions_api_contract.py",
        "-q"
      )
    },
    @{
      Label = "Positions frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/PositionsView.test.tsx",
        "src/test/RouteRegistry.test.tsx",
        "src/test/CustomerDetailModal.test.tsx"
      )
    },
    @{
      Label = "Positions browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@positions"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5899"
      }
    }
  )
} elseif ($PageSlug -eq "operations-analysis") {
  $checks += @(
    @{
      Label = "Operations Analysis backend product-category, balance, and golden-sample tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_product_category_pnl_flow.py",
        "tests/test_product_category_mapping_contract.py",
        "tests/test_balance_analysis_api.py",
        "tests/test_golden_samples_capture_ready.py",
        "-q"
      )
    },
    @{
      Label = "Operations Analysis frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/OperationsAnalysisPage.test.tsx",
        "src/test/OperationsAnalysisPage.governed.test.tsx"
      )
    },
    @{
      Label = "Operations Analysis browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@operations-analysis"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5900"
      }
    }
  )
} elseif ($PageSlug -eq "liability-analytics") {
  $checks += @(
    @{
      Label = "Liability Analytics backend compatibility, envelope, unit, and numeric tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_liability_analytics_api.py",
        "tests/test_liability_analytics_envelope_contract.py",
        "tests/test_liability_analytics_compat_contract.py",
        "tests/test_liability_analytics_unit_semantics.py",
        "tests/test_liability_analytics_numeric_migration.py",
        "-q"
      )
    },
    @{
      Label = "Liability Analytics frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/LiabilityAnalyticsPage.test.tsx",
        "src/features/liability-analytics/adapters/liabilityAdapter.test.ts",
        "src/features/liability-analytics/pages/liabilityAnalyticsPageModel.test.ts"
      )
    },
    @{
      Label = "Liability Analytics browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@liability-analytics"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5901"
      }
    }
  )
} elseif ($PageSlug -eq "market-data") {
  $checks += @(
    @{
      Label = "Market Data backend macro, FX, NCD proxy, Livermore, and result-meta tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "tests/test_market_data_ncd_proxy_api.py",
        "tests/test_market_data_livermore_api.py",
        "tests/test_market_data_livermore_risk_exit_source.py",
        "tests/test_macro_bond_linkage.py",
        "tests/test_fx_analytical_view_api.py",
        "-q"
      )
    },
    @{
      Label = "Market Data frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/MarketDataPage.test.tsx",
        "src/features/market-data/pages/marketDataPageModel.test.ts"
      )
    },
    @{
      Label = "Market Data browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@market-data"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5902"
      }
    }
  )
} elseif ($PageSlug -eq "macro-toolkit") {
  $checks += @(
    @{
      Label = "Macro Toolkit backend read, strategy, refresh, auth, and result-meta tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "tests/test_macro_toolkit_scripts.py",
        "tests/test_macro_toolkit_choice_stock_refresh_overview.py",
        "tests/test_macro_toolkit_factor_snapshot_dates.py",
        "tests/test_macro_toolkit_a_share_risk.py",
        "tests/test_macro_toolkit_shadow_portfolio_report.py",
        "tests/test_macro_query_contract_smoke.py",
        "tests/test_write_route_auth_contract.py",
        "-q"
      )
    },
    @{
      Label = "Macro Toolkit frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/MacroToolkitPage.test.tsx",
        "src/test/macroToolkitClient.test.ts"
      )
    },
    @{
      Label = "Macro Toolkit browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@macro-toolkit"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5903"
      }
    }
  )
} elseif ($PageSlug -eq "stock-analysis") {
  $checks += @(
    @{
      Label = "Stock Analysis backend Livermore observation and diagnostics tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "tests/test_market_data_livermore_api.py",
        "tests/test_market_data_livermore_candidate_history.py",
        "tests/test_market_data_livermore_stock_detail.py",
        "tests/test_market_data_livermore_sector_rank_series.py",
        "tests/test_market_data_livermore_risk_exit_source.py",
        "tests/test_livermore_signal_confluence.py",
        "-q"
      )
    },
    @{
      Label = "Stock Analysis frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/StockAnalysisPage.test.tsx",
        "src/test/StockAnalysisPageModel.test.ts",
        "src/test/StockDetailDrawer.test.tsx",
        "src/features/stock-analysis/lib/buildConsensusSummary.test.ts"
      )
    },
    @{
      Label = "Stock Analysis browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@stock-analysis"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5904"
      }
    }
  )
} elseif ($PageSlug -eq "pnl-attribution") {
  $checks += @(
    @{
      Label = "PnL Attribution backend workbench, numeric, and Campisi tests"
      WorkingDirectory = $root
      Command = "python"
      Args = @(
        "-m",
        "pytest",
        "tests/test_result_meta_on_all_ui_endpoints.py",
        "tests/test_pnl_attribution_api_contract.py",
        "tests/test_pnl_attribution_workbench_contract.py",
        "tests/test_pnl_attribution_service_explicit_numeric.py",
        "tests/test_pnl_attribution_numeric_migration.py",
        "tests/test_campisi_attribution_service.py",
        "tests/test_campisi_formula_golden.py",
        "-q"
      )
    },
    @{
      Label = "PnL Attribution frontend tests"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test",
        "--",
        "src/test/PnlAttributionPage.test.tsx",
        "src/features/pnl-attribution/adapters/pnlAttributionAdapter.test.ts",
        "src/features/pnl-attribution/components/PnlAttributionView.test.ts"
      )
    },
    @{
      Label = "PnL Attribution browser a11y smoke"
      WorkingDirectory = $frontendRoot
      Command = "npm.cmd"
      Args = @(
        "run",
        "test:a11y-smoke",
        "--",
        "--grep",
        "@pnl-attribution"
      )
      Env = @{
        "MOSS_PLAYWRIGHT_USE_WEB_SERVER" = "1"
        "MOSS_PLAYWRIGHT_PORT" = "5905"
      }
    }
  )
} else {
  throw "Unsupported page slug: $PageSlug"
}

$checks += @(
  @{
    Label = "Frontend typecheck"
    WorkingDirectory = $frontendRoot
    Command = "npm.cmd"
    Args = @("run", "typecheck")
  },
  @{
    Label = "Frontend debt audit"
    WorkingDirectory = $frontendRoot
    Command = "npm.cmd"
    Args = @("run", "debt:audit")
  },
  @{
    Label = "Frontend production build"
    WorkingDirectory = $frontendRoot
    Command = "npm.cmd"
    Args = @("run", "build")
  }
)

if ($SkipBrowserSmoke) {
  $checks = @($checks | Where-Object { -not (Test-CodexBrowserSmokeCheck -Check $_) })
}

$checkIndex = 0
foreach ($check in $checks) {
  $checkIndex += 1
  $isPytestCheck = Use-CodexPytestCommand -Check $check
  Set-CodexPlaywrightOutputDir -Check $check

  if (
    -not [string]::IsNullOrWhiteSpace($codexPytestTempRoot) -and
    $isPytestCheck -and
    -not ($check.Args -like "--basetemp=*")
  ) {
    $pytestBaseTemp = Get-CodexPytestBaseTemp -Label $check.Label -Index $checkIndex
    $check["PytestBaseTemp"] = $pytestBaseTemp
    $check.Args = @($check.Args) + "--basetemp=$pytestBaseTemp"
  }

  $argsText = ($check.Args -join " ")
  Write-Output "[$($check.Label)] $($check.Command) $argsText"

  if ($planOnly) {
    continue
  }

  if (
    -not [string]::IsNullOrWhiteSpace($codexPytestTempRoot) -and
    $isPytestCheck -and
    $check.ContainsKey("PytestBaseTemp")
  ) {
    $pytestBaseTempParent = Split-Path -Parent $check["PytestBaseTemp"]
    if (
      -not [string]::IsNullOrWhiteSpace($pytestBaseTempParent) -and
      -not (Test-Path -LiteralPath $pytestBaseTempParent)
    ) {
      New-Item -ItemType Directory -Force -Path $pytestBaseTempParent | Out-Null
    }
  }

  Push-Location $check.WorkingDirectory
  $previousEnv = @{}
  try {
    if ($check.ContainsKey("Env")) {
      foreach ($entry in $check.Env.GetEnumerator()) {
        $previousEnv[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, "Process")
        [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
      }
    }
    & $check.Command @($check.Args)
    $commandSucceeded = $?
    $exitCode = $LASTEXITCODE
    if (-not $commandSucceeded) {
      if ($null -eq $exitCode) {
        $exitCode = 1
      }
      throw "$($check.Label) failed with exit code $exitCode"
    }
  } finally {
    foreach ($entry in $previousEnv.GetEnumerator()) {
      [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
    }
    Pop-Location
  }
}

if ($planOnly) {
  Write-Output "Codex verify page dry run complete. Pass -Run to execute checks."
} else {
  Write-Output "Codex verify page checks passed."
}
