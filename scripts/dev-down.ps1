$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

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
}

Stop-NativeProcesses
& (Join-Path $root "scripts\dev-postgres-down.ps1")

Write-Host "Native MOSS dev stack stopped." -ForegroundColor Cyan
