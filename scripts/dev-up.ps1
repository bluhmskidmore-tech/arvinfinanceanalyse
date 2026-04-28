$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"

$powershellExe = (Get-Command powershell -ErrorAction Stop).Source
$logRoot = Join-Path $root "tmp-governance\runtime-clean\logs"
New-Item -ItemType Directory -Force $logRoot | Out-Null

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

function Get-NativeScriptProcess {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptName
  )

  return Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -eq "powershell.exe" -and
      $_.CommandLine -like ("*" + $ScriptName + "*")
    } |
    Select-Object -First 1
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

function Quote-CmdArgument {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Value
  )

  return '"' + ($Value -replace '"', '""') + '"'
}

function Assert-PortAvailableForScriptStart {
  param(
    [Parameter(Mandatory = $true)]
    [int]$Port,
    [Parameter(Mandatory = $true)]
    [string]$ScriptName,
    [Parameter(Mandatory = $true)]
    [string]$Description
  )

  $listener = Get-DevListeningPortOwner -Port $Port
  if (-not $listener) {
    return
  }

  $scriptProcess = Get-NativeScriptProcess -ScriptName $ScriptName
  if ($scriptProcess) {
    return
  }

  $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
  $processName = if ($process) { $process.ProcessName } else { "unknown" }
  throw (
    "$Description port $Port already has a listener (PID=$($listener.OwningProcess), process=$processName), " +
    "but $ScriptName is not running. Run scripts\dev-down.ps1 or stop the stale process before dev-up."
  )
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

function Get-RecentLogLines {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [int]$Tail = 40
  )

  if (-not (Test-Path $Path)) {
    return @()
  }

  return @(Get-Content -Path $Path -Tail $Tail -ErrorAction SilentlyContinue)
}

function Invoke-ConcurrentHttpSmoke {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [int]$RequestCount = 4,
    [int]$TimeoutSeconds = 30,
    [string]$Description = "concurrent HTTP smoke"
  )

  $jobs = @()
  try {
    for ($i = 0; $i -lt $RequestCount; $i++) {
      $jobs += Start-Job -ScriptBlock {
        param(
          [string]$RequestUrl,
          [int]$RequestTimeoutSeconds
        )

        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        try {
          $response = Invoke-WebRequest -Uri $RequestUrl -UseBasicParsing -TimeoutSec $RequestTimeoutSeconds
          $sw.Stop()
          [pscustomobject]@{
            Ok = ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
            StatusCode = [int]$response.StatusCode
            Ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
            Error = ""
          }
        } catch {
          $sw.Stop()
          $statusCode = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { -1 }
          [pscustomobject]@{
            Ok = $false
            StatusCode = $statusCode
            Ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
            Error = $_.Exception.Message
          }
        }
      } -ArgumentList $Url,$TimeoutSeconds
    }

    $results = @(Receive-Job -Job $jobs -Wait)
    $failed = @($results | Where-Object { -not $_.Ok })
    if ($failed.Count -gt 0) {
      $sample = ($failed | Select-Object -First 3 | ForEach-Object {
        "status=$($_.StatusCode), ms=$($_.Ms), error=$($_.Error)"
      }) -join "; "
      throw "$Description failed for $Url ($($failed.Count)/$RequestCount failures): $sample"
    }

    $maxMs = ($results | Measure-Object -Property Ms -Maximum).Maximum
    return [pscustomobject]@{
      Count = $results.Count
      MaxMs = [math]::Round($maxMs, 1)
    }
  } finally {
    if ($jobs.Count -gt 0) {
      Remove-Job -Job $jobs -Force -ErrorAction SilentlyContinue
    }
  }
}

