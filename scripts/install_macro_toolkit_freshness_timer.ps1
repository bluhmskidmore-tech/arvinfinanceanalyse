# Optional local installer for macro-toolkit freshness timer (Windows Task Scheduler).
# Not part of the enablement packet; operators run this deliberately on an approved host.
# Local installs use --run-once (no Dramatiq worker). Production hosts with a live worker
# should prefer the packet's --enqueue command instead.

param(
    [string]$TaskName = "MOSS-MacroToolkitFreshness",
    [string]$RepoRoot = "F:\MOSS-V3",
    [string]$PythonExe = "C:\Users\arvin\AppData\Local\Python\pythoncore-3.14-64\python.exe",
    # Host-local clock. On a UTC-4 host, 06:30 ≈ Asia/Shanghai 18:30.
    [string]$Time = "06:30",
    [string]$ChoiceSourceIp = ""
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "macro_toolkit_freshness_refresh.log"
$receiptPath = Join-Path $logDir "macro_toolkit_freshness_refresh_receipt.json"
$wrapper = Join-Path $logDir "macro_toolkit_freshness_refresh_runner.cmd"
$choiceSourceArg = if ([string]::IsNullOrWhiteSpace($ChoiceSourceIp)) {
    ""
} else {
    try {
        $parsedChoiceSourceIp = [System.Net.IPAddress]::Parse($ChoiceSourceIp)
    } catch {
        throw "ChoiceSourceIp must be a valid IPv4 address."
    }
    if ($parsedChoiceSourceIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw "ChoiceSourceIp must be a valid IPv4 address."
    }
    " --choice-source-ip `"$($parsedChoiceSourceIp.ToString())`""
}

@"
@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "$RepoRoot"
echo ===== %date% %time% =====>> "$logPath"
"$PythonExe" scripts\macro_toolkit_freshness_refresh.py --run-once --run-kind scheduled --receipt-path "$receiptPath"$choiceSourceArg >> "$logPath" 2>&1
set "refreshExit=!ERRORLEVEL!"
if not "!refreshExit!"=="0" echo ALERT macro toolkit freshness refresh failed with exit !refreshExit!>> "$logPath"
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
Write-Host "For Asia/Shanghai 18:30 on a UTC-4 host, use -Time 06:30 (default)."
Write-Host "The task may run on battery, will not stop when power changes, and catches up after a missed start."
Write-Host "The runner starts in a hidden, non-interactive PowerShell process."
Write-Host "Failures return nonzero, remain visible in Task Scheduler, and write ALERT to the log."
Write-Host "Wrapper: $wrapper"
Write-Host "Log: $logPath"
Write-Host "Receipt: $receiptPath"
Write-Host "Query: schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Pre-enable: python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage pre-enable"
Write-Host "Post-enable: python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage post-enable --receipt-path `"$receiptPath`""
