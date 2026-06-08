param(
  [ValidateSet("dashboard-home", "product-category-pnl", "balance-analysis", "pnl", "pnl-bridge", "risk-tensor", "bond-dashboard", "bond-analysis", "balance-movement-analysis", "ledger-pnl", "positions", "operations-analysis", "liability-analytics", "market-data", "macro-toolkit", "stock-analysis", "pnl-attribution", "concentration-monitor", "team-performance", "platform-config", "news-events")]
  [string]$PageSlug = "product-category-pnl",

  [string]$FrontendBaseUrl = "http://127.0.0.1:5888",
  [string]$ApiBaseUrl = "http://127.0.0.1:7888",
  [switch]$CheckLive
)

$ErrorActionPreference = "Stop"

function Get-ObjectPropertyValue {
  param(
    [object]$Object,
    [string]$Name
  )

  if ($null -eq $Object -or -not ($Object.PSObject.Properties.Name -contains $Name)) {
    return $null
  }
  return $Object.$Name
}

function Get-ReportDatesFromDatesPayload {
  param(
    [object]$DatesPayload
  )

  if ($null -eq $DatesPayload -or $null -eq $DatesPayload.result) {
    return @()
  }

  $result = $DatesPayload.result
  $reportDates = Get-ObjectPropertyValue -Object $result -Name "report_dates"
  if ($null -ne $reportDates) {
    return @($reportDates)
  }

  $dates = Get-ObjectPropertyValue -Object $result -Name "dates"
  if ($null -ne $dates) {
    return @($dates)
  }

  return @()
}

function Assert-BalanceMovementFreshnessGate {
  param(
    [object]$DatesPayload
  )

  if ($null -eq $DatesPayload -or $null -eq $DatesPayload.result) {
    throw "Balance Movement freshness gate failed: /dates returned no result payload."
  }

  $result = $DatesPayload.result
  $meta = $DatesPayload.result_meta
  $status = [string](Get-ObjectPropertyValue -Object $result -Name "freshness_status")
  $latestReadModel = [string](Get-ObjectPropertyValue -Object $result -Name "latest_read_model_report_date")
  $latestUpstream = [string](Get-ObjectPropertyValue -Object $result -Name "latest_upstream_control_report_date")
  $reportDates = @(Get-ReportDatesFromDatesPayload -DatesPayload $DatesPayload)
  $firstSelectable = ""
  if ($reportDates.Count -gt 0) {
    $firstSelectable = [string]$reportDates[0]
  }

  if ([string]::IsNullOrWhiteSpace($status)) {
    throw "Balance Movement freshness gate failed: /dates missing freshness_status. Restart or reload the API before accepting the page."
  }
  if ($status -ne "fresh") {
    throw "Balance Movement freshness gate failed: status=$status; read_model=$latestReadModel; upstream=$latestUpstream; first_selectable=$firstSelectable"
  }
  if (
    [string]::IsNullOrWhiteSpace($latestReadModel) -or
    [string]::IsNullOrWhiteSpace($latestUpstream) -or
    [string]::IsNullOrWhiteSpace($firstSelectable)
  ) {
    throw "Balance Movement freshness gate failed: missing read-model, upstream, or selectable report date."
  }
  if ($latestReadModel -ne $latestUpstream -or $firstSelectable -ne $latestReadModel) {
    throw "Balance Movement freshness gate failed: read_model=$latestReadModel; upstream=$latestUpstream; first_selectable=$firstSelectable"
  }

  $tablesUsed = @()
  if ($null -ne $meta -and $null -ne $meta.tables_used) {
    $tablesUsed = @($meta.tables_used | ForEach-Object { [string]$_ })
  }
  foreach ($expectedTable in @("fact_accounting_asset_movement_monthly", "product_category_pnl_canonical_fact")) {
    if ($tablesUsed -notcontains $expectedTable) {
      throw "Balance Movement freshness gate failed: result_meta.tables_used missing $expectedTable"
    }
  }

  Write-Output "- Balance Movement freshness gate passed: read_model=$latestReadModel; upstream=$latestUpstream; status=$status"
}

