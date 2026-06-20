param(
  [string]$TeamId = "moss-five-seed",
  [string]$OutputRoot = "",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8795,
  [ValidateSet("start", "open")]
  [string]$Command = "start"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$loopbackHosts = @("127.0.0.1", "localhost", "::1")
if ($loopbackHosts -notcontains $HostName) {
  throw "Hermes dispatch server must bind to loopback only."
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
  $OutputRoot = Join-Path $root ".omx\hermes-teams"
}

$teamDir = Join-Path $OutputRoot $TeamId
if (-not (Test-Path -LiteralPath (Join-Path $teamDir "manifest.json"))) {
  throw "Hermes team manifest not found: $teamDir"
}

$manifestPath = Join-Path $teamDir "manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$dispatchToken = ""
if ($null -ne $manifest.dispatch_token) {
  $dispatchToken = [string]$manifest.dispatch_token
}
if ([string]::IsNullOrWhiteSpace($dispatchToken)) {
  throw "Hermes team dispatch token is missing in manifest.json. Regenerate the team with scripts\start-hermes-agent-team.ps1."
}

$url = "http://$HostName`:$Port"

if ($Command -eq "open") {
  Start-Process $url
  Write-Host "Opened Hermes team dispatch dashboard: $url" -ForegroundColor Cyan
  exit 0
}

Write-Host "Hermes team dispatch dashboard: $url" -ForegroundColor Cyan
Write-Host "Team directory: $teamDir" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C here to stop the dispatch server." -ForegroundColor Yellow
Start-Process $url

python scripts\hermes_team_dispatch_server.py `
  --team-dir $teamDir `
  --host $HostName `
  --port $Port `
  --token $dispatchToken
