$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:MOSS_AGENT_ENABLED = "true"
$env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS = "1"

Write-Host "[MOSS Agent] Repo root: $root" -ForegroundColor Cyan
Write-Host "[MOSS Agent] MOSS_AGENT_ENABLED=$($env:MOSS_AGENT_ENABLED)" -ForegroundColor DarkGray
Write-Host "[MOSS Agent] MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=$($env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS)" -ForegroundColor DarkGray

& "$root\scripts\dev-api.ps1"