if ($PageSlug -eq "dashboard-home") {
  $route = "/"
  $routeAliases = @("/", "/dashboard")
  $primaryApi = "/ui/home/snapshot"
  $supportingApis = @(
    "/ui/home/overview",
    "/ui/home/summary",
    "/api/dashboard/core_metrics",
    "/api/dashboard/daily-changes",
    "/api/bond-dashboard/headline-kpis",
    "/api/bond-analytics/portfolio-headlines",
    "/ui/market-data/rates",
    "/ui/calendar/supply-auctions"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the daily cockpit judgment question.",
    "Confirm /ui/home/snapshot drives report date, main judgment, governance status, domains_missing, domains_effective_date, and result_meta.",
    "Confirm supplemental dashboard, bond, market, and calendar surfaces are visually secondary and respect report_date gating where required.",
    "Confirm analytical basis, partial mode, stale data, fallback, vendor unavailable, loading failure, and mock fallback states are explicit.",
    "Confirm reserved /ui/risk/overview, /ui/home/alerts, and /ui/home/contribution are not rendered as normal first-screen conclusions.",
    "Do not promote homepage aggregate values to formal metric truth without updating metric_dictionary, page contracts, and tests."
  )
} elseif ($PageSlug -eq "product-category-pnl") {
  $route = "/product-category-pnl"
  $routeAliases = @("/product-category-pnl")
  $primaryApi = "/ui/pnl/product-category"
  $supportingApis = @(
    "/ui/pnl/product-category/dates",
    "/ui/pnl/product-category/refresh",
    "/ui/pnl/product-category/refresh-status",
    "/ui/pnl/product-category/manual-adjustments",
    "/ui/pnl/product-category/manual-adjustments/export"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the product-category PnL total question.",
    "Confirm report date selector, monthly/ytd view selector, baseline totals, scenario state, category rows, metadata strip, and audit entry point are visible.",
    "Confirm no data, stale data, fallback, and loading failure states are explicit when triggered.",
    "Confirm result_meta fields remain inspectable: basis, scenario_flag, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Confirm rows stay tied to the paired ledger reconciliation + daily average source chain.",
    "Do not infer rows from ZQTZ holdings-side logic, holdings buckets, or research-style bond categories."
  )
} elseif ($PageSlug -eq "balance-analysis") {
  $route = "/balance-analysis"
  $routeAliases = @("/balance-analysis")
  $primaryApi = "/ui/balance-analysis/overview"
  $supportingApis = @(
    "/ui/balance-analysis/dates",
    "/ui/balance-analysis",
    "/ui/balance-analysis/summary",
    "/ui/balance-analysis/summary-by-basis",
    "/ui/balance-analysis/workbook",
    "/ui/balance-analysis/refresh",
    "/ui/balance-analysis/refresh-status"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the formal balance truth question.",
    "Confirm report date selector, position scope, currency basis, overview totals, formal meta panel, and workbook navigation are visible.",
    "Confirm no data, stale data, fallback, and loading failure states are explicit when triggered.",
    "Confirm result_meta fields remain inspectable: basis, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Confirm overview totals stay tied to fact_formal_zqtz_balance_daily and fact_formal_tyw_balance_daily.",
    "Do not use balance movement explanation, positions totals, or product-category PnL logic to replace PAGE-BALANCE-001 formal balance truth."
  )
} elseif ($PageSlug -eq "pnl") {
  $route = "/pnl"
  $routeAliases = @("/pnl")
  $primaryApi = "/api/pnl/overview"
  $supportingApis = @(
    "/api/pnl/dates",
    "/api/pnl/v1-data",
    "/api/pnl/data",
    "/api/data/refresh_pnl",
    "/api/data/import_status/pnl"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the formal PnL truth question.",
    "Confirm report month selector, PnL filter toolbar, total PnL readout, 514/516/517 decomposition, source mix, and detail rows are visible.",
    "Confirm no data, stale data, fallback, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable through the formal detail route: basis, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Confirm overview totals stay tied to fact_formal_pnl_fi and fact_nonstd_pnl_bridge via /api/pnl/overview and /api/pnl/v1-data.",
    "Do not replace PAGE-PNL-001 formal PnL truth with PnL Bridge reconciliation, executive overlays, product-category operating PnL, or frontend recomputation."
  )
} elseif ($PageSlug -eq "pnl-bridge") {
  $route = "/pnl-bridge"
  $routeAliases = @("/pnl-bridge")
  $primaryApi = "/api/pnl/bridge"
  $supportingApis = @(
    "/api/pnl/dates",
    "/api/data/refresh_pnl",
    "/api/data/import_status/pnl"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the PnL Bridge closure question.",
    "Confirm report date selector, closure conclusion, summary cards, waterfall card, detail table, bridge warnings, and result meta panel are visible.",
    "Confirm no data, stale data, fallback, bridge warnings, curve fallback, vendor stale, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable: basis, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Confirm bridge values stay tied to fact_formal_pnl_fi, fact_nonstd_pnl_bridge, current/prior balance lineage, yield curves, and FX rate evidence.",
    "Do not use PnL Bridge to replace PAGE-PNL-001 formal PnL detail truth, ledger-level PnL evidence, or frontend recomputation."
  )
} elseif ($PageSlug -eq "risk-tensor") {
  $route = "/risk-tensor"
  $routeAliases = @("/risk-tensor")
  $primaryApi = "/api/risk/tensor"
  $supportingApis = @(
    "/api/risk/tensor/dates"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the Risk Tensor formal truth question.",
    "Confirm report date selector, main risk conclusion, regulatory_dv01, DV01/KRD/CS01/convexity/liquidity/HHI cards, warnings, and result meta panel are visible.",
    "Confirm no data, stale data, fallback, blocked-date, upstream-missing, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable: basis, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Confirm risk values stay tied to fact_formal_risk_tensor_daily, bond analytics lineage, TYW liability lineage, and approved golden samples.",
    "Do not replace PAGE-RISK-001 formal risk tensor truth with dashboard summaries, bond analytics fragments, or frontend recomputation."
  )
} elseif ($PageSlug -eq "bond-dashboard") {
  $route = "/bond-dashboard"
  $routeAliases = @("/bond-dashboard", "/assets", "/bonds")
  $primaryApi = "/api/bond-dashboard/headline-kpis"
  $supportingApis = @(
    "/api/bond-dashboard/dates",
    "/api/bond-dashboard/asset-structure",
    "/api/bond-dashboard/yield-distribution",
    "/api/bond-dashboard/portfolio-comparison",
    "/api/bond-dashboard/spread-analysis",
    "/api/bond-dashboard/maturity-structure",
    "/api/bond-dashboard/industry-distribution",
    "/api/bond-dashboard/risk-indicators",
    "/api/bond-dashboard/business-type-metrics"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the candidate bond-dashboard headline question.",
    "Confirm report date selector, headline KPIs, asset structure, risk indicators, candidate-boundary notice, and result meta/source badges are visible.",
    "Confirm no data, stale data, fallback, vendor degradation, loading failure, and empty headline states are explicit when triggered.",
    "Confirm result_meta remains inspectable: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_surface, source_version, rule_version, cache_version, generated_at.",
    "Confirm headline and risk values stay tied to fact_formal_bond_analytics_daily and GS-BOND-HEADLINE-A page DTO evidence only.",
    "Do not promote MTR-BOND candidate metrics, balance-analysis metrics, or risk-tensor metrics from bond-dashboard display evidence."
  )
} elseif ($PageSlug -eq "bond-analysis") {
  $route = "/bond-analysis"
  $routeAliases = @("/bond-analysis", "/bond-analytics-advanced")
  $primaryApi = "/api/bond-analytics/action-attribution"
  $supportingApis = @(
    "/api/bond-analytics/dates",
    "/api/bond-analytics/return-decomposition",
    "/api/bond-analytics/benchmark-excess",
    "/api/bond-analytics/krd-curve-risk",
    "/api/bond-analytics/dv01-risk",
    "/api/bond-analytics/dv01-reconciliation",
    "/api/bond-analytics/dv01-movement",
    "/api/bond-analytics/dv01-action-plan",
    "/api/bond-analytics/dv01-limit-config-status",
    "/api/bond-analytics/accounting-class-audit",
    "/api/bond-analytics/credit-spread-migration",
    "/api/bond-analytics/portfolio-headlines",
    "/api/bond-analytics/top-holdings",
    "/api/bond-analytics/position-changes",
    "/api/bond-analytics/yield-curve-term-structure",
    "/api/credit-spread-analysis/detail"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the fixed-income action attribution and risk decision question.",
    "Confirm report date selector, period selector, FI risk decision cockpit, trust state, warning state, next action, source details, and result_meta-driven data-quality banner are visible.",
    "Confirm GAP-BOND-ANALYSIS-PAGE stays a route-specific Gate I gap; no direct page contract, golden sample, governance validation, or owner approval is implied.",
    "Confirm PAGE-BOND-001, GS-BOND-HEADLINE-A, and MTR-BOND-001 through MTR-BOND-004 are not used to certify /bond-analysis.",
    "Confirm fixed-income units and states remain inspectable: DV01, duration/KRD, yield/YTM %, bp movement, market value scale, accounting class, report date, stale/fallback/no-data, and formal_use_allowed.",
    "Do not promote action-attribution PnL, DV01, duration, KRD, credit-spread, holdings, yield, or accounting-class values into formal metric truth without direct /bond-analysis contract evidence."
  )
} elseif ($PageSlug -eq "concentration-monitor") {
  $route = "/concentration-monitor"
  $routeAliases = @("/concentration-monitor")
  $primaryApi = "/api/bond-analytics/credit-spread-migration"
  $supportingApis = @(
    "/api/bond-analytics/dates"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the concentration-monitor candidate risk question.",
    "Confirm report date selector, issuer HHI, top5 concentration, credit weight, AA-and-below ratio, limit comparison rows, source evidence, and result meta/source badges are visible.",
    "Confirm PAGE-CONTRACT-PENDING:/concentration-monitor and MTR-CON candidate boundaries remain visible.",
    "Confirm no data, stale data, fallback, missing-source, vendor degradation, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_surface, source_version, rule_version, cache_version, tables_used, evidence_rows, generated_at.",
    "Do not treat issuer HHI, top5 concentration, credit weight, AA-and-below ratio, or frontend limit comparisons as formal risk truth or certified concentration-limit approval."
  )
} elseif ($PageSlug -eq "team-performance") {
  $route = "/team-performance"
  $routeAliases = @("/team-performance")
  $primaryApi = "/api/pnl/by-business-ytd"
  $supportingApis = @(
    "/api/pnl/by-business-monthly",
    "/api/pnl/by-business",
    "/ui/pnl/product-category",
    "/ui/pnl/product-category/dates"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the candidate team-performance mapping question.",
    "Confirm report year/date selectors, mapped team count, summary cards, center matrix, Q1 caliber panel, warning banner, result_meta, and candidate evidence panels are visible.",
    "Confirm PAGE-CONTRACT-PENDING:/team-performance and MTR-TEAM-001 candidate boundaries remain visible.",
    "Confirm no data, stale data, fallback, pending split references, workbook-local source warnings, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable for by-business/product-category context: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_surface, source_version, rule_version, cache_version, generated_at.",
    "Do not treat workbook score, mapped PnL, Q1 split references, or team mapping as formal KPI truth, formal PnL truth, or owner-approved performance allocation."
  )
} elseif ($PageSlug -eq "platform-config") {
  $route = "/platform-config"
  $routeAliases = @("/platform-config")
  $primaryApi = "/ui/preview/source-foundation"
  $supportingApis = @(
    "/health/ready",
    "/health/live",
    "/health",
    "/ui/preview/source-foundation/history",
    "/ui/preview/source-foundation/refresh-status"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the diagnostic platform/source question.",
    "Confirm system status, live probe, summary probe, environment, source count, abnormal source count, manual review rows, health cards, and source table are visible.",
    "Confirm PAGE-CONTRACT-PENDING:/platform-config and MTR-PLT-001 through MTR-PLT-003 candidate boundaries remain visible.",
    "Confirm no data, stale data, fallback, source-preview unavailable, health failure, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable for source foundation: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_surface, source_version, rule_version, cache_version, generated_at.",
    "Do not treat system status, health probes, environment text, source count, abnormal sources, or manual review rows as business metric truth or data-quality approval."
  )
} elseif ($PageSlug -eq "news-events") {
  $route = "/news-events"
  $routeAliases = @("/news-events")
  $primaryApi = "/ui/news/choice-events/latest"
  $supportingApis = @()
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the analytical news/event context question.",
    "Confirm topic filter, stock filter, error-only filter, total count, current page count, error count, active topic, event table, pagination, and result_meta/source badges are visible.",
    "Confirm PAGE-CONTRACT-PENDING:/news-events and GAP-NEWS-EVENTS-PAGE analytical temporary-exception boundaries remain visible.",
    "Confirm no data, stale data, fallback, missing choice_news_event table, permission failure, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable for Choice news events: basis=analytical, formal_use_allowed=false, result_kind=news.choice.latest, source_surface, source_version, rule_version, cache_version, tables_used, generated_at.",
    "Do not treat news headlines, topic counts, event counts, stock filters, or error rows as formal metric truth, trading instruction, source data-quality approval, or business-owner-approved evidence."
  )
} elseif ($PageSlug -eq "balance-movement-analysis") {
  $route = "/balance-movement-analysis"
  $routeAliases = @("/balance-movement-analysis")
  $primaryApi = "/ui/balance-movement-analysis"
  $supportingApis = @(
    "/ui/balance-movement-analysis/dates",
    "/ui/balance-movement-analysis/refresh"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the candidate balance movement explanation question.",
    "Confirm report date selector, currency basis, movement conclusion, summary cards, reconciliation strip, diagnostics, and result meta/source badges are visible.",
    "Confirm live /dates freshness gate exposes freshness_status, read-model date, upstream control date, and both source tables before accepting a full-run closure.",
    "Confirm no data, stale data, fallback, low-coverage, residual, unsupported valuation, refresh failure, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_surface, source_version, rule_version, cache_version, generated_at.",
    "Confirm movement values stay tied to fact_accounting_asset_movement_monthly and fact_formal_zqtz_balance_daily for the selected report date and CNX currency basis.",
    "Do not promote MTR-BMV candidate metrics, replace PAGE-BALANCE-001 formal balance truth, or infer rows from ZQTZ holdings-side logic."
  )
} elseif ($PageSlug -eq "ledger-pnl") {
  $route = "/ledger-pnl"
  $routeAliases = @("/ledger-pnl")
  $primaryApi = "/api/ledger-pnl/summary"
  $supportingApis = @(
    "/api/ledger-pnl/dates",
    "/api/ledger-pnl/data",
    "/api/ledger-pnl/formal-financial-indicators"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the ledger-account PnL candidate display question.",
    "Confirm report date selector, currency filter, summary cards, detail tables, formal financial indicator source-contract panel, and result meta/source badges are visible.",
    "Confirm no data, stale data, fallback, missing-source, formal_pending, vendor degradation, and loading failure states are explicit when triggered.",
    "Confirm result_meta remains inspectable: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_surface, source_version, rule_version, cache_version, generated_at.",
    "Confirm ledger summary values stay tied to /api/ledger-pnl/summary, /api/ledger-pnl/data, and the qdb_general_ledger_workbook logical source contract.",
    "Do not promote MTR-LPN candidate display metrics, formal_pending financial indicators, or candidate_qdb_aligned values to formal metric truth."
  )
} elseif ($PageSlug -eq "positions") {
  $route = "/positions"
  $routeAliases = @("/positions")
  $primaryApi = "/api/positions/bonds"
  $supportingApis = @(
    "/ui/balance-analysis/dates",
    "/api/positions/bonds/sub_types",
    "/api/positions/interbank/product_types",
    "/api/positions/interbank",
    "/api/positions/counterparty/bonds",
    "/api/positions/counterparty/interbank/split",
    "/api/positions/stats/rating",
    "/api/positions/stats/industry",
    "/api/positions/customer/details",
    "/api/positions/customer/trend"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the positions list candidate display question.",
    "Confirm report date selector, bond/interbank tabs, list totals, candidate-boundary notice, table rows, distribution cards, and result meta/source badges are visible.",
    "Confirm no data, stale data, fallback, missing report_date, loading failure, empty list, and customer drilldown states are explicit when triggered.",
    "Confirm result_meta remains inspectable: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_surface, source_version, rule_version, cache_version, generated_at.",
    "Confirm list and stat values stay tied to /api/positions/bonds, /api/positions/interbank, positions_snapshot, zqtz_bond_daily_snapshot, and tyw_interbank_daily_snapshot for the selected report_date.",
    "Do not promote MTR-POS candidate display metrics, filter context fields, or positions list totals into formal metric truth without approved samples and contracts."
  )
} elseif ($PageSlug -eq "operations-analysis") {
  $route = "/operations-analysis"
  $routeAliases = @("/operations-analysis")
  $primaryApi = "/ui/pnl/product-category"
  $supportingApis = @(
    "/ui/pnl/product-category/dates",
    "/ui/balance-analysis/dates",
    "/ui/balance-analysis/overview",
    "/ui/preview/source-foundation",
    "/ui/preview/macro-foundation",
    "/ui/macro/choice-series/latest",
    "/ui/market-data/fx/formal-status",
    "/ui/news/choice-events/latest"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the operations mixed-source entry question.",
    "Confirm product-category headline cards, balance topic-entry evidence, source preview, macro, FX, news, result meta, and temporary-exception boundaries are visible.",
    "Confirm no data, stale data, fallback, vendor unavailable, mock-mode, static-example, and loading failure states are explicit when triggered.",
    "Confirm product-category headline values stay tied to MTR-PCP-001 through MTR-PCP-003 and GS-PROD-CAT-PNL-A.",
    "Confirm balance overview remains supplemental topic-entry evidence and routes users to /balance-analysis for PAGE-BALANCE-001 workbook/detail truth.",
    "Do not create or promote MTR-OPS metrics, source preview, macro, FX, Choice news, watch items, or calendar examples into formal business metric truth."
  )
} elseif ($PageSlug -eq "liability-analytics") {
  $route = "/liability-analytics"
  $routeAliases = @("/liability-analytics")
  $primaryApi = "/api/risk/buckets"
  $supportingApis = @(
    "/api/analysis/yield_metrics",
    "/api/analysis/yield-by-period",
    "/api/analysis/liabilities/counterparty",
    "/api/liabilities/monthly",
    "/ui/liability/business-context",
    "/api/analysis/liabilities/cockpit-warnings",
    "/api/analysis/liabilities/contribution-split",
    "/ui/balance-analysis/dates",
    "/ui/balance-analysis/overview",
    "/api/analysis/adb/monthly"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the liability compatibility analytics question.",
    "Confirm report date selector, daily/monthly tabs, liability KPIs, counterparty evidence, monthly snapshots, business context, warnings, and result meta boundaries are visible.",
    "Confirm no data, stale data, fallback, missing result_meta, compatibility, synthetic, pending-definition, and loading failure states are explicit when triggered.",
    "Confirm MTR-LIAB-001..007 and MTR-LIAB compatibility sections remain governed-mixed-source / compatibility analytical, not formal balance/PnL truth.",
    "Confirm values stay tied to /api/risk/buckets, /api/analysis/yield_metrics, /api/analysis/liabilities/counterparty, /api/liabilities/monthly, and /api/analysis/adb/monthly for the selected report_date.",
    "Do not perform frontend recomputation of liability cost, NIM, maturity pressure, counterparty concentration, monthly averages, or bucket definitions; keep result_meta/no-data/fallback/stale boundaries visible."
  )
} elseif ($PageSlug -eq "market-data") {
  $route = "/market-data"
  $routeAliases = @("/market-data")
  $primaryApi = "/ui/preview/macro-foundation"
  $supportingApis = @(
    "/ui/market-data/rates",
    "/ui/macro/choice-series/latest",
    "/ui/market-data/fx/formal-status",
    "/ui/market-data/fx/analytical",
    "/ui/market-data/ncd-funding-proxy",
    "/api/macro-bond-linkage",
    "/ui/market-data/livermore",
    "/ui/market-data/livermore/stock-detail",
    "/ui/market-data/livermore/candidate-history",
    "/ui/market-data/livermore/sector-rank-series"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the market-data mixed-source question.",
    "Confirm macro preview, formal rates fragment, FX analytical/status, NCD proxy, macro-bond linkage, Livermore analytical, and source-pending terminal sections are visible as separate evidence surfaces.",
    "Confirm MTR-MKT-001 remains pending/candidate and the page does not claim full-page formal truth from macro preview, formal rates fragment, FX analytical, NCD proxy, or Livermore analytical outputs.",
    "Confirm no data, stale data, fallback, blocked, source-pending, proxy, analytical, and loading failure states are explicit when triggered.",
    "Confirm result_meta fields remain inspectable on live surfaces: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Do not fill missing rate quote, money market, bond futures, bond trade detail, credit trade, FX, or macro rows with static demo backfill in real mode."
  )
} elseif ($PageSlug -eq "macro-toolkit") {
  $route = "/macro-toolkit"
  $routeAliases = @("/macro-toolkit")
  $primaryApi = "/ui/macro/toolkit/analysis"
  $supportingApis = @(
    "/ui/macro/toolkit/analysis/strategy-summaries",
    "/ui/macro/toolkit/scripts",
    "/ui/macro/toolkit/adversarial-signal",
    "/ui/macro/toolkit/choice-stock/refresh-status"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the macro-toolkit tooling observation question.",
    "Confirm analysis cards, strategy summaries, script registry, operation console, refresh status, source/version/run_id evidence, and result_meta boundaries are visible as tooling evidence.",
    "Confirm PAGE-MACRO-TOOLKIT-001 stays tooling/analysis only and does not claim formal metric truth from macro analysis, script registry, refresh status, strategy summaries, or operation/script outputs.",
    "Confirm no data, stale data, fallback, source gap, permission failure, deferred-section, and loading failure states are explicit when triggered.",
    "Confirm result_meta fields remain inspectable on live read surfaces: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Do not treat analysis cards, strategies, script outputs, vendor reads, refresh counts, source/version/run_id, coverage.hit_rate, MTR-MACRO placeholders, or operation/script outputs as investment recommendations or executable trade signals."
  )
} elseif ($PageSlug -eq "stock-analysis") {
  $route = "/stock-analysis"
  $routeAliases = @("/stock-analysis")
  $primaryApi = "/ui/market-data/livermore"
  $supportingApis = @(
    "/ui/market-data/livermore/signal-confluence",
    "/ui/market-data/livermore/stock-detail",
    "/ui/market-data/livermore/candidate-history",
    "/ui/market-data/livermore/strategy-score",
    "/ui/market-data/livermore/strategy-optimization",
    "/ui/market-data/livermore/cycle-proxy-backtest",
    "/ui/market-data/livermore/candidate-history-portfolio-backtest",
    "/ui/market-data/livermore/sector-rank-series"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the stock-analysis observational review question.",
    "Confirm Livermore analytical candidates, signal confluence, stock detail, candidate history, strategy score, optimization, proxy backtests, sector ranking, source badges, and result_meta boundaries are visible as observation evidence.",
    "Confirm GAP-STOCK-ANALYSIS-PAGE stays observational only; no PAGE-STOCK formal contract, golden sample, or full-page formal metric truth is claimed.",
    "Confirm no data, stale data, fallback, pending source, low-coverage, analytical-only, and loading failure states are explicit when triggered.",
    "Confirm result_meta fields remain inspectable on live read surfaces: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Do not create trading instructions, allocation guidance, position-change commands, demo backfill in real mode, or promotion of Livermore candidates, signal confluence, sector ranking, strategy scores, or proxy backtests into formal metric truth."
  )
} elseif ($PageSlug -eq "pnl-attribution") {
  $route = "/pnl-attribution"
  $routeAliases = @("/pnl-attribution")
  $primaryApi = "/api/pnl-attribution/volume-rate"
  $supportingApis = @(
    "/api/pnl-attribution/tpl-market",
    "/api/pnl-attribution/composition",
    "/api/pnl-attribution/summary",
    "/api/pnl-attribution/advanced/carry-rolldown",
    "/api/pnl-attribution/advanced/spread",
    "/api/pnl-attribution/advanced/krd",
    "/api/pnl-attribution/advanced/summary",
    "/api/pnl-attribution/advanced/campisi",
    "/api/pnl-attribution/campisi/four-effects",
    "/api/pnl-attribution/campisi/enhanced",
    "/api/pnl-attribution/campisi/maturity-buckets",
    "/api/pnl-attribution/campisi/decision-grade"
  )
  $checklist = @(
    "Open the route with Playwright MCP and confirm the first screen answers the PnL Attribution Workbench candidate closure question.",
    "Confirm MTR-PAT volume/rate, TPL-market, composition, advanced carry/rolldown, spread, KRD, Campisi, source badges, and result_meta boundaries are visible as candidate workbench evidence.",
    "Confirm PAGE-PNL-ATTR-WB-001 stays candidate_or_pending with formal_use_allowed false; it must not replace the formal PnL overview or merge with the executive analytical overlay.",
    "Confirm no data, stale data, fallback, blocked, metric-definition-pending, no direct page governance, missing golden sample, and loading failure states are explicit when triggered.",
    "Confirm result_meta fields remain inspectable on live read surfaces: basis, formal_use_allowed, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at.",
    "Confirm frontend recomputation is not introduced for MTR-PAT values, ZQTZ holdings-side logic, Campisi effects, or advanced attribution summaries; displayed values must stay API/adapter driven."
  )
} else {
  throw "Unsupported page slug: $PageSlug"
}

