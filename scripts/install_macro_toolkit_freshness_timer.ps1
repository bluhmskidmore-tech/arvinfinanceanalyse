# Optional local installer for macro-toolkit freshness timer (Windows Task Scheduler).
# Not part of the enablement packet; operators run this deliberately on an approved host.

param(
    [string]$TaskName = "MOSS-MacroToolkitFreshness",
    [string]$RepoRoot = "F:\MOSS-V3",
    [string]$PythonExe = "C:\Users\arvin\AppData\Local\Python\pythoncore-3.14-64\python.exe",
    [string]$Time = "06:30"
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "macro_toolkit_freshness_refresh.log"
$wrapper = Join-Path $logDir "macro_toolkit_freshness_refresh_runner.cmd"

@"
@echo off
cd /d "$RepoRoot"
echo ===== %date% %time% =====>> "$logPath"
"$PythonExe" scripts\macro_toolkit_freshness_refresh.py --run-once >> "$logPath" 2>&1
"@ | Set-Content -Path $wrapper -Encoding ASCII

schtasks /Create /TN $TaskName /TR "`"$wrapper`"" /SC DAILY /ST $Time /F /RL LIMITED | Out-Host
Write-Host "Installed task $TaskName at daily $Time (host local clock)."
Write-Host "For Asia/Shanghai 18:30 on a UTC-4 host, use -Time 06:30 (default)."
Write-Host "Wrapper: $wrapper"
Write-Host "Log: $logPath"
Write-Host "Query: schtasks /Query /TN $TaskName /V /FO LIST"
