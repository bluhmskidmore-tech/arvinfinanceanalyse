<#
.SYNOPSIS
  Idempotently register (or unregister) the MOSS daily/monthly scheduled tasks.

.DESCRIPTION
  Registers two Windows scheduled tasks pointing at the scripts in this folder:

    MOSS-DailyDataRefresh    daily at -DailyTime (default 18:45, host clock)
                             -> daily_data_refresh.ps1
    MOSS-MonthlyWalkForward  first Saturday of each month at -MonthlyTime
                             (default 09:00) -> monthly_walk_forward.ps1

  Re-running updates the existing tasks in place (schtasks /F). Supports
  -WhatIf for a no-op preview and -Unregister to remove both tasks.

  This host may already have per-step legacy timers enabled
  (MOSS-ChoiceStockDailyRefresh, MOSS-MacroToolkitFreshness,
  MOSS-MacroToolkitDailyChain). daily_data_refresh.ps1 skips the steps those
  cover, so coexistence is safe but the chain then only adds the candidate/
  outcome step. To let MOSS-DailyDataRefresh own the whole chain, pass
  -DisableLegacyTimers (reversible via 'schtasks /Change /TN <name> /ENABLE').

.EXAMPLE
  # preview only
  .\register_scheduled_tasks.ps1 -WhatIf

.EXAMPLE
  # install, letting the new daily task own the full chain
  .\register_scheduled_tasks.ps1 -DisableLegacyTimers

.EXAMPLE
  # remove both tasks
  .\register_scheduled_tasks.ps1 -Unregister
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoRoot = "",
    [string]$DailyTaskName = "MOSS-DailyDataRefresh",
    [string]$MonthlyTaskName = "MOSS-MonthlyWalkForward",
    [ValidatePattern('^\d{2}:\d{2}$')]
    [string]$DailyTime = "18:45",
    [ValidatePattern('^\d{2}:\d{2}$')]
    [string]$MonthlyTime = "09:00",
    [string]$VendorSourceIp = "",
    [switch]$Unregister,
    [switch]$DisableLegacyTimers
)

$ErrorActionPreference = "Stop"

function Resolve-ValidatedVendorSourceIp {
    param([string]$Value)

    if ([string]::IsNullOrEmpty($Value)) {
        return ""
    }
    if ($Value -ne $Value.Trim()) {
        throw "VendorSourceIp must be a plain IPv4 literal with no surrounding whitespace."
    }
    if ($Value -notmatch '^(?:\d{1,3}\.){3}\d{1,3}$') {
        throw "VendorSourceIp must be a plain IPv4 literal like 172.16.115.248."
    }

    try {
        $parsed = [System.Net.IPAddress]::Parse($Value)
    } catch {
        throw "VendorSourceIp must be a plain IPv4 literal like 172.16.115.248."
    }
    if ($parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw "VendorSourceIp must be a plain IPv4 literal like 172.16.115.248."
    }
    return $parsed.ToString()
}

$normalizedVendorSourceIp = Resolve-ValidatedVendorSourceIp -Value $VendorSourceIp

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
$dailyScript = Join-Path $PSScriptRoot "run_daily_data_refresh_host.ps1"
$maintenanceHelper = Join-Path $PSScriptRoot "market_refresh_host_common.ps1"
$monthlyScript = Join-Path $PSScriptRoot "monthly_walk_forward.ps1"
$powerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

$requiredPaths = @($dailyScript, $maintenanceHelper, $monthlyScript, $powerShellExe)
if (-not $Unregister -and -not $WhatIfPreference) {
    . (Join-Path $RepoRoot "scripts\dev-python.ps1")
    $pythonExe = Resolve-DevPython -RequiredModules @("duckdb")
    $requiredPaths = @($pythonExe) + $requiredPaths
}
foreach ($required in $requiredPaths) {
    if (-not (Test-Path $required)) {
        throw "Required path not found: $required"
    }
}

$legacyTimerNames = @(
    "MOSS-ChoiceStockDailyRefresh",
    "MOSS-MacroToolkitFreshness",
    "MOSS-MacroToolkitDailyChain"
)

function ConvertTo-CommandLineString {
    param([string[]]$Arguments)

    if (-not $Arguments -or $Arguments.Count -eq 0) {
        return ""
    }
    return " " + ($Arguments -join " ")
}

