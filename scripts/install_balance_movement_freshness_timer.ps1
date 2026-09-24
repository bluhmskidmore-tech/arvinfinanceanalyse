# Installs the balance-movement freshness guard as a host-local daily task.

param(
    [string]$TaskName = "MOSS-BalanceMovementFreshness",
    [string]$RepoRoot = "F:\MOSS-V3",
    [string]$PythonExe = "C:\Users\arvin\AppData\Local\Python\pythoncore-3.14-64\python.exe",
    [string]$Time = "06:45"
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "balance_movement_freshness.log"
$receiptPath = Join-Path $logDir "balance_movement_freshness_receipt.json"
$wrapper = Join-Path $logDir "balance_movement_freshness_runner.cmd"

@"
@echo off
cd /d "$RepoRoot"
echo ===== %date% %time% =====>> "$logPath"
"$PythonExe" scripts\balance_movement_freshness_watch.py --run-once --run-kind scheduled --receipt-path "$receiptPath" >> "$logPath" 2>&1
set "watchExit=%ERRORLEVEL%"
if not "%watchExit%"=="0" echo ALERT balance movement freshness watch failed with exit %watchExit%>> "$logPath"
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
Write-Host "The task is idempotent: fresh dates are a no-op; lagging dates are repaired."
Write-Host "Failures return nonzero, remain visible in Task Scheduler, and write ALERT to the log."
Write-Host "Wrapper: $wrapper"
Write-Host "Log: $logPath"
Write-Host "Receipt: $receiptPath"
Write-Host "Query: schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Run now: schtasks /Run /TN $TaskName"
Write-Host "Manual check: python scripts\balance_movement_freshness_watch.py --run-once --receipt-path `"$receiptPath`""
