<#
.SYNOPSIS
  MOSS after-close daily data refresh chain (Windows Task Scheduler entry point).

.DESCRIPTION
  Serially runs the after-close data chain, reusing the existing operator CLIs:

    1. choice_stock_daily_refresh   (CRITICAL) daily stock ingest + materialize
                                    + market breadth + gate supplement/history
                                    + position snapshot roll-forward
                                    + supply freshness report
    2. stock_adjustment_factor_daily_refresh
                                    (after 1, before pretrade) daily adj-factor
                                    increment for current stock observations
    3. stock_limit_price_daily_refresh
                                    (after 2, before pretrade) numeric limit
                                    price refresh for current observations
    4. macro_toolkit_freshness      (independent) vendor macro data refresh
    5. livermore_pretrade_candidates (depends on 3 and 4) candidate history
                                    + execution history + outcome maturity
                                    + pretrade export
    6. tushare_news_backup          (independent) market news ingest
    7. macro_toolkit_daily_chain    (after 4) ten-model chain + daily report

  Steps 1/5/6 are skipped automatically when their dedicated legacy scheduled
  task (MOSS-ChoiceStockDailyRefresh / MOSS-MacroToolkitFreshness /
  MOSS-MacroToolkitDailyChain) exists and is enabled. If a skipped legacy step
  is an upstream dependency of a local step, the local branch fails closed
  because this process cannot verify that the external timer has completed.
  Pass -IgnoreExistingTimers only when duplicate execution is intentionally safe.

  Concept interval rebuild is intentionally not part of this chain yet. The
  current snapshot cadence can still leave stale intervals, and scheduler
  ownership for that contract is not approved.

  Every step appends stdout/stderr to scripts\scheduling\logs\YYYYMMDD.log.
  Receipts follow the existing convention under data\logs\*_receipt.json.

  Exit codes:
    0  every executed step succeeded (independent skips and non-trading day are fine)
    1  a non-critical step failed; the rest of the chain still ran
    2  the critical ingest step failed; dependent steps were aborted

.PARAMETER DryRun
  Print the execution plan (commands, skip predictions) without running anything.

.PARAMETER AsOfDate
  Optional YYYY-MM-DD override for reruns; forwarded as --as-of-date /
  --target-date. Without it the CLIs default to today and skip weekends.

.PARAMETER VendorSourceIp
  Optional IPv4 (or 'auto') forwarded to Choice, Tushare, public macro, factor,
  and limit-price refreshes for hosts with a TLS-breaking default route.

.PARAMETER TushareStockGapRepair
  Run step 1 through the controlled single-day Tushare stock gap-repair path.
  The stock CLI binds the history start to its resolved target date.

.PARAMETER IgnoreExistingTimers
  Run every step even when the legacy per-step scheduled tasks are enabled.

.PARAMETER PublicationOnly
  Recover or retry publication for one already completed aggregate receipt. The
  seven business children are never entered in this mode.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$AsOfDate = "",
    [string]$RepoRoot = "",
    [string]$PythonExe = "",
    [string]$VendorSourceIp = "",
    [switch]$TushareStockGapRepair,
    [switch]$IgnoreExistingTimers,
    [switch]$PublicationOnly,
    [string]$AggregateRunId = "",
    [string]$AggregateReceiptPath = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    . (Join-Path $RepoRoot "scripts\dev-python.ps1")
    $PythonExe = Resolve-DevPython
}
if (-not (Test-Path $PythonExe)) {
    throw "PythonExe not found: $PythonExe"
}
if (-not [string]::IsNullOrWhiteSpace($AsOfDate)) {
    if ($AsOfDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
        throw "AsOfDate must be YYYY-MM-DD, got: $AsOfDate"
    }
}
if (
    -not $PublicationOnly -and
    -not $DryRun -and
    $env:MOSS_SYSTEM_READ_PUBLICATION_ENABLED -match '^(true|1|yes|on)$' -and
    -not [string]::IsNullOrWhiteSpace($AsOfDate) -and
    $AsOfDate -ne (Get-Date -Format "yyyy-MM-dd")
) {
    throw "Historical AsOfDate cannot run the undated macro freshness writer; use a current-date aggregate."
}

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ("{0}.log" -f (Get-Date -Format "yyyyMMdd"))
$dataLogDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $dataLogDir | Out-Null