Write-Output "Codex page smoke: $PageSlug"
Write-Output "Frontend route: $FrontendBaseUrl$route"
Write-Output "Route aliases:"
foreach ($alias in $routeAliases) {
  Write-Output "- $FrontendBaseUrl$alias"
}
Write-Output "Primary API: $ApiBaseUrl$primaryApi"
Write-Output "Supporting APIs:"
foreach ($api in $supportingApis) {
  Write-Output "- $ApiBaseUrl$api"
}

Write-Output "Smoke checklist:"
foreach ($item in $checklist) {
  Write-Output "- $item"
}

if ($CheckLive) {
  Write-Output "Live checks:"
  Invoke-WebRequest -Uri "$ApiBaseUrl/health" -UseBasicParsing | Out-Null
  Write-Output "- API health reachable"
  foreach ($alias in $routeAliases) {
    Invoke-WebRequest -Uri "$FrontendBaseUrl$alias" -UseBasicParsing | Out-Null
    Write-Output "- Frontend route reachable: $alias"
  }

  $datesPayload = $null
  foreach ($api in $supportingApis) {
    if ($api -eq "/ui/pnl/product-category/dates" -or $api -eq "/ui/balance-analysis/dates" -or $api -eq "/api/pnl/dates" -or $api -eq "/api/risk/tensor/dates" -or $api -eq "/api/bond-dashboard/dates" -or $api -eq "/api/bond-analytics/dates" -or $api -eq "/ui/balance-movement-analysis/dates" -or $api -eq "/api/ledger-pnl/dates") {
      $datesPayload = Invoke-RestMethod -Uri "$ApiBaseUrl$api"
      Write-Output "- Page API reachable: $api"
    } else {
      Write-Output "- Page API live check skipped (may require parameters, external data, or mutation): $api"
    }
  }

  if ($PageSlug -eq "dashboard-home") {
    $snapshotPayload = Invoke-RestMethod -Uri "$ApiBaseUrl$primaryApi"
    Write-Output "- Page API reachable: $primaryApi"
    $snapshotReportDate = $null
    if ($null -ne $snapshotPayload -and $null -ne $snapshotPayload.result -and $null -ne $snapshotPayload.result.report_date) {
      $snapshotReportDate = [string]$snapshotPayload.result.report_date
    }

    if ([string]::IsNullOrWhiteSpace($snapshotReportDate)) {
      Write-Output "- Supplemental API probe skipped: /ui/home/snapshot returned no report_date"
    } else {
      $escapedReportDate = [uri]::EscapeDataString($snapshotReportDate)
      $supplementalProbes = @(
        "/api/dashboard/core_metrics?report_date=$escapedReportDate",
        "/api/dashboard/daily-changes?report_date=$escapedReportDate",
        "/api/bond-dashboard/headline-kpis?report_date=$escapedReportDate",
        "/api/bond-analytics/portfolio-headlines?report_date=$escapedReportDate",
        "/ui/market-data/rates",
        "/ui/calendar/supply-auctions?limit=1"
      )
      foreach ($probe in $supplementalProbes) {
        try {
          Invoke-WebRequest -Uri "$ApiBaseUrl$probe" -UseBasicParsing | Out-Null
          Write-Output "- Supplemental API probe reachable: $probe"
        } catch {
          Write-Output "- Supplemental API probe warning: $probe ($($_.Exception.Message))"
        }
      }
    }
  } else {
    $reportDates = @()
    if ($PageSlug -eq "balance-movement-analysis") {
      Assert-BalanceMovementFreshnessGate -DatesPayload $datesPayload
    }
    $reportDates = @(Get-ReportDatesFromDatesPayload -DatesPayload $datesPayload)

    if ($reportDates.Count -gt 0) {
      $reportDate = [uri]::EscapeDataString([string]$reportDates[0])
      if ($PageSlug -eq "product-category-pnl") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate&view=monthly" -UseBasicParsing | Out-Null
      } elseif ($PageSlug -eq "pnl") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/pnl/v1-data`?date=$reportDate" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /api/pnl/v1-data"
      } elseif ($PageSlug -eq "pnl-bridge") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate" -UseBasicParsing | Out-Null
      } elseif ($PageSlug -eq "risk-tensor") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate" -UseBasicParsing | Out-Null
      } elseif ($PageSlug -eq "bond-dashboard") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate" -UseBasicParsing | Out-Null
      } elseif ($PageSlug -eq "bond-analysis") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate&period_type=MoM" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/bond-analytics/dv01-risk`?report_date=$reportDate&accounting_class=OCI&top_n=20&shock_bps=1,10,25,50" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/bond-analytics/krd-curve-risk`?report_date=$reportDate" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/bond-analytics/portfolio-headlines`?report_date=$reportDate" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /api/bond-analytics/dv01-risk"
        Write-Output "- Page API reachable: /api/bond-analytics/krd-curve-risk"
        Write-Output "- Page API reachable: /api/bond-analytics/portfolio-headlines"
      } elseif ($PageSlug -eq "concentration-monitor") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate" -UseBasicParsing | Out-Null
      } elseif ($PageSlug -eq "team-performance") {
        $reportYear = ([string]$reportDates[0]).Substring(0, 4)
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?year=$reportYear&report_date=$reportDate" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/pnl/product-category`?report_date=$reportDate&view=monthly" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /ui/pnl/product-category"
      } elseif ($PageSlug -eq "platform-config") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/health/ready" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/health/live" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/health" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/preview/source-foundation/refresh-status" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /health/ready"
        Write-Output "- Page API reachable: /health/live"
        Write-Output "- Page API reachable: /health"
        Write-Output "- Page API reachable: /ui/preview/source-foundation/refresh-status"
      } elseif ($PageSlug -eq "balance-movement-analysis") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate&currency_basis=CNX" -UseBasicParsing | Out-Null
      } elseif ($PageSlug -eq "ledger-pnl") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?date=$reportDate" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/ledger-pnl/data`?date=$reportDate" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /api/ledger-pnl/data"
      } elseif ($PageSlug -eq "positions") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate&page=1&page_size=10" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/positions/interbank`?report_date=$reportDate&page=1&page_size=10" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /api/positions/interbank"
      } elseif ($PageSlug -eq "operations-analysis") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate&view=monthly" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/balance-analysis/overview`?report_date=$reportDate&position_scope=all&currency_basis=CNY" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /ui/balance-analysis/overview"
      } elseif ($PageSlug -eq "liability-analytics") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/analysis/yield_metrics`?report_date=$reportDate" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/analysis/liabilities/counterparty`?report_date=$reportDate" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /api/analysis/yield_metrics"
        Write-Output "- Page API reachable: /api/analysis/liabilities/counterparty"
      } elseif ($PageSlug -eq "market-data") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/rates" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/ncd-funding-proxy" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/livermore" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /ui/market-data/rates"
        Write-Output "- Page API reachable: /ui/market-data/ncd-funding-proxy"
        Write-Output "- Page API reachable: /ui/market-data/livermore"
      } elseif ($PageSlug -eq "macro-toolkit") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?detail=core" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/macro/toolkit/analysis/strategy-summaries" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/macro/toolkit/scripts" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/macro/toolkit/choice-stock/refresh-status" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /ui/macro/toolkit/analysis/strategy-summaries"
        Write-Output "- Page API reachable: /ui/macro/toolkit/scripts"
        Write-Output "- Page API reachable: /ui/macro/toolkit/choice-stock/refresh-status"
      } elseif ($PageSlug -eq "stock-analysis") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/livermore/signal-confluence" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/livermore/strategy-score" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/livermore/sector-rank-series" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /ui/market-data/livermore/signal-confluence"
        Write-Output "- Page API reachable: /ui/market-data/livermore/strategy-score"
        Write-Output "- Page API reachable: /ui/market-data/livermore/sector-rank-series"
      } elseif ($PageSlug -eq "pnl-attribution") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/pnl-attribution/tpl-market" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/pnl-attribution/composition" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/pnl-attribution/advanced/summary" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: /api/pnl-attribution/tpl-market"
        Write-Output "- Page API reachable: /api/pnl-attribution/composition"
        Write-Output "- Page API reachable: /api/pnl-attribution/advanced/summary"
      } else {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate&position_scope=all&currency_basis=CNY" -UseBasicParsing | Out-Null
      }
      Write-Output "- Page API reachable: $primaryApi"
    } else {
      if ($PageSlug -eq "macro-toolkit") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?detail=core" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/macro/toolkit/analysis/strategy-summaries" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/macro/toolkit/scripts" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/macro/toolkit/choice-stock/refresh-status" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: $primaryApi"
        Write-Output "- Page API reachable: /ui/macro/toolkit/analysis/strategy-summaries"
        Write-Output "- Page API reachable: /ui/macro/toolkit/scripts"
        Write-Output "- Page API reachable: /ui/macro/toolkit/choice-stock/refresh-status"
      } elseif ($PageSlug -eq "stock-analysis") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/livermore/signal-confluence" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/livermore/strategy-score" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/market-data/livermore/sector-rank-series" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: $primaryApi"
        Write-Output "- Page API reachable: /ui/market-data/livermore/signal-confluence"
        Write-Output "- Page API reachable: /ui/market-data/livermore/strategy-score"
        Write-Output "- Page API reachable: /ui/market-data/livermore/sector-rank-series"
      } elseif ($PageSlug -eq "pnl-attribution") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/pnl-attribution/tpl-market" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/pnl-attribution/composition" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/api/pnl-attribution/advanced/summary" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: $primaryApi"
        Write-Output "- Page API reachable: /api/pnl-attribution/tpl-market"
        Write-Output "- Page API reachable: /api/pnl-attribution/composition"
        Write-Output "- Page API reachable: /api/pnl-attribution/advanced/summary"
      } elseif ($PageSlug -eq "platform-config") {
        Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/health/ready" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/health/live" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/health" -UseBasicParsing | Out-Null
        Invoke-WebRequest -Uri "$ApiBaseUrl/ui/preview/source-foundation/refresh-status" -UseBasicParsing | Out-Null
        Write-Output "- Page API reachable: $primaryApi"
        Write-Output "- Page API reachable: /health/ready"
        Write-Output "- Page API reachable: /health/live"
        Write-Output "- Page API reachable: /health"
        Write-Output "- Page API reachable: /ui/preview/source-foundation/refresh-status"
      } else {
        Write-Output "- Page API detail skipped: no dates returned by /dates"
      }
    }
  }
}
