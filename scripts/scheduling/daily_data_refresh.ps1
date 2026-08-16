<#
.SYNOPSIS
  MOSS after-close daily data refresh chain (Windows Task Scheduler entry point).

.DESCRIPTION
  Serially runs the after-close data chain, reusing the existing operator CLIs:

    1. choice_stock_daily_refresh   (CRITICAL) daily stock ingest + materialize
                                    + market breadth + gate supplement/history
                                    + position snapshot roll-forward
                                    + supply freshness report
    2. livermore_pretrade_candidates (depends on 1) candidate history
                                    + execution history + outcome maturity
                                    + pretrade export
    3. macro_toolkit_freshness      (independent) vendor macro data refresh
    4. macro_toolkit_daily_chain    (after 3) ten-model chain + daily report

  Steps 1/3/4 are skipped automatically when their dedicated legacy scheduled
  task (MOSS-ChoiceStockDailyRefresh / MOSS-MacroToolkitFreshness /
  MOSS-MacroToolkitDailyChain) exists and is enabled, so this chain never
  double-runs a vendor ingest. Pass -IgnoreExistingTimers to force every step.

  Every step appends stdout/stderr to scripts\scheduling\logs\YYYYMMDD.log.
  Receipts follow the existing convention under data\logs\*_receipt.json.

  Exit codes:
    0  every executed step succeeded (skips are fine, incl. non-trading day)
    1  a non-critical step failed; the rest of the chain still ran
    2  the critical ingest step failed; dependent steps were aborted

.PARAMETER DryRun
  Print the execution plan (commands, skip predictions) without running anything.

.PARAMETER AsOfDate
  Optional YYYY-MM-DD override for reruns; forwarded as --as-of-date /
  --target-date. Without it the CLIs default to today and skip weekends.

.PARAMETER VendorSourceIp
  Optional IPv4 (or 'auto') forwarded to choice_stock_daily_refresh
  --vendor-source-ip for hosts with a TLS-breaking default route.

.PARAMETER IgnoreExistingTimers
  Run every step even when the legacy per-step scheduled tasks are enabled.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$AsOfDate = "",
    [string]$RepoRoot = "",
    [string]$PythonExe = "",
    [string]$VendorSourceIp = "",
    [switch]$IgnoreExistingTimers
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path $PythonExe)) {
    throw "PythonExe not found: $PythonExe"
}
if (-not [string]::IsNullOrWhiteSpace($AsOfDate)) {
    if ($AsOfDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
        throw "AsOfDate must be YYYY-MM-DD, got: $AsOfDate"
    }
}

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ("{0}.log" -f (Get-Date -Format "yyyyMMdd"))
$dataLogDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $dataLogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Test-EnabledScheduledTask {
    param([string]$TaskName)
    try {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    } catch {
        return $false
    }
    return ($task.State -ne "Disabled")
}

# ---------------------------------------------------------------- step table

$choiceArgs = @(
    "scripts\choice_stock_daily_refresh.py",
    "--run-once", "--run-kind", "scheduled",
    "--receipt-path", (Join-Path $dataLogDir "choice_stock_daily_refresh_receipt.json")
)
if ($AsOfDate) { $choiceArgs += @("--as-of-date", $AsOfDate) }
if (-not [string]::IsNullOrWhiteSpace($VendorSourceIp)) {
    $choiceArgs += @("--vendor-source-ip", $VendorSourceIp.Trim())
}

$pretradeArgs = @("scripts\run_livermore_daily_pretrade_refresh.py")
if ($AsOfDate) { $pretradeArgs += @("--target-date", $AsOfDate) }

$freshnessArgs = @(
    "scripts\macro_toolkit_freshness_refresh.py",
    "--run-once", "--run-kind", "scheduled",
    "--receipt-path", (Join-Path $dataLogDir "macro_toolkit_freshness_refresh_receipt.json")
)

$macroChainArgs = @(
    "scripts\macro_toolkit_daily_chain.py",
    "--run-once", "--run-kind", "scheduled",
    "--receipt-path", (Join-Path $dataLogDir "macro_toolkit_daily_chain_receipt.json")
)

$steps = @(
    @{
        Name       = "choice_stock_daily_refresh"
        Critical   = $true
        LegacyTask = "MOSS-ChoiceStockDailyRefresh"
        DependsOn  = $null
        Args       = $choiceArgs
        Purpose    = "stock ingest -> materialize -> breadth -> gate supplement/history -> position snapshot"
    },
    @{
        Name       = "livermore_pretrade_candidates"
        Critical   = $false
        LegacyTask = $null
        DependsOn  = "choice_stock_daily_refresh"
        Args       = $pretradeArgs
        Purpose    = "candidate history -> execution history -> outcome maturity -> pretrade export"
    },
    @{
        Name       = "macro_toolkit_freshness"
        Critical   = $false
        LegacyTask = "MOSS-MacroToolkitFreshness"
        DependsOn  = $null
        Args       = $freshnessArgs
        Purpose    = "vendor macro data refresh (commodity, headlines, NCD, CFFEX)"
    },
    @{
        Name       = "macro_toolkit_daily_chain"
        Critical   = $false
        LegacyTask = "MOSS-MacroToolkitDailyChain"
        DependsOn  = $null
        Args       = $macroChainArgs
        Purpose    = "ten-model macro chain + illustrated daily report"
    }
)