$reportDate = if ($AsOfDate) { $AsOfDate } else { Get-Date -Format "yyyy-MM-dd" }
if ([string]::IsNullOrWhiteSpace($AggregateRunId)) {
    if ($PublicationOnly) {
        throw "PublicationOnly requires AggregateRunId."
    }
    $AggregateRunId = "market-daily:{0}:{1}" -f $reportDate, ([guid]::NewGuid().ToString("N").Substring(0, 12))
}
$aggregateSlug = $AggregateRunId -replace '[^A-Za-z0-9._-]', '_'
if ([string]::IsNullOrWhiteSpace($AggregateReceiptPath)) {
    if ($PublicationOnly) {
        throw "PublicationOnly requires AggregateReceiptPath."
    }
    $AggregateReceiptPath = Join-Path $dataLogDir ("market_daily_refresh_{0}.json" -f $aggregateSlug)
}
$AggregateReceiptPath = [IO.Path]::GetFullPath($AggregateReceiptPath)

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
    "--receipt-path", (Join-Path $dataLogDir ("choice_stock_daily_refresh_{0}.json" -f $aggregateSlug))
)
if ($AsOfDate) { $choiceArgs += @("--as-of-date", $AsOfDate) }
if (-not [string]::IsNullOrWhiteSpace($VendorSourceIp)) {
    $choiceArgs += @("--vendor-source-ip", $VendorSourceIp.Trim())
}

function Invoke-MarketReceiptControl {
    param(
        [string[]]$Arguments,
        [switch]$AllowFailure
    )
    $controlOutput = & $PythonExe -m backend.app.tasks.system_read_market_publication @Arguments 2>&1
    $controlExitCode = $LASTEXITCODE
    foreach ($line in $controlOutput) {
        $text = if ($line -is [System.Management.Automation.ErrorRecord]) { $line.Exception.Message } else { [string]$line }
        Write-Log ("    market-publication: " + $text)
    }
    if ($controlExitCode -ne 0 -and -not $AllowFailure) {
        throw "Market aggregate receipt control failed with exit=$controlExitCode."
    }
    return $controlExitCode
}
if ($TushareStockGapRepair) { $choiceArgs += "--tushare-gap-repair" }

$pretradeArgs = @("scripts\run_livermore_daily_pretrade_refresh.py")
if ($AsOfDate) { $pretradeArgs += @("--target-date", $AsOfDate) }
if (-not [string]::IsNullOrWhiteSpace($VendorSourceIp)) {
    $pretradeArgs += @("--vendor-source-ip", $VendorSourceIp.Trim())
}

$factorArgs = @(
    "scripts\stock_adjustment_factor_daily_refresh.py",
    "--run-once",
    "--run-kind", "scheduled",
    "--receipt-path", (Join-Path $dataLogDir ("stock_adjustment_factor_daily_refresh_{0}.json" -f $aggregateSlug))
)
if ($AsOfDate) { $factorArgs += @("--as-of-date", $AsOfDate) }
if (-not [string]::IsNullOrWhiteSpace($VendorSourceIp)) {
    $factorArgs += @("--vendor-source-ip", $VendorSourceIp.Trim())
}

$limitPriceArgs = @(
    "-m",
    "backend.app.tasks.stock_limit_price_daily_refresh",
    "--run-once",
    "--receipt-dir", $dataLogDir
)
if ($AsOfDate) { $limitPriceArgs += @("--as-of-date", $AsOfDate) }
if (-not [string]::IsNullOrWhiteSpace($VendorSourceIp)) {
    $limitPriceArgs += @("--source-ip", $VendorSourceIp.Trim())
}

