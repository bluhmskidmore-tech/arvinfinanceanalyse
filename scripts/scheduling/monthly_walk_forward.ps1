<#
.SYNOPSIS
  Monthly walk-forward validation run with dated report archival.

.DESCRIPTION
  Runs scripts\run_walk_forward_validation.py against data\moss.duckdb and
  archives the Markdown report (plus the machine-readable JSON the script
  writes next to it) as docs\strategy-reports\walk-forward-YYYYMMDD.md/.json.

  Appends all output to scripts\scheduling\logs\monthly-YYYYMMDD.log.
  Exit code is the validation script's own exit code (0 = report written).

.PARAMETER DryRun
  Print the command that would run, without executing it.

.PARAMETER ReportDate
  Date suffix for the archived report (default: today, yyyyMMdd).
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$RepoRoot = "",
    [string]$PythonExe = "",
    [string]$ReportDate = ""
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
if ([string]::IsNullOrWhiteSpace($ReportDate)) {
    $ReportDate = Get-Date -Format "yyyyMMdd"
}
if ($ReportDate -notmatch '^\d{8}$') {
    throw "ReportDate must be yyyyMMdd, got: $ReportDate"
}

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ("monthly-{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logPath -Value $line -Encoding UTF8
    Write-Host $line
}

$reportPath = "docs\strategy-reports\walk-forward-$ReportDate.md"
$scriptArgs = @(
    "scripts\run_walk_forward_validation.py",
    "--db-path", "data\moss.duckdb",
    "--report-path", $reportPath
)

Write-Log "===== monthly_walk_forward start (DryRun=$DryRun, ReportDate=$ReportDate) ====="
Write-Log ("command: `"{0}`" {1}" -f $PythonExe, ($scriptArgs -join " "))

if ($DryRun) {
    Write-Log "dry run: nothing executed; report would land at $reportPath (+ .json)"
    Write-Log "===== dry run complete; exit 0 ====="
    exit 0
}

Set-Location $RepoRoot
$env:PYTHONIOENCODING = "utf-8"

$started = Get-Date
$output = & $PythonExe @scriptArgs 2>&1
$exitCode = $LASTEXITCODE
foreach ($line in $output) {
    Add-Content -Path $logPath -Value ("    " + [string]$line) -Encoding UTF8
}
$elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)

if ($exitCode -eq 0) {
    Write-Log ("OK exit=0 elapsed={0}s report={1}" -f $elapsed, $reportPath)
} else {
    Write-Log ("ALERT walk-forward validation failed exit={0} elapsed={1}s" -f $exitCode, $elapsed)
}
Write-Log "===== monthly_walk_forward finished (exit $exitCode) ====="
exit $exitCode