# ---------------------------------------------------------------- planning

$plan = @()
foreach ($step in $steps) {
    $skipReason = $null
    if ($step.LegacyTask -and -not $IgnoreExistingTimers) {
        if (Test-EnabledScheduledTask -TaskName $step.LegacyTask) {
            $skipReason = "covered by enabled scheduled task '$($step.LegacyTask)'"
        }
    }
    $plan += @{ Step = $step; SkipReason = $skipReason }
}

Write-Log "===== daily_data_refresh start (DryRun=$DryRun, AsOfDate='$AsOfDate', IgnoreExistingTimers=$IgnoreExistingTimers) ====="
Write-Log "RepoRoot=$RepoRoot"
Write-Log "PythonExe=$PythonExe"

if ($DryRun) {
    Write-Log "-- execution plan (nothing will run) --"
    $index = 0
    foreach ($item in $plan) {
        $index += 1
        $step = $item.Step
        $critical = if ($step.Critical) { "CRITICAL" } else { "non-critical" }
        $depends = if ($step.DependsOn) { "depends on: $($step.DependsOn)" } else { "independent" }
        Write-Log ("[{0}] {1} ({2}, {3})" -f $index, $step.Name, $critical, $depends)
        Write-Log ("      purpose: {0}" -f $step.Purpose)
        if ($item.SkipReason) {
            Write-Log ("      WOULD SKIP: {0}" -f $item.SkipReason)
        } else {
            Write-Log ("      command: `"{0}`" {1}" -f $PythonExe, ($step.Args -join " "))
        }
    }
    Write-Log "===== dry run complete; exit 0 ====="
    exit 0
}

# ---------------------------------------------------------------- execution

Set-Location $RepoRoot
$env:PYTHONIOENCODING = "utf-8"

$results = @{}
$anyNonCriticalFailure = $false
$criticalFailure = $false

foreach ($item in $plan) {
    $step = $item.Step
    $name = $step.Name

    if ($item.SkipReason) {
        Write-Log ("[{0}] SKIP: {1}" -f $name, $item.SkipReason)
        $results[$name] = "skipped_covered_by_timer"
        continue
    }

    if ($step.DependsOn) {
        $upstream = $results[$step.DependsOn]
        if ($upstream -eq "failed") {
            Write-Log ("[{0}] SKIP: upstream step '{1}' failed" -f $name, $step.DependsOn)
            $results[$name] = "skipped_upstream_failed"
            continue
        }
        if ($upstream -eq "skipped_non_trading_day") {
            Write-Log ("[{0}] SKIP: non-trading day (per '{1}')" -f $name, $step.DependsOn)
            $results[$name] = "skipped_non_trading_day"
            continue
        }
        # upstream success or covered-by-timer: proceed; the CLI has its own
        # not_ready guard if the data has not actually landed yet.
    }

    Write-Log ("[{0}] START `"{1}`" {2}" -f $name, $PythonExe, ($step.Args -join " "))
    $started = Get-Date
    $stepArgs = $step.Args
    $output = & $PythonExe @stepArgs 2>&1
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) {
        Add-Content -Path $logPath -Value ("    " + [string]$line) -Encoding UTF8
    }
    $elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
    $outputText = ($output | Out-String)

    if ($exitCode -eq 0 -and $outputText -match "skipped_non_trading_day") {
        Write-Log ("[{0}] SKIPPED non-trading day (exit=0, {1}s)" -f $name, $elapsed)
        $results[$name] = "skipped_non_trading_day"
        continue
    }

    if ($exitCode -eq 0) {
        Write-Log ("[{0}] OK exit=0 elapsed={1}s" -f $name, $elapsed)
        $results[$name] = "success"
    } else {
        Write-Log ("[{0}] ALERT FAILED exit={1} elapsed={2}s" -f $name, $exitCode, $elapsed)
        $results[$name] = "failed"
        if ($step.Critical) {
            $criticalFailure = $true
        } else {
            $anyNonCriticalFailure = $true
        }
    }
}

# ---------------------------------------------------------------- summary

Write-Log "-- summary --"
foreach ($step in $steps) {
    $status = $results[$step.Name]
    if (-not $status) { $status = "not_reached" }
    Write-Log ("    {0,-32} {1}" -f $step.Name, $status)
}

if ($criticalFailure) {
    Write-Log "===== daily_data_refresh finished: CRITICAL FAILURE (exit 2) ====="
    exit 2
}
if ($anyNonCriticalFailure) {
    Write-Log "===== daily_data_refresh finished: PARTIAL FAILURE (exit 1) ====="
    exit 1
}
Write-Log "===== daily_data_refresh finished: OK (exit 0) ====="
exit 0
