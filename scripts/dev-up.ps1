$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"

$powershellExe = (Get-Command powershell -ErrorAction Stop).Source

function Wait-HttpEndpoint {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [int]$TimeoutSeconds = 60,
    [string]$Description = "endpoint"
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
        return $response
      }
    } catch {
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)

  throw "Timed out waiting for $Description at $Url"
}

function Wait-TcpPort {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ListenHost,
    [Parameter(Mandatory = $true)]
    [int]$Port,
    [int]$TimeoutSeconds = 30,
    [string]$Description = "tcp port"
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop |
        Where-Object { $_.LocalAddress -in @($ListenHost, '0.0.0.0', '::', '::1') } |
        Select-Object -First 1
      if ($connection) {
        return $connection
      }
    } catch {
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)

  throw ("Timed out waiting for {0} on {1}:{2}" -f $Description, $ListenHost, $Port)
}

function Wait-FileReady {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedToken,
    [int]$TimeoutSeconds = 30,
    [string]$Description = "file readiness"
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    if (Test-Path $Path) {
      try {
        $raw = Get-Content -Path $Path -Raw -Encoding UTF8
        if (-not [string]::IsNullOrWhiteSpace($raw)) {
          $payload = $raw | ConvertFrom-Json
          if ($payload.token -eq $ExpectedToken) {
            return $payload
          }
        }
      } catch {
      }
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)

  throw "Timed out waiting for $Description at $Path"
}

function Assert-NativeProcessRunning {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Description,
    [Parameter(Mandatory = $true)]
    [scriptblock]$Predicate
  )

  $match = Get-CimInstance Win32_Process | Where-Object $Predicate | Select-Object -First 1
  if (-not $match) {
    throw "Expected $Description process to be running, but no matching process was found."
  }
  return $match
}

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
if ($LASTEXITCODE -ne 0) {
  throw "dev-postgres-up.ps1 failed; aborting dev-up startup."
}

$postgresPort = Wait-TcpPort -ListenHost "127.0.0.1" -Port 55432 -Description "local Postgres dev cluster"

Start-NativeScript -ScriptName "dev-api.ps1"
Start-NativeScript -ScriptName "dev-worker.ps1"
Start-NativeScript -ScriptName "dev-frontend.ps1"

$workerHeartbeatPath = Join-Path $root "tmp-governance\runtime-clean\governance\dev-worker-heartbeat.json"
$workerHeartbeatToken = [guid]::NewGuid().ToString("N")
Remove-Item -Path $workerHeartbeatPath -Force -ErrorAction SilentlyContinue
$pythonExe = (Get-Command python -ErrorAction Stop).Source
& $pythonExe -c "from backend.app.tasks.dev_health import write_dev_worker_heartbeat; write_dev_worker_heartbeat.send(heartbeat_path=r'$workerHeartbeatPath', token=r'$workerHeartbeatToken')"
if ($LASTEXITCODE -ne 0) {
  throw "Failed to enqueue dev worker heartbeat smoke task."
}

$apiHealth = Wait-HttpEndpoint -Url "http://127.0.0.1:7888/health" -Description "API health"
$bondDates = Wait-HttpEndpoint -Url "http://127.0.0.1:7888/api/bond-analytics/dates" -Description "bond analytics dates"
$frontendRoot = Wait-HttpEndpoint -Url "http://127.0.0.1:5888" -Description "frontend root"
$workerHeartbeat = Wait-FileReady -Path $workerHeartbeatPath -ExpectedToken $workerHeartbeatToken -Description "worker heartbeat"

$apiProcess = Assert-NativeProcessRunning -Description "API" -Predicate {
  $_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app.main:app*"
}
$workerProcess = Assert-NativeProcessRunning -Description "worker" -Predicate {
  $_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app.tasks.worker_bootstrap*"
}
$frontendProcess = Assert-NativeProcessRunning -Description "frontend" -Predicate {
  $_.Name -eq "node.exe" -and
  $_.CommandLine -like ("*" + (Join-Path $root "frontend") + "*") -and
  $_.CommandLine -like "*vite*"
}

$audit = python "$root\scripts\audit_governance_lineage.py" --governance-dir (Join-Path $root "data\governance")
$auditSummary = $audit | ConvertFrom-Json
if ($auditSummary.dirty_rows -ne 0) {
  throw "Governance lineage audit failed: dirty_rows=$($auditSummary.dirty_rows)"
}

Write-Host "Native MOSS dev stack launched." -ForegroundColor Cyan
Write-Host "API:      http://127.0.0.1:7888" -ForegroundColor Gray
Write-Host "Frontend: http://127.0.0.1:5888" -ForegroundColor Gray
Write-Host "Postgres: postgresql://moss:moss@127.0.0.1:55432/moss" -ForegroundColor Gray
Write-Host "API PID:      $($apiProcess.ProcessId)" -ForegroundColor DarkGray
Write-Host "Worker PID:   $($workerProcess.ProcessId)" -ForegroundColor DarkGray
Write-Host "Frontend PID: $($frontendProcess.ProcessId)" -ForegroundColor DarkGray
Write-Host "Postgres PID: $($postgresPort.OwningProcess)" -ForegroundColor DarkGray
Write-Host "API health:   $($apiHealth.StatusCode)" -ForegroundColor DarkGray
Write-Host "Bond dates:   $($bondDates.StatusCode)" -ForegroundColor DarkGray
Write-Host "Frontend:     $($frontendRoot.StatusCode)" -ForegroundColor DarkGray
Write-Host "Worker smoke: $($workerHeartbeat.token)" -ForegroundColor DarkGray
Write-Host "Lineage audit: clean" -ForegroundColor DarkGray
exit 0
