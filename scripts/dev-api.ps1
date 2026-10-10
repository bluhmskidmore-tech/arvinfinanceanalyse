param(
  [switch]$SkipStartupStorageMigrations
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
. "$root\scripts\dev-runtime-common.ps1"
Assert-DevRuntimeAllowed
Set-Location $root
. "$root\scripts\dev-env.ps1"

# This native entrypoint always uses the local OS-session trust boundary.
# Reject explicit opt-outs/unknown input instead of silently overriding them.
if (-not (Test-Path Env:MOSS_LOCAL_ONLY_API)) {
  $env:MOSS_LOCAL_ONLY_API = "1"
} elseif ($env:MOSS_LOCAL_ONLY_API.Trim().ToLowerInvariant() -notin @("1", "true", "yes", "on")) {
  throw "Native dev-api requires MOSS_LOCAL_ONLY_API=true; explicit disabled or invalid values are refused."
}
$env:MOSS_LOCAL_ONLY_API = "1"

. "$root\scripts\dev-python.ps1"
$python = Resolve-DevPython
$systemReadPublicationProbe = @(
  & $python -c "import sys; from backend.app.governance.settings import get_settings; s = get_settings(); (s.environment == 'development' and s.local_only_api) or sys.exit('Native dev-api local entrance policy is not active'); print('1' if s.system_read_publication_enabled else '0')"
)
$systemReadPublicationProbeExitCode = $LASTEXITCODE
if ($systemReadPublicationProbeExitCode -ne 0) {
  throw "Unable to verify native local entrance policy/system_read_publication_enabled; aborting dev-api startup."
}
if (
  $systemReadPublicationProbe.Count -ne 1 -or
  ($systemReadPublicationProbe[0] -ne "0" -and $systemReadPublicationProbe[0] -ne "1")
) {
  throw "Invalid system_read_publication_enabled probe output; expected exactly '0' or '1'."
}
$systemReadPublicationEnabled = $systemReadPublicationProbe[0] -eq "1"

$hadStartupStorageMigrationSetting = Test-Path Env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS
$originalStartupStorageMigrationSetting = $env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS
$forcedImmutableStartup = $systemReadPublicationEnabled -and -not $SkipStartupStorageMigrations
if ($SkipStartupStorageMigrations -or $systemReadPublicationEnabled) {
  $env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS = "1"
}

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

try {
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

  if (-not $systemReadPublicationEnabled) {
    Invoke-DevRuntimeAction {
      & "$root\scripts\dev-postgres-up.ps1"
      if ($LASTEXITCODE -ne 0) {
        throw "dev-postgres-up.ps1 failed; aborting dev-api startup."
      }
      Assert-DevBootstrapStorageReady -ProbeLabel "dev-api"
    }
  }

  $args = @("--host", "127.0.0.1", "--port", "$port")
  if ($env:MOSS_DEV_RELOAD -eq "1") {
    $args += "--reload"
  }

  if ([string]::IsNullOrWhiteSpace($env:MOSS_HOME_SNAPSHOT_PREWARM_ENABLED)) {
    $env:MOSS_HOME_SNAPSHOT_PREWARM_ENABLED = "1"
  }

  if ([string]::IsNullOrWhiteSpace($env:MOSS_MARKET_HOME_PREWARM_ENABLED)) {
    $env:MOSS_MARKET_HOME_PREWARM_ENABLED = "1"
  }

  Invoke-DevRuntimeProcess -Command (@($python, "-m", "uvicorn", "backend.app.main:app") + $args)
} finally {
  if ($forcedImmutableStartup) {
    if ($hadStartupStorageMigrationSetting) {
      $env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS = $originalStartupStorageMigrationSetting
    } else {
      Remove-Item Env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS -ErrorAction SilentlyContinue
    }
  }
}