function Test-TaskExists {
    param([string]$TaskName)
    schtasks /Query /TN $TaskName 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Remove-TaskIfExists {
    param([string]$TaskName)
    if (-not (Test-TaskExists -TaskName $TaskName)) {
        Write-Host "Task $TaskName does not exist; nothing to delete."
        return
    }
    if ($PSCmdlet.ShouldProcess($TaskName, "Delete scheduled task")) {
        schtasks /Delete /TN $TaskName /F | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "schtasks /Delete failed for $TaskName" }
    }
}

function Register-MossTask {
    param(
        [string]$TaskName,
        [string]$ScriptPath,
        [string[]]$ScriptArgs,
        [string[]]$ScheduleArgs,
        [string]$Description
    )
    $scriptArgString = ConvertTo-CommandLineString -Arguments $ScriptArgs
    $actionArgs = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`"$scriptArgString"
    $trString = "`"$powerShellExe`" $actionArgs"
    if (-not $PSCmdlet.ShouldProcess($TaskName, "Register scheduled task ($Description)")) {
        return
    }
    schtasks /Create /TN $TaskName /TR $trString @ScheduleArgs /F /RL LIMITED | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "schtasks /Create failed for $TaskName" }

    # Refine with a proper working directory and resilient settings.
    $taskAction = New-ScheduledTaskAction `
        -Execute $powerShellExe `
        -Argument $actionArgs `
        -WorkingDirectory $RepoRoot
    $taskSettings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 6)
    Set-ScheduledTask -TaskName $TaskName -Action $taskAction -Settings $taskSettings | Out-Null
    Write-Host "Registered $TaskName ($Description)."
}

$dailyScriptArgs = @()
if (-not [string]::IsNullOrWhiteSpace($normalizedVendorSourceIp)) {
    $dailyScriptArgs += @("-VendorSourceIp", $normalizedVendorSourceIp)
}

if ($Unregister) {
    Remove-TaskIfExists -TaskName $DailyTaskName
    Remove-TaskIfExists -TaskName $MonthlyTaskName
    Write-Host "Unregister complete. Legacy timers (if any) were not touched."
    Write-Host "Re-enable legacy timers with: schtasks /Change /TN <name> /ENABLE"
    exit 0
}

Register-MossTask `
    -TaskName $DailyTaskName `
    -ScriptPath $dailyScript `
    -ScriptArgs $dailyScriptArgs `
    -ScheduleArgs @("/SC", "DAILY", "/ST", $DailyTime) `
    -Description "daily $DailyTime, full after-close data chain"

Register-MossTask `
    -TaskName $MonthlyTaskName `
    -ScriptPath $monthlyScript `
    -ScheduleArgs @("/SC", "MONTHLY", "/MO", "FIRST", "/D", "SAT", "/ST", $MonthlyTime) `
    -Description "first Saturday of each month $MonthlyTime, walk-forward validation"

# ------------------------------------------------------------ legacy timers

$enabledLegacy = @()
foreach ($name in $legacyTimerNames) {
    try {
        $task = Get-ScheduledTask -TaskName $name -ErrorAction Stop
        if ($task.State -ne "Disabled") { $enabledLegacy += $name }
    } catch {
        continue
    }
}

if ($DisableLegacyTimers) {
    foreach ($name in $enabledLegacy) {
        if ($PSCmdlet.ShouldProcess($name, "Disable legacy scheduled task")) {
            schtasks /Change /TN $name /DISABLE | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "schtasks /Change /DISABLE failed for $name" }
            Write-Host "Disabled legacy timer $name (re-enable: schtasks /Change /TN $name /ENABLE)."
        }
    }
} elseif ($enabledLegacy.Count -gt 0) {
    Write-Host ""
    Write-Warning ("These legacy per-step timers are still enabled: {0}. " -f ($enabledLegacy -join ", "))
    Write-Warning ("daily_data_refresh.ps1 will SKIP the steps they cover. If you want " +
        "$DailyTaskName to own the whole chain, re-run with -DisableLegacyTimers.")
}

Write-Host ""
Write-Host "Verify:  schtasks /Query /TN $DailyTaskName /V /FO LIST"
Write-Host "         schtasks /Query /TN $MonthlyTaskName /V /FO LIST"
Write-Host "Logs:    $PSScriptRoot\logs\YYYYMMDD.log (daily), monthly-YYYYMMDD.log (monthly)"
Write-Host "Dry run: powershell -File `"$dailyScript`" -DryRun"
