$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Wait-ProcessStopped {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Description,
    [Parameter(Mandatory = $true)]
    [scriptblock]$Predicate,
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    $match = Get-CimInstance Win32_Process | Where-Object $Predicate | Select-Object -First 1
    if (-not $match) {
      return
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)

  throw "Timed out waiting for $Description process to stop."
}

function Wait-PortsClosed {
  param(
    [Parameter(Mandatory = $true)]
    [int[]]$Ports,
    [int[]]$OwningProcessIds = @(),
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    $listening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
      Where-Object {
        ($Ports -contains $_.LocalPort) -and
        (($OwningProcessIds.Count -eq 0) -or ($OwningProcessIds -contains $_.OwningProcess))
      }
    if (-not $listening) {
      return
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)

  throw ("Timed out waiting for ports to close: {0}" -f (($Ports | Sort-Object) -join ", "))
}

function Stop-NativeProcesses {
  $targets = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq "powershell.exe" -and (
      $_.CommandLine -like "*scripts\dev-api.ps1*" -or
      $_.CommandLine -like "*scripts\dev-worker.ps1*" -or
      $_.CommandLine -like "*scripts\dev-frontend.ps1*"
    )) -or
    ($_.Name -eq "python.exe" -and (
      $_.CommandLine -like "*backend.app.main:app*" -or
      $_.CommandLine -like "*backend.app.tasks.worker_bootstrap*"
    )) -or
    ($_.Name -eq "node.exe" -and (
      $_.CommandLine -like ("*" + (Join-Path $root "frontend") + "*") -and
      $_.CommandLine -like "*vite*"
    ))
  }

  $targetIds = @($targets | Select-Object -ExpandProperty ProcessId)
  foreach ($proc in $targets) {
    try {
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
    } catch {
    }
  }

  $spawnChildren = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and
    $_.CommandLine -like "*spawn_main*" -and
    ($targetIds -contains $_.ParentProcessId)
  }
  foreach ($proc in $spawnChildren) {
    try {
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
    } catch {
    }
  }

  return [pscustomobject]@{
    TargetIds = $targetIds
  }
}

$stopped = Stop-NativeProcesses
& (Join-Path $root "scripts\dev-postgres-down.ps1")

Wait-ProcessStopped -Description "API" -Predicate {
  $_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app.main:app*"
}
Wait-ProcessStopped -Description "worker" -Predicate {
  $_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app.tasks.worker_bootstrap*"
}
Wait-ProcessStopped -Description "frontend" -Predicate {
  $_.Name -eq "node.exe" -and
  $_.CommandLine -like ("*" + (Join-Path $root "frontend") + "*") -and
  $_.CommandLine -like "*vite*"
}
Wait-PortsClosed -Ports @(7888, 5888) -OwningProcessIds $stopped.TargetIds

$postgresStatusRaw = & (Join-Path $root "scripts\dev-postgres-status.ps1")
if ($LASTEXITCODE -ne 0) {
  throw "dev-postgres-status.ps1 failed during teardown verification."
}
$postgresStatusJson = @($postgresStatusRaw | Where-Object { $_ -match '^\s*\{.*\}\s*$' } | Select-Object -Last 1)
if (-not $postgresStatusJson) {
  throw "dev-postgres-status.ps1 did not emit a JSON status payload."
}
$postgresStatus = $postgresStatusJson | ConvertFrom-Json
if ($postgresStatus.running) {
  throw "Local PostgreSQL dev cluster still reports running=true after teardown."
}

Write-Host "Native MOSS dev stack stopped." -ForegroundColor Cyan
