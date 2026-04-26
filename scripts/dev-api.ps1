$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"
Assert-DevBootstrapStorageReady -ProbeLabel "dev-api"
. "$root\scripts\dev-python.ps1"
$python = Resolve-DevPython

function Get-DevListeningPortOwner {
  param(
    [Parameter(Mandatory = $true)]
    [int]$Port
  )

  $pattern = "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$"
  $line = netstat -ano |
    Where-Object { $_ -match $pattern } |
    Select-Object -First 1
  if (-not $line) {
    return $null
  }

  if ($line -match $pattern) {
    return [pscustomobject]@{
      OwningProcess = [int]$Matches[1]
      Line = $line
    }
  }

  return $null
}

$port = 7888
$listener = Get-DevListeningPortOwner -Port $port
if ($listener) {
  $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
  $processName = if ($process) { $process.ProcessName } else { "unknown" }
  throw (
    "Port $port already has a listener (PID=$($listener.OwningProcess), process=$processName). " +
    "Run scripts\dev-down.ps1 or stop the stale API process before starting dev-api.ps1."
  )
}

$args = @("--host", "127.0.0.1", "--port", "$port")
if ($env:MOSS_DEV_RELOAD -eq "1") {
  $args += "--reload"
}

& $python -m uvicorn backend.app.main:app @args
