param(
  [string]$PageSlug = "product-category-pnl",

  [ValidateSet("plan", "preflight", "verify", "readiness", "approval", "all")]
  [string]$Mode = "plan",

  [switch]$Run,
  [switch]$CheckLive,
  [switch]$SkipMcpContracts,
  [switch]$SkipBrowserSmoke
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$readinessScript = Join-Path $root "scripts\codex-page-readiness.ps1"
$verifyScript = Join-Path $root "scripts\codex-verify-page.ps1"

Set-Location $root

function Write-FlowPlan {
  Write-Output "1. Preflight readiness"
  Write-Output "   scripts\codex-page-readiness.ps1 -PageSlug $PageSlug"
  Write-Output "2. Page verification"
  Write-Output "   scripts\codex-verify-page.ps1 -PageSlug $PageSlug -Run"
  Write-Output "3. Page readiness gate"
  Write-Output "   scripts\codex-page-readiness.ps1 -PageSlug $PageSlug -Run"
  Write-Output "4. Approval capture check"
  Write-Output "   scripts\codex-page-readiness.ps1 -PageSlug $PageSlug -RequireApprovalCaptured"
}

function Invoke-CheckedPowerShell {
  param(
    [string]$Label,
    [string]$ScriptPath,
    [string[]]$ArgumentList
  )

  Write-Output "Running $Label"
  & powershell -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ArgumentList
  if ($LASTEXITCODE -ne 0) {
    throw "$Label failed with exit code $LASTEXITCODE"
  }
}

function Invoke-Preflight {
  Invoke-CheckedPowerShell `
    -Label "preflight readiness" `
    -ScriptPath $readinessScript `
    -ArgumentList @("-PageSlug", $PageSlug)
}

function Invoke-Verify {
  $args = @("-PageSlug", $PageSlug, "-Run")
  if ($SkipMcpContracts) {
    $args += "-SkipMcpContracts"
  }
  if ($SkipBrowserSmoke) {
    $args += "-SkipBrowserSmoke"
  }

  Invoke-CheckedPowerShell `
    -Label "page verification" `
    -ScriptPath $verifyScript `
    -ArgumentList $args
}

function Invoke-Readiness {
  $args = @("-PageSlug", $PageSlug, "-Run")
  if ($CheckLive) {
    $args += "-CheckLive"
  }

  Invoke-CheckedPowerShell `
    -Label "page readiness gate" `
    -ScriptPath $readinessScript `
    -ArgumentList $args
}

function Invoke-Approval {
  Invoke-CheckedPowerShell `
    -Label "approval capture check" `
    -ScriptPath $readinessScript `
    -ArgumentList @("-PageSlug", $PageSlug, "-RequireApprovalCaptured")
}

Write-Output "MOSS development flow adapter: $PageSlug"
Write-Output "Mode: $Mode"

if (-not $Run -or $Mode -eq "plan") {
  Write-FlowPlan
  Write-Output "Development flow plan complete. Pass -Run with -Mode verify/readiness/approval/all to execute."
  exit 0
}

if ($Mode -eq "preflight") {
  Invoke-Preflight
} elseif ($Mode -eq "verify") {
  Invoke-Verify
} elseif ($Mode -eq "readiness") {
  Invoke-Readiness
} elseif ($Mode -eq "approval") {
  Invoke-Approval
} elseif ($Mode -eq "all") {
  Invoke-Preflight
  Invoke-Verify
  Invoke-Readiness
  Invoke-Approval
} else {
  throw "Unsupported mode: $Mode"
}

Write-Output "Development flow adapter finished."
