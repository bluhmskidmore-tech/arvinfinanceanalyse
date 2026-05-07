$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:MOSS_AGENT_ENABLED = "true"
$env:MOSS_AGENT_PROVIDER = "hermes"
$env:MOSS_AGENT_HERMES_HOME = "/home/hermes/.hermes-moss"
$env:MOSS_AGENT_HERMES_TRANSPORT = "bridge"
$env:MOSS_AGENT_HERMES_BRIDGE_URL = "http://127.0.0.1:7891"
$env:MOSS_AGENT_HERMES_TOOLSETS = "file"
$env:MOSS_DEV_API_SCRIPT = "dev-agent-api.ps1"
$env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS = "1"

Write-Host "[MOSS Agent] Repo root: $root" -ForegroundColor Cyan
Write-Host "[MOSS Agent] MOSS_AGENT_ENABLED=$($env:MOSS_AGENT_ENABLED)" -ForegroundColor DarkGray
Write-Host "[MOSS Agent] MOSS_AGENT_PROVIDER=$($env:MOSS_AGENT_PROVIDER)" -ForegroundColor DarkGray
Write-Host "[MOSS Agent] MOSS_AGENT_HERMES_HOME=$($env:MOSS_AGENT_HERMES_HOME)" -ForegroundColor DarkGray
Write-Host "[MOSS Agent] MOSS_AGENT_HERMES_TRANSPORT=$($env:MOSS_AGENT_HERMES_TRANSPORT)" -ForegroundColor DarkGray
Write-Host "[MOSS Agent] MOSS_AGENT_HERMES_BRIDGE_URL=$($env:MOSS_AGENT_HERMES_BRIDGE_URL)" -ForegroundColor DarkGray
Write-Host "[MOSS Agent] MOSS_AGENT_HERMES_TOOLSETS=$($env:MOSS_AGENT_HERMES_TOOLSETS)" -ForegroundColor DarkGray
Write-Host "[MOSS Agent] MOSS_DEV_API_SCRIPT=$($env:MOSS_DEV_API_SCRIPT)" -ForegroundColor DarkGray
Write-Host "[MOSS Agent] MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=$($env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS)" -ForegroundColor DarkGray

& "$root\scripts\dev-api.ps1"
