$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"
. "$root\scripts\dev-python.ps1"

$powershellExe = (Get-Command powershell -ErrorAction Stop).Source
$logRoot = Join-Path $root "tmp-governance\runtime-clean\logs"
New-Item -ItemType Directory -Force $logRoot | Out-Null
$script:ProcessInspectionAvailable = $true
$allowedApiScriptNames = @("dev-api.ps1", "dev-agent-api.ps1")
$apiScriptName = if ([string]::IsNullOrWhiteSpace($env:MOSS_DEV_API_SCRIPT)) {
  "dev-api.ps1"
} else {
  [string]$env:MOSS_DEV_API_SCRIPT
}
if ($apiScriptName -notin $allowedApiScriptNames) {
  throw "MOSS_DEV_API_SCRIPT must be one of: $($allowedApiScriptNames -join ', '). Received: $apiScriptName"
}
$apiLogName = [System.IO.Path]::GetFileNameWithoutExtension($apiScriptName)
$agentDevMode = $apiScriptName -eq "dev-agent-api.ps1"

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
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
      $connectTask = $client.ConnectAsync($ListenHost, $Port)
      if ($connectTask.Wait(500) -and $client.Connected) {
        $owner = Get-DevListeningPortOwner -Port $Port
        return [pscustomobject]@{
          LocalAddress = $ListenHost
          LocalPort = $Port
          OwningProcess = if ($owner) { $owner.OwningProcess } else { $null }
        }
      }
    } catch {
    } finally {
      $client.Dispose()
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

  try {
    return Get-CimInstance Win32_Process |
      Where-Object {
        $_.Name -eq "powershell.exe" -and
        $_.CommandLine -like ("*" + $ScriptName + "*")
      } |
      Select-Object -First 1
  } catch {
    $script:ProcessInspectionAvailable = $false
    Write-Warning "process lookup failed for ${ScriptName}: $($_.Exception.Message)"
    return $null
  }
}

function Test-NativeWorkerProcess {
  param(
    [Parameter(Mandatory = $true)]
    [object]$Process
  )

  return (
    $Process.Name -eq "python.exe" -and (
      $Process.CommandLine -like "*backend.app.tasks.dev_worker_runner*" -or
      $Process.CommandLine -like "*backend.app.tasks.worker_bootstrap*"
    )
  )
}

