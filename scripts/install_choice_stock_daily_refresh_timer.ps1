# Optional local installer for the daily Choice-stock materialization timer (Windows Task Scheduler).
# Mirrors install_macro_toolkit_freshness_timer.ps1: operators run this deliberately on an approved host.
# Local installs use --run-once (no Dramatiq worker required).

param(
    [string]$TaskName = "MOSS-ChoiceStockDailyRefresh",
    [string]$RepoRoot = "F:\MOSS-V3",
    [string]$PythonExe = "F:\MOSS-V3\.venv\Scripts\python.exe",
    # Host-local clock. On an Asia/Shanghai host, 18:45 runs after the A-share close data lands.
    [string]$Time = "18:45",
    [string]$VendorSourceIp = ""
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "choice_stock_daily_refresh.log"
$receiptPath = Join-Path $logDir "choice_stock_daily_refresh_receipt.json"
$wrapper = Join-Path $logDir "choice_stock_daily_refresh_runner.cmd"
$vendorSourceArg = if ([string]::IsNullOrWhiteSpace($VendorSourceIp)) {
    ""
} else {
    try {
        $parsedVendorSourceIp = [System.Net.IPAddress]::Parse($VendorSourceIp)
    } catch {
        throw "VendorSourceIp must be a valid IPv4 address."
    }
    if ($parsedVendorSourceIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw "VendorSourceIp must be a valid IPv4 address."
    }
    " --vendor-source-ip `"$($parsedVendorSourceIp.ToString())`""
}

@"
@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "$RepoRoot"
echo ===== %date% %time% =====>> "$logPath"
"$PythonExe" scripts\choice_stock_daily_refresh.py --run-once --run-kind scheduled --receipt-path "$receiptPath"$vendorSourceArg >> "$logPath" 2>&1
set "refreshExit=!ERRORLEVEL!"
if not "!refreshExit!"=="0" echo ALERT choice stock daily refresh failed with exit !refreshExit!>> "$logPath"
exit /b !refreshExit!
"@ | Set-Content -Path $wrapper -Encoding ASCII

schtasks /Create /TN $TaskName /TR "`"$wrapper`"" /SC DAILY /ST $Time /F /RL LIMITED | Out-Host
$powerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$escapedWrapper = $wrapper.Replace("'", "''")
$actionArgs = "-NoProfile -NonInteractive -WindowStyle Hidden -Command `"& '$escapedWrapper'; exit `$LASTEXITCODE`""
$taskAction = New-ScheduledTaskAction `
    -Execute $powerShellExe `
    -Argument $actionArgs `
    -WorkingDirectory $RepoRoot
$taskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable
Set-ScheduledTask -TaskName $TaskName -Action $taskAction -Settings $taskSettings | Out-Null

Write-Host "Installed task $TaskName at daily $Time (host local clock)."
Write-Host "Weekends are skipped by the CLI unless --as-of-date is passed explicitly."
Write-Host "The task may run on battery, will not stop when power changes, and catches up after a missed start."
Write-Host "Failures return nonzero, remain visible in Task Scheduler, and write ALERT to the log."
Write-Host "Wrapper: $wrapper"
Write-Host "Log: $logPath"
Write-Host "Receipt: $receiptPath"
Write-Host "Query: schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Latest run is also visible at GET /ui/macro/toolkit/choice-stock/refresh-status."
