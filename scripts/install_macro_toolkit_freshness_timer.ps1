# Optional local installer for macro-toolkit freshness timer (Windows Task Scheduler).
# Not part of the enablement packet; operators run this deliberately on an approved host.
# Local installs use --run-once (no Dramatiq worker). Production hosts with a live worker
# should prefer the packet's --enqueue command instead.

param(
    [string]$TaskName = "MOSS-MacroToolkitFreshness",
    [string]$RepoRoot = "F:\MOSS-V3",
    [string]$PythonExe = "C:\Users\arvin\AppData\Local\Python\pythoncore-3.14-64\python.exe",
    # Host-local clock. On a UTC-4 host, 06:30 ≈ Asia/Shanghai 18:30.
    [string]$Time = "06:30"
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "macro_toolkit_freshness_refresh.log"
$receiptPath = Join-Path $logDir "macro_toolkit_freshness_refresh_receipt.json"
$wrapper = Join-Path $logDir "macro_toolkit_freshness_refresh_runner.cmd"

@"
@echo off
cd /d "$RepoRoot"
echo ===== %date% %time% =====>> "$logPath"
"$PythonExe" scripts\macro_toolkit_freshness_refresh.py --run-once --run-kind scheduled --receipt-path "$receiptPath" >> "$logPath" 2>&1
"@ | Set-Content -Path $wrapper -Encoding ASCII

schtasks /Create /TN $TaskName /TR "`"$wrapper`"" /SC DAILY /ST $Time /F /RL LIMITED | Out-Host
Write-Host "Installed task $TaskName at daily $Time (host local clock)."
Write-Host "For Asia/Shanghai 18:30 on a UTC-4 host, use -Time 06:30 (default)."
Write-Host "Wrapper: $wrapper"
Write-Host "Log: $logPath"
Write-Host "Receipt: $receiptPath"
Write-Host "Query: schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Pre-enable: python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage pre-enable"
Write-Host "Post-enable: python scripts/macro_toolkit_freshness_refresh_timer_preflight.py --stage post-enable --receipt-path `"$receiptPath`""
