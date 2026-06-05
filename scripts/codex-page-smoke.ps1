param(
  [ValidateSet("dashboard-home", "product-category-pnl")]
  [string]$PageSlug = "product-category-pnl",

  [string]$FrontendBaseUrl = "http://127.0.0.1:5888",
  [string]$ApiBaseUrl = "http://127.0.0.1:7888",
  [switch]$CheckLive
)

$ErrorActionPreference = "Stop"

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
    if ($api -eq "/ui/pnl/product-category/dates") {
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
    if ($null -ne $datesPayload -and $null -ne $datesPayload.result -and $null -ne $datesPayload.result.report_dates) {
      $reportDates = @($datesPayload.result.report_dates)
    }

    if ($reportDates.Count -gt 0) {
      $reportDate = [uri]::EscapeDataString([string]$reportDates[0])
      Invoke-WebRequest -Uri "$ApiBaseUrl$primaryApi`?report_date=$reportDate&view=monthly" -UseBasicParsing | Out-Null
      Write-Output "- Page API reachable: $primaryApi"
    } else {
      Write-Output "- Page API detail skipped: no report_dates returned by /dates"
    }
  }
}
