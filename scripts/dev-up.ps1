$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$powershellExe = (Get-Command powershell -ErrorAction Stop).Source

function Start-NativeScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptName
  )

  $scriptPath = Join-Path $root ("scripts\" + $ScriptName)
  if (-not (Test-Path $scriptPath)) {
    throw "Missing script: $scriptPath"
  }

  $alreadyRunning = Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -eq "powershell.exe" -and
      $_.CommandLine -like ("*" + $ScriptName + "*")
    } |
    Select-Object -First 1

  if ($alreadyRunning) {
    Write-Host "$ScriptName already running (PID=$($alreadyRunning.ProcessId))" -ForegroundColor Yellow
    return
  }

  Start-Process -FilePath $powershellExe `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath) `
    -WorkingDirectory $root | Out-Null
}

& (Join-Path $root "scripts\dev-postgres-up.ps1")

Start-NativeScript -ScriptName "dev-api.ps1"
Start-NativeScript -ScriptName "dev-worker.ps1"
Start-NativeScript -ScriptName "dev-frontend.ps1"

Write-Host "Native MOSS dev stack launched." -ForegroundColor Cyan
Write-Host "API:      http://127.0.0.1:7888" -ForegroundColor Gray
Write-Host "Frontend: http://127.0.0.1:5888" -ForegroundColor Gray
Write-Host "Postgres: postgresql://moss:moss@127.0.0.1:55432/moss" -ForegroundColor Gray
