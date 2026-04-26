param(
  [ValidateSet("product-category-pnl")]
  [string]$PageSlug = "product-category-pnl",

  [string]$FrontendBaseUrl = "http://127.0.0.1:5888",
  [string]$ApiBaseUrl = "http://127.0.0.1:7888",
  [switch]$CheckLive
)

$ErrorActionPreference = "Stop"

if ($PageSlug -ne "product-category-pnl") {
  throw "Unsupported page slug: $PageSlug"
}

$route = "/product-category-pnl"
$primaryApi = "/ui/pnl/product-category"
$supportingApis = @(
  "/ui/pnl/product-category/dates",
  "/ui/pnl/product-category/refresh",
  "/ui/pnl/product-category/refresh-status",
  "/ui/pnl/product-category/manual-adjustments",
  "/ui/pnl/product-category/manual-adjustments/export"
)

Write-Output "Codex page smoke: $PageSlug"
Write-Output "Frontend route: $FrontendBaseUrl$route"
Write-Output "Primary API: $ApiBaseUrl$primaryApi"
Write-Output "Supporting APIs:"
foreach ($api in $supportingApis) {
  Write-Output "- $ApiBaseUrl$api"
}

Write-Output "Smoke checklist:"
Write-Output "- Open the route with Playwright MCP and confirm the first screen answers the product-category PnL total question."
Write-Output "- Confirm report date selector, monthly/ytd view selector, baseline totals, scenario state, category rows, metadata strip, and audit entry point are visible."
Write-Output "- Confirm no data, stale data, fallback, and loading failure states are explicit when triggered."
Write-Output "- Confirm result_meta fields remain inspectable: basis, scenario_flag, quality_flag, fallback_mode, trace_id, source_version, rule_version, cache_version, generated_at."
Write-Output "- Confirm rows stay tied to the paired ledger reconciliation + daily average source chain."
Write-Output "- Do not infer rows from ZQTZ holdings-side logic, holdings buckets, or research-style bond categories."

if ($CheckLive) {
  Write-Output "Live checks:"
  Invoke-WebRequest -Uri "$ApiBaseUrl/health" -UseBasicParsing | Out-Null
  Write-Output "- API health reachable"
  Invoke-WebRequest -Uri "$FrontendBaseUrl$route" -UseBasicParsing | Out-Null
  Write-Output "- Frontend route reachable"

  $datesPayload = $null
  foreach ($api in $supportingApis) {
    if ($api -eq "/ui/pnl/product-category/dates") {
      $datesPayload = Invoke-RestMethod -Uri "$ApiBaseUrl$api"
      Write-Output "- Page API reachable: $api"
    } else {
      Write-Output "- Page API live check skipped (requires mutation or parameters): $api"
    }
  }

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