function Start-DevScriptDetached {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptName
  )

  $scriptPath = Join-Path $root ("scripts\" + $ScriptName)
  if (-not (Test-Path $scriptPath)) {
    throw "Missing script: $scriptPath"
  }

  $alreadyRunning = Get-NativeScriptProcess -ScriptName $ScriptName

  if ($alreadyRunning) {
    Write-Host "$ScriptName already running (PID=$($alreadyRunning.ProcessId))" -ForegroundColor Yellow
    return [pscustomobject]@{
      Started = $false
      ProcessId = [int]$alreadyRunning.ProcessId
      StdoutPath = $null
      StderrPath = $null
    }
  }

  $logName = [System.IO.Path]::GetFileNameWithoutExtension($ScriptName)
  $stdoutPath = Join-Path $logRoot "$logName.out.log"
  $stderrPath = Join-Path $logRoot "$logName.err.log"
  Remove-Item -Path $stdoutPath,$stderrPath -Force -ErrorAction SilentlyContinue

  $scriptCommand = (
    (Quote-CmdArgument $powershellExe) +
    " -NoProfile -ExecutionPolicy Bypass -File " +
    (Quote-CmdArgument $scriptPath) +
    " 1> " +
    (Quote-CmdArgument $stdoutPath) +
    " 2> " +
    (Quote-CmdArgument $stderrPath)
  )
  $command = "cmd.exe /d /c " + '"' + $scriptCommand + '"'
  $shell = New-Object -ComObject WScript.Shell
  $shell.CurrentDirectory = $root
  $launchResult = $shell.Run($command, 0, $false)
  if ($launchResult -ne 0) {
    throw "$ScriptName launcher failed with exit code $launchResult"
  }

  Start-Sleep -Milliseconds 250
  $process = Get-NativeScriptProcess -ScriptName $ScriptName
  if (-not $process) {
    $stderr = Get-RecentLogLines -Path $stderrPath
    $stdout = Get-RecentLogLines -Path $stdoutPath
    throw (
      "$ScriptName did not remain running after detached launch. " +
      "stdout=$stdoutPath stderr=$stderrPath`n" +
      (($stderr + $stdout) -join "`n")
    ).Trim()
  }

  return [pscustomobject]@{
    Started = $true
    ProcessId = [int]$process.ProcessId
    StdoutPath = $stdoutPath
    StderrPath = $stderrPath
  }
}

& (Join-Path $root "scripts\dev-postgres-up.ps1")
if ($LASTEXITCODE -ne 0) {
  throw "dev-postgres-up.ps1 failed; aborting dev-up startup."
}

$postgresPort = Wait-TcpPort -ListenHost "127.0.0.1" -Port 55432 -Description "local Postgres dev cluster"

Assert-PortAvailableForScriptStart -Port 7888 -ScriptName "dev-api.ps1" -Description "API"
$apiLaunch = Start-DevScriptDetached -ScriptName "dev-api.ps1"
$workerLaunch = Start-DevScriptDetached -ScriptName "dev-worker.ps1"

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
$riskDates = Wait-HttpEndpoint -Url "http://127.0.0.1:7888/api/risk/tensor/dates" -Description "risk tensor dates"
$riskDatesPayload = $riskDates.Content | ConvertFrom-Json
$riskReportDate = @($riskDatesPayload.result.report_dates) | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($riskReportDate)) {
  throw "Risk tensor dates smoke returned no report_dates."
}
$riskTensorSmoke = Invoke-ConcurrentHttpSmoke `
  -Url "http://127.0.0.1:7888/api/risk/tensor?report_date=$riskReportDate" `
  -RequestCount 8 `
  -Description "risk tensor detail concurrent smoke"
$riskDatesSmoke = Invoke-ConcurrentHttpSmoke `
  -Url "http://127.0.0.1:7888/api/risk/tensor/dates" `
  -RequestCount 4 `
  -Description "risk tensor dates concurrent smoke"
$frontendLaunch = Start-DevScriptDetached -ScriptName "dev-frontend.ps1"
$frontendRoot = Wait-HttpEndpoint -Url "http://127.0.0.1:5888" -Description "frontend root"
$keepaliveLaunch = Start-DevScriptDetached -ScriptName "dev-keepalive.ps1"
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
Write-Host "Risk tensor:  $($riskTensorSmoke.Count) detail + $($riskDatesSmoke.Count) dates concurrent checks, report_date=$riskReportDate" -ForegroundColor DarkGray
Write-Host "Frontend:     $($frontendRoot.StatusCode)" -ForegroundColor DarkGray
Write-Host "Worker smoke: $($workerHeartbeat.token)" -ForegroundColor DarkGray
Write-Host "Lineage audit: clean" -ForegroundColor DarkGray
Write-Host "API logs:      $($apiLaunch.StdoutPath) / $($apiLaunch.StderrPath)" -ForegroundColor DarkGray
Write-Host "Worker logs:   $($workerLaunch.StdoutPath) / $($workerLaunch.StderrPath)" -ForegroundColor DarkGray
Write-Host "Frontend logs: $($frontendLaunch.StdoutPath) / $($frontendLaunch.StderrPath)" -ForegroundColor DarkGray
Write-Host "Keepalive:     $($keepaliveLaunch.ProcessId) (log: $logRoot\dev-keepalive.log)" -ForegroundColor DarkGray
exit 0