function Get-NativeWorkerProcess {
  try {
    return Get-CimInstance Win32_Process |
      Where-Object { Test-NativeWorkerProcess -Process $_ } |
      Select-Object -First 1
  } catch {
    $script:ProcessInspectionAvailable = $false
    Write-Warning "process lookup failed for native worker: $($_.Exception.Message)"
    return $null
  }
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

function Find-DevScriptLaunch {
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
    return $null
  }

  $scriptProcess = Get-NativeScriptProcess -ScriptName $ScriptName
  if (-not $script:ProcessInspectionAvailable) {
    Write-Warning "$Description port $Port already has a listener (PID=$($listener.OwningProcess)); process verification unavailable."
    return [pscustomobject]@{
      Started = $false
      ProcessId = $listener.OwningProcess
      PortVerifiedOnly = $true
    }
  }
  if ($scriptProcess) {
    return [pscustomobject]@{
      Started = $false
      ProcessId = [int]$scriptProcess.ProcessId
      PortVerifiedOnly = $false
    }
  }

  $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
  $processName = if ($process) { $process.ProcessName } else { "unknown" }
  throw (
    "$Description port $Port already has a listener (PID=$($listener.OwningProcess), process=$processName), " +
    "but $ScriptName is not running. Run scripts\dev-down.ps1 or stop the stale process before dev-up."
  )
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

  $existingLaunch = Find-DevScriptLaunch -Port $Port -ScriptName $ScriptName -Description $Description
  return $existingLaunch
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

  try {
    $match = Get-CimInstance Win32_Process | Where-Object $Predicate | Select-Object -First 1
  } catch {
    $script:ProcessInspectionAvailable = $false
    Write-Warning "$Description process verification unavailable: $($_.Exception.Message)"
    return [pscustomobject]@{
      ProcessId = "unknown"
    }
  }
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

function Format-RecentLogSnippet {
  param(
    [string[]]$LogPaths = @(),
    [int]$Tail = 40
  )

  $blocks = @()
  foreach ($path in ($LogPaths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)) {
    $lines = Get-RecentLogLines -Path $path -Tail $Tail
    if ($lines.Count -gt 0) {
      $blocks += "---- $path ----`n$($lines -join "`n")"
    }
  }

  return ($blocks -join "`n")
}

function Add-LogContext {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Message,
    [string[]]$LogPaths = @()
  )

  $snippet = Format-RecentLogSnippet -LogPaths $LogPaths
  if ([string]::IsNullOrWhiteSpace($snippet)) {
    return $Message
  }

  return "$Message`nRecent logs:`n$snippet"
}

function Wait-HttpEndpointWithLogs {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [int]$TimeoutSeconds = 60,
    [string]$Description = "endpoint",
    [string[]]$LogPaths = @()
  )

  try {
    return Wait-HttpEndpoint -Url $Url -TimeoutSeconds $TimeoutSeconds -Description $Description
  } catch {
    throw (Add-LogContext -Message ($_.Exception.Message) -LogPaths $LogPaths)
  }
}

function Wait-JsonStatusOkEndpointWithLogs {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [int]$TimeoutSeconds = 60,
    [string]$Description = "JSON readiness endpoint",
    [string[]]$LogPaths = @()
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $lastError = ""
  do {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
        try {
          $payload = $response.Content | ConvertFrom-Json
          if ($payload.status -eq "ok") {
            return $response
          }
          $lastError = "status=$($payload.status), content=$($response.Content)"
        } catch {
          $lastError = "failed to parse JSON response: $($_.Exception.Message)"
        }
      }
    } catch {
      $lastError = $_.Exception.Message
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)

  $message = "Timed out waiting for $Description at $Url"
  if (-not [string]::IsNullOrWhiteSpace($lastError)) {
    $message = "$message; last error: $lastError"
  }
  throw (Add-LogContext -Message $message -LogPaths $LogPaths)
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

  $logName = [System.IO.Path]::GetFileNameWithoutExtension($ScriptName)
  $stdoutPath = Join-Path $logRoot "$logName.out.log"
  $stderrPath = Join-Path $logRoot "$logName.err.log"
  $alreadyRunning = Get-NativeScriptProcess -ScriptName $ScriptName
  if (-not $alreadyRunning -and $ScriptName -eq "dev-worker.ps1" -and $script:ProcessInspectionAvailable) {
    $alreadyRunning = Get-NativeWorkerProcess
  }
  if (-not $script:ProcessInspectionAvailable -and $ScriptName -eq "dev-worker.ps1") {
    throw "Worker process inspection unavailable; refusing to launch dev-worker.ps1 because doing so can create a duplicate worker."
  }

  if ($alreadyRunning) {
    Write-Host "$ScriptName already running (PID=$($alreadyRunning.ProcessId))" -ForegroundColor Yellow
    return [pscustomobject]@{
      Started = $false
      ProcessId = [int]$alreadyRunning.ProcessId
      StdoutPath = $stdoutPath
      StderrPath = $stderrPath
    }
  }

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
  # The former COM launcher inherited Cursor's Windows Job, so its children
  # were reaped with that Job. WMI creates the process under WmiPrvSE instead.
  $startupInfo = New-CimInstance `
    -ClassName Win32_ProcessStartup `
    -ClientOnly `
    -Property @{
      ShowWindow = [uint16]0
    }
  $launchResult = Invoke-CimMethod `
    -ClassName Win32_Process `
    -MethodName Create `
    -Arguments @{
      CommandLine = $command
      CurrentDirectory = $root
      ProcessStartupInformation = $startupInfo
    }
  if ([int]$launchResult.ReturnValue -ne 0) {
    throw "$ScriptName launcher failed with WMI return code $($launchResult.ReturnValue)"
  }

  $launchDeadline = (Get-Date).AddSeconds(5)
  do {
    Start-Sleep -Milliseconds 100
    $process = Get-NativeScriptProcess -ScriptName $ScriptName
  } while (
    -not $process -and
    $script:ProcessInspectionAvailable -and
    (Get-Date) -lt $launchDeadline
  )
  if (-not $script:ProcessInspectionAvailable) {
    Write-Warning "launched $ScriptName; process verification unavailable"
    return [pscustomobject]@{
      Started = $true
      ProcessId = "unknown"
      StdoutPath = $stdoutPath
      StderrPath = $stderrPath
    }
  }

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

$postgresPort = Wait-TcpPort -ListenHost "127.0.0.1" -Port 55432 -TimeoutSeconds 120 -Description "local Postgres dev cluster"

$existingApiLaunch = Assert-PortAvailableForScriptStart -Port 7888 -ScriptName $apiScriptName -Description "API"
if ($existingApiLaunch) {
  $apiLaunch = [pscustomobject]@{
    Started = $false
    ProcessId = $existingApiLaunch.ProcessId
    StdoutPath = Join-Path $logRoot "$apiLogName.out.log"
    StderrPath = Join-Path $logRoot "$apiLogName.err.log"
  }
} else {
  $apiLaunch = Start-DevScriptDetached -ScriptName $apiScriptName
}
$workerLaunch = Start-DevScriptDetached -ScriptName "dev-worker.ps1"
$apiLogPaths = @($apiLaunch.StderrPath, $apiLaunch.StdoutPath, (Join-Path $logRoot "$apiLogName.err.log"), (Join-Path $logRoot "$apiLogName.out.log"))
$workerLogPaths = @($workerLaunch.StderrPath, $workerLaunch.StdoutPath, (Join-Path $logRoot "dev-worker.err.log"), (Join-Path $logRoot "dev-worker.out.log"))

$workerHeartbeatPath = Join-Path $root "tmp-governance\runtime-clean\governance\dev-worker-heartbeat.json"
$workerHeartbeatToken = [guid]::NewGuid().ToString("N")
Remove-Item -Path $workerHeartbeatPath -Force -ErrorAction SilentlyContinue
$pythonExe = Resolve-DevPython
& $pythonExe -c "from backend.app.tasks.dev_health import write_dev_worker_heartbeat; write_dev_worker_heartbeat.send(heartbeat_path=r'$workerHeartbeatPath', token=r'$workerHeartbeatToken')"
if ($LASTEXITCODE -ne 0) {
  throw (Add-LogContext -Message "Failed to enqueue dev worker heartbeat smoke task." -LogPaths $workerLogPaths)
}

$apiHealth = Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:7888/health" -Description "API health" -LogPaths $apiLogPaths
$apiReady = Wait-JsonStatusOkEndpointWithLogs -Url "http://127.0.0.1:7888/health/ready" -Description "API readiness" -LogPaths $apiLogPaths
if ($agentDevMode) {
  $agentProjects = Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:7888/api/agent/projects" -Description "Agent projects" -LogPaths $apiLogPaths
  $agentRuns = Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:7888/api/agent/runs?limit=1" -Description "Agent runs" -LogPaths $apiLogPaths
} else {
  $homeSnapshotWarm = Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:7888/ui/home/snapshot" -TimeoutSeconds 120 -Description "home snapshot warm cache" -LogPaths $apiLogPaths
  $apiReadyAfterHomeWarm = Wait-JsonStatusOkEndpointWithLogs -Url "http://127.0.0.1:7888/health/ready" -Description "API readiness after home snapshot warm cache" -LogPaths $apiLogPaths
  $apiReadyAfterHomeWarmPayload = $apiReadyAfterHomeWarm.Content | ConvertFrom-Json
  $homeSnapshotPrewarm = $apiReadyAfterHomeWarmPayload.checks.home_snapshot_prewarm
  if ($null -eq $homeSnapshotPrewarm) {
    throw "API readiness after home snapshot warm cache did not expose checks.home_snapshot_prewarm. Restart the API so the home prewarm guard is active."
  }
  if ($homeSnapshotPrewarm.status -ne "ready") {
    throw "Home snapshot prewarm is not ready: status=$($homeSnapshotPrewarm.status) error=$($homeSnapshotPrewarm.error)"
  }
  $bondDates = Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:7888/api/bond-analytics/dates" -Description "bond analytics dates" -LogPaths $apiLogPaths
  $riskDates = Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:7888/api/risk/tensor/dates" -Description "risk tensor dates" -LogPaths $apiLogPaths
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
}
$frontendLaunch = Start-DevScriptDetached -ScriptName "dev-frontend.ps1"
$frontendLogPaths = @($frontendLaunch.StderrPath, $frontendLaunch.StdoutPath, (Join-Path $logRoot "dev-frontend.err.log"), (Join-Path $logRoot "dev-frontend.out.log"))
$frontendRoot = Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:5888" -Description "frontend root" -LogPaths $frontendLogPaths
$frontendClientContext = Wait-HttpEndpointWithLogs -Url "http://127.0.0.1:5888/src/api/clientContext.ts" -Description "frontend Vite API client context module" -LogPaths $frontendLogPaths
$keepaliveLaunch = Start-DevScriptDetached -ScriptName "dev-keepalive.ps1"
try {
  $workerHeartbeat = Wait-FileReady -Path $workerHeartbeatPath -ExpectedToken $workerHeartbeatToken -TimeoutSeconds 120 -Description "worker heartbeat"
} catch {
  throw (Add-LogContext -Message ($_.Exception.Message) -LogPaths $workerLogPaths)
}

$apiProcess = Assert-NativeProcessRunning -Description "API" -Predicate {
  $_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app.main:app*"
}
$workerProcess = Assert-NativeProcessRunning -Description "worker" -Predicate {
  Test-NativeWorkerProcess -Process $_
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
Write-Host "API script: $apiScriptName" -ForegroundColor DarkGray
Write-Host "API:      http://127.0.0.1:7888" -ForegroundColor Gray
Write-Host "Frontend: http://127.0.0.1:5888" -ForegroundColor Gray
Write-Host "Postgres: postgresql://moss:moss@127.0.0.1:55432/moss" -ForegroundColor Gray
Write-Host "API PID:      $($apiProcess.ProcessId)" -ForegroundColor DarkGray
Write-Host "Worker PID:   $($workerProcess.ProcessId)" -ForegroundColor DarkGray
Write-Host "Frontend PID: $($frontendProcess.ProcessId)" -ForegroundColor DarkGray
Write-Host "Postgres PID: $($postgresPort.OwningProcess)" -ForegroundColor DarkGray
Write-Host "API health:   $($apiHealth.StatusCode)" -ForegroundColor DarkGray
Write-Host "API ready:    $($apiReady.StatusCode)" -ForegroundColor DarkGray
if ($agentDevMode) {
  Write-Host "Agent projects: $($agentProjects.StatusCode)" -ForegroundColor DarkGray
  Write-Host "Agent runs:     $($agentRuns.StatusCode)" -ForegroundColor DarkGray
} else {
  Write-Host "Home cache:   $($homeSnapshotWarm.StatusCode) snapshot warmed" -ForegroundColor DarkGray
  Write-Host "Home prewarm: $($homeSnapshotPrewarm.status) ($($homeSnapshotPrewarm.last_duration_ms) ms) error=$($homeSnapshotPrewarm.error)" -ForegroundColor DarkGray
  Write-Host "Bond dates:   $($bondDates.StatusCode)" -ForegroundColor DarkGray
  Write-Host "Risk tensor:  $($riskTensorSmoke.Count) detail + $($riskDatesSmoke.Count) dates concurrent checks, report_date=$riskReportDate" -ForegroundColor DarkGray
}
Write-Host "Frontend:     $($frontendRoot.StatusCode) root + $($frontendClientContext.StatusCode) client context module" -ForegroundColor DarkGray
Write-Host "Worker smoke: $($workerHeartbeat.token)" -ForegroundColor DarkGray
Write-Host "Lineage audit: clean" -ForegroundColor DarkGray
Write-Host "API logs:      $($apiLaunch.StdoutPath) / $($apiLaunch.StderrPath)" -ForegroundColor DarkGray
Write-Host "Worker logs:   $($workerLaunch.StdoutPath) / $($workerLaunch.StderrPath)" -ForegroundColor DarkGray
Write-Host "Frontend logs: $($frontendLaunch.StdoutPath) / $($frontendLaunch.StderrPath)" -ForegroundColor DarkGray
Write-Host "Keepalive:     $($keepaliveLaunch.ProcessId) (log: $logRoot\dev-keepalive.log)" -ForegroundColor DarkGray
exit 0
