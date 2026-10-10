# Optional local installer for the macro-toolkit daily model-chain timer (Windows Task Scheduler).
# Runs after the freshness refresh timer (default 18:30 host clock) so the chain
# consumes freshly refreshed vendor data. Uses the repo venv python because the
# model scripts depend on venv-only packages (arch, duckdb, pandas).

param(
    [string]$TaskName = "MOSS-MacroToolkitDailyChain",
    [string]$RepoRoot = "F:\MOSS-V3",
    [string]$PythonExe = "F:\MOSS-V3\.venv\Scripts\python.exe",
    [string]$Time = "19:10"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $PythonExe)) {
    throw "PythonExe not found: $PythonExe"
}
$logDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "macro_toolkit_daily_chain.log"
$receiptPath = Join-Path $logDir "macro_toolkit_daily_chain_receipt.json"
$wrapper = Join-Path $logDir "macro_toolkit_daily_chain_runner.cmd"

@"
@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "$RepoRoot"
set "PYTHONIOENCODING=utf-8"
echo ===== %date% %time% =====>> "$logPath"
"$PythonExe" scripts\macro_toolkit_daily_chain.py --run-once --run-kind scheduled --receipt-path "$receiptPath" >> "$logPath" 2>&1
set "chainExit=!ERRORLEVEL!"
if not "!chainExit!"=="0" echo ALERT macro toolkit daily chain failed with exit !chainExit!>> "$logPath"
exit /b !chainExit!
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
Write-Host "Sequence: MOSS-MacroToolkitFreshness refreshes vendor data first (default 18:30);"
Write-Host "this task then recomputes the full ten-model chain against the fresh data."
Write-Host "Failures return nonzero, remain visible in Task Scheduler, and write ALERT to the log."
Write-Host "Wrapper: $wrapper"
Write-Host "Log: $logPath"
Write-Host "Receipt: $receiptPath"
Write-Host "Query: schtasks /Query /TN $TaskName /V /FO LIST"