$freshnessArgs = @(
    "scripts\macro_toolkit_freshness_refresh.py",
    "--run-once", "--run-kind", "scheduled",
    "--receipt-path", (Join-Path $dataLogDir ("macro_toolkit_freshness_refresh_{0}.json" -f $aggregateSlug))
)
if (-not [string]::IsNullOrWhiteSpace($VendorSourceIp)) {
    $freshnessArgs += @("--vendor-source-ip", $VendorSourceIp.Trim())
}

# News ingest deduplicates by event_key and holds the DuckDB writer lock, so a
# daily rerun with 48h lookback is idempotent. Without this step the news table
# silently goes stale once the 30-day retention window passes (observed 07-15
# to 08-27 outage: the script previously had no scheduler owner).
$newsBackupArgs = @(
    "scripts\refresh_tushare_news_backup.py",
    "--news-src", "sina"
)
if (-not [string]::IsNullOrWhiteSpace($VendorSourceIp)) {
    $newsBackupArgs += @("--vendor-source-ip", $VendorSourceIp.Trim())
}

$macroChainArgs = @(
    "scripts\macro_toolkit_daily_chain.py",
    "--run-once", "--run-kind", "scheduled",
    "--receipt-path", (Join-Path $dataLogDir ("macro_toolkit_daily_chain_{0}.json" -f $aggregateSlug))
)

