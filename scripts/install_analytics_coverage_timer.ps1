# Installs the analytics coverage guard as a host-local daily task.
# The guard is read-only: it alerts on coverage gaps and never materializes anything.

param(
    [string]$TaskName = "MOSS-AnalyticsCoverage",
    [string]$RepoRoot = "F:\MOSS-V3",
    [string]$PythonExe = "C:\Users\arvin\AppData\Local\Python\pythoncore-3.14-64\python.exe",
    [string]$Time = "07:15"
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "analytics_coverage.log"
$receiptPath = Join-Path $logDir "analytics_coverage_receipt.json"
$wrapper = Join-Path $logDir "analytics_coverage_runner.cmd"

@"
@echo off
cd /d "$RepoRoot"
echo ===== %date% %time% =====>> "$logPath"
"$PythonExe" scripts\analytics_coverage_watch.py --run-once --run-kind scheduled --receipt-path "$receiptPath" >> "$logPath" 2>&1
set "watchExit=%ERRORLEVEL%"
if not "%watchExit%"=="0" echo ALERT analytics coverage watch failed with exit %watchExit%>> "$logPath"
exit /b %watchExit%
"@ | Set-Content -Path $wrapper -Encoding ASCII

schtasks /Create `
    /TN $TaskName `
    /TR "`"$wrapper`"" `
    /SC DAILY `
    /ST $Time `
    /F `
    /RL LIMITED | Out-Host

$taskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 15)
Set-ScheduledTask -TaskName $TaskName -Settings $taskSettings | Out-Null


Write-Host "Installed task $TaskName at daily $Time (host local clock)."
Write-Host "The guard is alert-only and read-only: it never writes DuckDB and never repairs a gap."
Write-Host "Covered dates return exit 0; any daily or month-end gap returns nonzero and writes ALERT to the log."
Write-Host "Repair a daily gap with: python -m backend.app.tasks.formal_balance_pipeline --start-date <d> --end-date <d>"
Write-Host "Repair a month-end curve gap with the yield_curve_month_end_backfill job (writes new curve snapshots)."
Write-Host "Wrapper: $wrapper"
Write-Host "Log: $logPath"
Write-Host "Receipt: $receiptPath"
Write-Host "Query: schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Run now: schtasks /Run /TN $TaskName"
Write-Host "Manual check: python scripts\analytics_coverage_watch.py --run-once --receipt-path `"$receiptPath`""