$steps = @(
    @{
        Name       = "choice_stock_daily_refresh"
        Critical   = $true
        LegacyTask = "MOSS-ChoiceStockDailyRefresh"
        DependsOn  = $null
        Args       = $choiceArgs
        ReceiptPath = (Join-Path $dataLogDir ("choice_stock_daily_refresh_{0}.json" -f $aggregateSlug))
        Purpose    = "stock ingest -> materialize -> breadth -> gate supplement/history -> position snapshot"
    },
    @{
        Name       = "stock_adjustment_factor_daily_refresh"
        Critical   = $false
        LegacyTask = $null
        DependsOn  = "choice_stock_daily_refresh"
        Args       = $factorArgs
        ReceiptPath = (Join-Path $dataLogDir ("stock_adjustment_factor_daily_refresh_{0}.json" -f $aggregateSlug))
        Purpose    = "daily stock adjustment factor increment for current observations"
    },
    @{
        Name       = "stock_limit_price_daily_refresh"
        Critical   = $false
        LegacyTask = $null
        DependsOn  = "stock_adjustment_factor_daily_refresh"
        Args       = $limitPriceArgs
        ReceiptDir = $dataLogDir
        Purpose    = "numeric stock limit price refresh for current observations"
    },
    @{
        Name       = "macro_toolkit_freshness"
        Critical   = $false
        LegacyTask = "MOSS-MacroToolkitFreshness"
        DependsOn  = $null
        Args       = $freshnessArgs
        ReceiptPath = (Join-Path $dataLogDir ("macro_toolkit_freshness_refresh_{0}.json" -f $aggregateSlug))
        Purpose    = "vendor macro data refresh (commodity, headlines, NCD, CFFEX)"
    },
    @{
        Name       = "livermore_pretrade_candidates"
        Critical   = $false
        LegacyTask = $null
        DependsOn  = @("stock_limit_price_daily_refresh", "macro_toolkit_freshness")
        Args       = $pretradeArgs
        Purpose    = "candidate history -> execution history -> outcome maturity -> pretrade export"
    },
    @{
        Name       = "tushare_news_backup"
        Critical   = $false
        LegacyTask = $null
        DependsOn  = $null
        Args       = $newsBackupArgs
        Purpose    = "Tushare news backup ingest feeding the market-overview news surfaces"
    },
    @{
        Name       = "macro_toolkit_daily_chain"
        Critical   = $false
        LegacyTask = "MOSS-MacroToolkitDailyChain"
        DependsOn  = $null
        Args       = $macroChainArgs
        ReceiptPath = (Join-Path $dataLogDir ("macro_toolkit_daily_chain_{0}.json" -f $aggregateSlug))
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

Write-Log "===== daily_data_refresh start (DryRun=$DryRun, AsOfDate='$AsOfDate', TushareStockGapRepair=$TushareStockGapRepair, IgnoreExistingTimers=$IgnoreExistingTimers, PublicationOnly=$PublicationOnly) ====="
Write-Log "RepoRoot=$RepoRoot"
Write-Log "PythonExe=$PythonExe"
Write-Log "AggregateRunId=$AggregateRunId"
Write-Log "AggregateReceiptPath=$AggregateReceiptPath"

if ($PublicationOnly) {
    Set-Location $RepoRoot
    $env:PYTHONIOENCODING = "utf-8"
    $recoveryArgs = @(
        "recover",
        "--receipt-path", $AggregateReceiptPath,
        "--run-id", $AggregateRunId,
        "--report-date", $reportDate
    )
    $recoveryExitCode = Invoke-MarketReceiptControl -Arguments $recoveryArgs -AllowFailure
    if ($recoveryExitCode -ne 0) {
        Write-Log "===== publication-only recovery failed (exit 1); business children were not run ====="
        exit 1
    }
    Write-Log "===== publication-only recovery complete (exit 0); business children were not run ====="
    exit 0
}

if ($DryRun) {
    Write-Log "-- execution plan (nothing will run) --"
    $index = 0
    foreach ($item in $plan) {
        $index += 1
        $step = $item.Step
        $critical = if ($step.Critical) { "CRITICAL" } else { "non-critical" }
        $depends = if ($step.DependsOn) { "depends on: $(@($step.DependsOn) -join ', ')" } else { "independent" }
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

$beginArgs = @(
    "begin",
    "--receipt-path", $AggregateReceiptPath,
    "--run-id", $AggregateRunId,
    "--report-date", $reportDate
)
try {
    Invoke-MarketReceiptControl -Arguments $beginArgs | Out-Null
} catch {
    Write-Log ("===== aggregate receipt initialization failed; no business child was run: {0} =====" -f $_.Exception.Message)
    exit 2
}

$results = @{}
$childRunIds = @{}
$anyNonCriticalFailure = $false
$criticalFailure = $false

foreach ($item in $plan) {
    $step = $item.Step
    $name = $step.Name

    if ($item.SkipReason) {
        Write-Log ("[{0}] SKIP: {1}" -f $name, $item.SkipReason)
        $results[$name] = "skipped_covered_by_timer"
        $skipArgs = @(
            "skip-child", "--receipt-path", $AggregateReceiptPath,
            "--run-id", $AggregateRunId, "--report-date", $reportDate,
            "--child-name", $name, "--reason", $item.SkipReason
        )
        Invoke-MarketReceiptControl -Arguments $skipArgs | Out-Null
        $hasLocalDependents = @(
            $steps | Where-Object { @($_.DependsOn) -contains $name }
        ).Count -gt 0
        if ($hasLocalDependents) {
            Write-Log (
                "[{0}] ALERT: cannot verify completion of legacy timer; dependent local steps will fail closed" -f $name
            )
            if ($step.Critical) {
                $criticalFailure = $true
            } else {
                $anyNonCriticalFailure = $true
            }
        }
        continue
    }

    $blockedDependency = $null
    $blockedStatus = $null
    $dependencyNames = if ($step.DependsOn) { @($step.DependsOn) } else { @() }
    foreach ($dependencyName in $dependencyNames) {
        $upstream = $results[$dependencyName]
        if ($upstream -in @("failed", "skipped_upstream_failed")) {
            $blockedDependency = $dependencyName
            $blockedStatus = "failed"
            break
        }
        if ($upstream -eq "skipped_non_trading_day") {
            $blockedDependency = $dependencyName
            $blockedStatus = "non_trading_day"
            break
        }
        if ($upstream -in @("skipped_covered_by_timer", "skipped_upstream_unverified")) {
            $blockedDependency = $dependencyName
            $blockedStatus = "unverified"
            break
        }
    }
    if ($blockedStatus) {
        if ($blockedStatus -eq "failed") {
            Write-Log ("[{0}] SKIP: upstream step '{1}' failed" -f $name, $blockedDependency)
            $results[$name] = "skipped_upstream_failed"
            $skipArgs = @(
                "skip-child", "--receipt-path", $AggregateReceiptPath,
                "--run-id", $AggregateRunId, "--report-date", $reportDate,
                "--child-name", $name, "--reason", "upstream failed"
            )
            Invoke-MarketReceiptControl -Arguments $skipArgs | Out-Null
            continue
        }
        if ($blockedStatus -eq "non_trading_day") {
            Write-Log ("[{0}] SKIP: non-trading day (per '{1}')" -f $name, $blockedDependency)
            $results[$name] = "skipped_non_trading_day"
            $skipChildRunId = "{0}:{1}:not-executed" -f $AggregateRunId, $name
            $childRunIds[$name] = $skipChildRunId
            $upstreamReceiptStatus = if ($blockedDependency -eq "choice_stock_daily_refresh") {
                "skipped_non_trading_day"
            } else {
                "not_executed"
            }
            $skipArgs = @(
                "skip-child", "--receipt-path", $AggregateReceiptPath,
                "--run-id", $AggregateRunId, "--report-date", $reportDate,
                "--child-name", $name, "--reason", "upstream non-trading day",
                "--child-run-id", $skipChildRunId,
                "--upstream-child-name", $blockedDependency,
                "--upstream-child-run-id", $childRunIds[$blockedDependency],
                "--upstream-status", $upstreamReceiptStatus
            )
            Invoke-MarketReceiptControl -Arguments $skipArgs | Out-Null
            continue
        }
        Write-Log (
            "[{0}] SKIP: upstream step '{1}' completion cannot be verified in this run" -f $name, $blockedDependency
        )
        $results[$name] = "skipped_upstream_unverified"
        $skipArgs = @(
            "skip-child", "--receipt-path", $AggregateReceiptPath,
            "--run-id", $AggregateRunId, "--report-date", $reportDate,
            "--child-name", $name, "--reason", "upstream completion unverified"
        )
        Invoke-MarketReceiptControl -Arguments $skipArgs | Out-Null
        continue
    }

    $childRunId = "{0}:{1}:{2}" -f $AggregateRunId, $name, ([guid]::NewGuid().ToString("N").Substring(0, 12))
    $childRunIds[$name] = $childRunId
    $startArgs = @(
        "start-child", "--receipt-path", $AggregateReceiptPath,
        "--run-id", $AggregateRunId, "--report-date", $reportDate,
        "--child-name", $name, "--child-run-id", $childRunId
    )
    try {
        Invoke-MarketReceiptControl -Arguments $startArgs | Out-Null
    } catch {
        Write-Log ("[{0}] ALERT: child identity could not be persisted before execution" -f $name)
        if ($step.Critical) { $criticalFailure = $true } else { $anyNonCriticalFailure = $true }
        $results[$name] = "failed"
        continue
    }
    if ($name -eq "stock_limit_price_daily_refresh") {
        $step.Args += @("--run-id", $childRunId)
    }
    Write-Log ("[{0}] START `"{1}`" {2}" -f $name, $PythonExe, ($step.Args -join " "))
    $started = Get-Date
    $stepArgs = $step.Args
    # Windows PowerShell 5.1 wraps native stderr lines as NativeCommandError.
    # Keep them non-terminating here so the child exit code determines the step outcome.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $PythonExe @stepArgs 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    foreach ($line in $output) {
        $text = if ($line -is [System.Management.Automation.ErrorRecord]) { $line.Exception.Message } else { [string]$line }
        Add-Content -Path $logPath -Value ("    " + $text) -Encoding UTF8
    }
    $elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
    $outputText = ($output | Out-String)
    $outputPath = Join-Path $dataLogDir ("market_daily_child_{0}_{1}.jsonout" -f ($name -replace '[^A-Za-z0-9._-]', '_'), ([guid]::NewGuid().ToString("N")))
    [IO.File]::WriteAllText($outputPath, $outputText, [Text.UTF8Encoding]::new($false))
    $finishArgs = @(
        "finish-child", "--receipt-path", $AggregateReceiptPath,
        "--run-id", $AggregateRunId, "--report-date", $reportDate,
        "--child-name", $name, "--child-run-id", $childRunId,
        "--exit-code", [string]$exitCode, "--output-path", $outputPath
    )
    if ($step.ReceiptPath) { $finishArgs += @("--external-receipt-path", [string]$step.ReceiptPath) }
    if ($step.ReceiptDir) { $finishArgs += @("--external-receipt-dir", [string]$step.ReceiptDir) }
    $finishExitCode = Invoke-MarketReceiptControl -Arguments $finishArgs -AllowFailure
    [IO.File]::Delete($outputPath)
    if ($finishExitCode -ne 0) {
        Write-Log ("[{0}] ALERT: terminal child receipt could not be persisted" -f $name)
        $exitCode = 1
    }

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
    $failureArgs = @(
        "fail-aggregate", "--receipt-path", $AggregateReceiptPath,
        "--run-id", $AggregateRunId, "--report-date", $reportDate,
        "--failure-status", "business_failed",
        "--reason", "one or more critical business children failed or were unverified"
    )
    Invoke-MarketReceiptControl -Arguments $failureArgs -AllowFailure | Out-Null
    Write-Log "===== daily_data_refresh finished: CRITICAL FAILURE (exit 2) ====="
    exit 2
}
if ($anyNonCriticalFailure) {
    $failureArgs = @(
        "fail-aggregate", "--receipt-path", $AggregateReceiptPath,
        "--run-id", $AggregateRunId, "--report-date", $reportDate,
        "--failure-status", "business_failed",
        "--reason", "one or more business children failed or were unverified"
    )
    Invoke-MarketReceiptControl -Arguments $failureArgs -AllowFailure | Out-Null
    Write-Log "===== daily_data_refresh finished: PARTIAL FAILURE (exit 1) ====="
    exit 1
}
try {
    $completeArgs = @(
        "complete-business", "--receipt-path", $AggregateReceiptPath,
        "--run-id", $AggregateRunId, "--report-date", $reportDate
    )
    Invoke-MarketReceiptControl -Arguments $completeArgs | Out-Null
} catch {
    $failureArgs = @(
        "fail-aggregate", "--receipt-path", $AggregateReceiptPath,
        "--run-id", $AggregateRunId, "--report-date", $reportDate,
        "--failure-status", "qualification_failed",
        "--reason", "aggregate completion qualification failed"
    )
    Invoke-MarketReceiptControl -Arguments $failureArgs -AllowFailure | Out-Null
    Write-Log ("===== daily_data_refresh qualification failed (exit 1): {0} =====" -f $_.Exception.Message)
    exit 1
}
try {
    $publishArgs = @(
        "publish", "--receipt-path", $AggregateReceiptPath,
        "--run-id", $AggregateRunId, "--report-date", $reportDate
    )
    Invoke-MarketReceiptControl -Arguments $publishArgs | Out-Null
} catch {
    Write-Log ("===== daily_data_refresh business complete but publication failed (exit 1): {0} =====" -f $_.Exception.Message)
    exit 1
}
Write-Log "===== daily_data_refresh finished: OK (exit 0) ====="
exit 0
