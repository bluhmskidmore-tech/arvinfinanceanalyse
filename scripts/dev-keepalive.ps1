param(
  [int]$IntervalSeconds = 5,
  [int]$RestartCooldownSeconds = 15,
  [ValidateRange(1, 10)]
  [int]$PostgresProbeFailureThreshold = 3,
  [ValidateRange(1, 20)]
  [int]$PostgresRecoveryMaxAttempts = 3,
  [switch]$Once
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$powershellExe = (Get-Command powershell -ErrorAction Stop).Source
$logRoot = Join-Path $root "tmp-governance\runtime-clean\logs"
New-Item -ItemType Directory -Force $logRoot | Out-Null
$keepaliveLog = Join-Path $logRoot "dev-keepalive.log"
$script:ProcessInspectionAvailable = $true
$apiScriptName = if ([string]::IsNullOrWhiteSpace($env:MOSS_DEV_API_SCRIPT)) {
  "dev-api.ps1"
} else {
  [string]$env:MOSS_DEV_API_SCRIPT
}

function Write-KeepaliveLog {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Message
  )

  $line = "{0} {1}" -f (Get-Date).ToString("s"), $Message
  try {
    Add-Content -Path $keepaliveLog -Value $line -Encoding UTF8 -ErrorAction Stop
  } catch {
  }

  try {
    Write-Host $line
  } catch {
  }
}

$instanceLockPath = Join-Path $logRoot "dev-keepalive.instance.lock"
try {
  $script:InstanceLock = [System.IO.File]::Open(
    $instanceLockPath,
    [System.IO.FileMode]::OpenOrCreate,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
  )
} catch [System.IO.IOException] {
  Write-KeepaliveLog "another dev keepalive instance already owns $instanceLockPath; exiting"
  exit 0
}

function Test-HttpEndpoint {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [int]$TimeoutSeconds = 3
  )

  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
  } catch {
    return $false
  }
}

function Test-FrontendReady {
  return (
    (Test-HttpEndpoint -Url "http://127.0.0.1:5888") -and
    (Test-HttpEndpoint -Url "http://127.0.0.1:5888/src/api/clientContext.ts")
  )
}

function Wait-HttpEndpoint {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [int]$TimeoutSeconds = 45,
    [string]$Description = "endpoint"
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    if (Test-HttpEndpoint -Url $Url) {
      return
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)

  throw "Timed out waiting for $Description at $Url"
}

function Quote-CmdArgument {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Value
  )

  return '"' + ($Value -replace '"', '""') + '"'
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
    Write-KeepaliveLog "process lookup failed for ${ScriptName}: $($_.Exception.Message)"
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
    Write-KeepaliveLog "process lookup failed for native worker: $($_.Exception.Message)"
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

function Stop-MatchingProcesses {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Description,
    [Parameter(Mandatory = $true)]
    [scriptblock]$Predicate
  )

  try {
    $targets = @(Get-CimInstance Win32_Process | Where-Object $Predicate)
  } catch {
    $script:ProcessInspectionAvailable = $false
    Write-KeepaliveLog "process lookup failed for ${Description}: $($_.Exception.Message)"
    return
  }

  foreach ($proc in $targets) {
    try {
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
      Write-KeepaliveLog "stopped stale ${Description} process PID=$($proc.ProcessId)"
    } catch {
      Write-KeepaliveLog "failed to stop ${Description} process PID=$($proc.ProcessId): $($_.Exception.Message)"
    }
  }
}

function Stop-KnownServiceProcesses {
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("api", "worker", "frontend")]
    [string]$ServiceName
  )

  switch ($ServiceName) {
    "api" {
      Stop-MatchingProcesses -Description "API" -Predicate {
        ($_.Name -eq "powershell.exe" -and $_.CommandLine -like "*scripts\dev-api.ps1*") -or
        ($_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app.main:app*")
      }
    }
    "worker" {
      Stop-MatchingProcesses -Description "worker" -Predicate {
        ($_.Name -eq "powershell.exe" -and $_.CommandLine -like "*scripts\dev-worker.ps1*") -or
        (Test-NativeWorkerProcess -Process $_)
      }
    }
    "frontend" {
      Stop-MatchingProcesses -Description "frontend" -Predicate {
        ($_.Name -eq "powershell.exe" -and $_.CommandLine -like "*scripts\dev-frontend.ps1*") -or
        ($_.Name -eq "node.exe" -and
          $_.CommandLine -like ("*" + (Join-Path $root "frontend") + "*") -and
          $_.CommandLine -like "*vite*")
      }
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
  if (-not $alreadyRunning -and $ScriptName -eq "dev-worker.ps1" -and $script:ProcessInspectionAvailable) {
    $alreadyRunning = Get-NativeWorkerProcess
  }
  if (-not $script:ProcessInspectionAvailable -and $ScriptName -eq "dev-worker.ps1") {
    throw "Worker process inspection unavailable; refusing to launch dev-worker.ps1 because doing so can create a duplicate worker."
  }
  if ($alreadyRunning) {
    Write-KeepaliveLog "$ScriptName already running (PID=$($alreadyRunning.ProcessId))"
    return
  }

  $logName = [System.IO.Path]::GetFileNameWithoutExtension($ScriptName)
  $stdoutPath = Join-Path $logRoot "$logName.out.log"
  $stderrPath = Join-Path $logRoot "$logName.err.log"
  Remove-Item -Path $stdoutPath,$stderrPath -Force -ErrorAction SilentlyContinue
  $scriptArguments = if ($ScriptName -eq "dev-api.ps1") {
    " -SkipStartupStorageMigrations"
  } else {
    ""
  }

  $scriptCommand = (
    (Quote-CmdArgument $powershellExe) +
    " -NoProfile -ExecutionPolicy Bypass -File " +
    (Quote-CmdArgument $scriptPath) +
    $scriptArguments +
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
    Write-KeepaliveLog "launched $ScriptName; process verification unavailable"
    return
  }

  if (-not $process) {
    $stderr = if (Test-Path $stderrPath) { @(Get-Content -Path $stderrPath -Tail 40 -ErrorAction SilentlyContinue) } else { @() }
    $stdout = if (Test-Path $stdoutPath) { @(Get-Content -Path $stdoutPath -Tail 40 -ErrorAction SilentlyContinue) } else { @() }
    throw (
      "$ScriptName did not remain running after detached launch. " +
      "stdout=$stdoutPath stderr=$stderrPath`n" +
      (($stderr + $stdout) -join "`n")
    ).Trim()
  }

  Write-KeepaliveLog "started $ScriptName (PID=$($process.ProcessId))"
}

$lastRestartAt = @{}
$lastHeartbeatAt = [datetime]::MinValue
$script:PostgresConsecutiveProbeFailures = 0
$script:PostgresRecoveryFailureCount = 0
$script:PostgresRecoverySuppressionLogged = $false
$script:LastPostgresProbeState = "unknown"

function Test-RestartCooldown {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Key
  )

  if (-not $lastRestartAt.ContainsKey($Key)) {
    return $false
  }

  $elapsed = ((Get-Date) - [datetime]$lastRestartAt[$Key]).TotalSeconds
  return ($elapsed -lt $RestartCooldownSeconds)
}

function Set-RestartTimestamp {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Key
  )

  $lastRestartAt[$Key] = Get-Date
}

function Get-DevPostgresProbe {
  $listener = Get-DevListeningPortOwner -Port 55432
  if (-not $listener) {
    return [pscustomobject]@{
      State = "missing"
      OwningProcess = $null
      Detail = "no listener on 127.0.0.1:55432"
    }
  }

  $owningProcess = [int]$listener.OwningProcess
  try {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$owningProcess" |
      Select-Object -First 1
  } catch {
    return [pscustomobject]@{
      State = "unverifiable"
      OwningProcess = $owningProcess
      Detail = $_.Exception.Message
    }
  }

  if (-not $process -or [string]::IsNullOrWhiteSpace([string]$process.CommandLine)) {
    return [pscustomobject]@{
      State = "unverifiable"
      OwningProcess = $owningProcess
      Detail = "listener process command line is unavailable"
    }
  }

  $expectedDataDir = (Join-Path $root "tmp-governance\pgdev\data").Replace("\", "/")
  $commandLine = ([string]$process.CommandLine).Replace("\", "/")
  $ownsDataDir = $commandLine.IndexOf(
    $expectedDataDir,
    [System.StringComparison]::OrdinalIgnoreCase
  ) -ge 0
  $ownsHost = $commandLine -match '(?i)(^|\s)-h\s+"?127\.0\.0\.1"?(\s|$)'
  $ownsPort = $commandLine -match '(?i)(^|\s)-p\s+"?55432"?(\s|$)'
  $isPostgres = ([string]$process.Name) -ieq "postgres.exe"
  $state = if ($isPostgres -and $ownsDataDir -and $ownsHost -and $ownsPort) {
    "owned"
  } else {
    "foreign"
  }

  return [pscustomobject]@{
    State = $state
    OwningProcess = $owningProcess
    Detail = "name=$($process.Name) dataDir=$ownsDataDir host=$ownsHost port=$ownsPort"
  }
}

function Test-DevPostgresReady {
  $probe = Get-DevPostgresProbe
  return ($probe.State -eq "owned")
}

function Invoke-DevPostgresUp {
  $scriptPath = Join-Path $root "scripts\dev-postgres-up.ps1"
  $output = @(
    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File $scriptPath 2>&1
  )

  return [pscustomobject]@{
    ExitCode = [int]$LASTEXITCODE
    Output = (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
  }
}

function Ensure-DevPostgresRunning {
  $probe = Get-DevPostgresProbe
  if ($probe.State -eq "owned") {
    if ($script:PostgresRecoveryFailureCount -gt 0) {
      Write-KeepaliveLog "private Postgres listener recovered outside keepalive; clearing failure count"
    }
    $script:PostgresConsecutiveProbeFailures = 0
    $script:PostgresRecoveryFailureCount = 0
    $script:PostgresRecoverySuppressionLogged = $false
    $script:LastPostgresProbeState = "owned"
    return $true
  }

  if ($probe.State -eq "foreign" -or $probe.State -eq "unverifiable") {
    $script:PostgresConsecutiveProbeFailures = 0
    if ($script:LastPostgresProbeState -ne $probe.State) {
      $label = if ($probe.State -eq "foreign") { "foreign listener" } else { "listener ownership unverifiable" }
      Write-KeepaliveLog "private Postgres probe blocked by $label on 127.0.0.1:55432 PID=$($probe.OwningProcess); recovery refused"
    }
    $script:LastPostgresProbeState = $probe.State
    return $false
  }

  $script:LastPostgresProbeState = "missing"
  $script:PostgresConsecutiveProbeFailures += 1
  if ($script:PostgresConsecutiveProbeFailures -lt $PostgresProbeFailureThreshold) {
    Write-KeepaliveLog "private Postgres listener missing on 127.0.0.1:55432; probe $script:PostgresConsecutiveProbeFailures/$PostgresProbeFailureThreshold before recovery"
    return $false
  }

  if ($script:PostgresRecoveryFailureCount -ge $PostgresRecoveryMaxAttempts) {
    if (-not $script:PostgresRecoverySuppressionLogged) {
      Write-KeepaliveLog "private Postgres recovery suppressed after $PostgresRecoveryMaxAttempts failed attempts; manual intervention required"
      $script:PostgresRecoverySuppressionLogged = $true
    }
    return $false
  }

  if (Test-RestartCooldown -Key "postgres") {
    Write-KeepaliveLog "private Postgres listener missing on 127.0.0.1:55432; recovery skipped by cooldown"
    return $false
  }

  $attempt = $script:PostgresRecoveryFailureCount + 1
  Write-KeepaliveLog "private Postgres listener missing on 127.0.0.1:55432; recovery attempt $attempt/$PostgresRecoveryMaxAttempts"
  Set-RestartTimestamp -Key "postgres"

  try {
    $result = Invoke-DevPostgresUp
    if ($result.ExitCode -ne 0) {
      throw "dev-postgres-up.ps1 exited with code $($result.ExitCode): $($result.Output)"
    }
    $recoveredProbe = Get-DevPostgresProbe
    if ($recoveredProbe.State -ne "owned") {
      throw "dev-postgres-up.ps1 returned success but the owned cluster is not ready on 127.0.0.1:55432 (state=$($recoveredProbe.State))"
    }

    $script:PostgresConsecutiveProbeFailures = 0
    $script:PostgresRecoveryFailureCount = 0
    $script:PostgresRecoverySuppressionLogged = $false
    Write-KeepaliveLog "private Postgres recovered on 127.0.0.1:55432"
    return $true
  } catch {
    $script:PostgresRecoveryFailureCount += 1
    $remaining = [Math]::Max(0, $PostgresRecoveryMaxAttempts - $script:PostgresRecoveryFailureCount)
    Write-KeepaliveLog "private Postgres recovery attempt $attempt failed; remaining=$remaining error=$($_.Exception.Message)"
    return $false
  }
}

function Restart-HttpService {
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("api", "frontend")]
    [string]$ServiceName,
    [Parameter(Mandatory = $true)]
    [string]$ScriptName,
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [Parameter(Mandatory = $true)]
    [int]$Port
  )

  if (Test-RestartCooldown -Key $ServiceName) {
    Write-KeepaliveLog "$ServiceName probe failed, restart skipped by cooldown"
    return
  }

  Write-KeepaliveLog "$ServiceName probe failed at $Url; restarting $ScriptName"
  Set-RestartTimestamp -Key $ServiceName
  Stop-KnownServiceProcesses -ServiceName $ServiceName
  Start-Sleep -Milliseconds 500

  $listener = Get-DevListeningPortOwner -Port $Port
  if ($listener) {
    Write-KeepaliveLog "$ServiceName port $Port is still occupied by PID=$($listener.OwningProcess); restart skipped"
    return
  }

  Start-DevScriptDetached -ScriptName $ScriptName
  Wait-HttpEndpoint -Url $Url -Description $ServiceName
  Write-KeepaliveLog "$ServiceName recovered at $Url"
}

function Ensure-WorkerRunning {
  $workerScript = Get-NativeScriptProcess -ScriptName "dev-worker.ps1"
  $workerProcess = $null
  if (-not $workerScript -and $script:ProcessInspectionAvailable) {
    $workerProcess = Get-NativeWorkerProcess
  }
  if (-not $script:ProcessInspectionAvailable) {
    Write-KeepaliveLog "worker process verification unavailable; skipping worker keepalive"
    return
  }

  if ($workerScript -or $workerProcess) {
    return
  }

  if (Test-RestartCooldown -Key "worker") {
    Write-KeepaliveLog "worker process missing, restart skipped by cooldown"
    return
  }

  Write-KeepaliveLog "worker process missing; restarting dev-worker.ps1"
  Set-RestartTimestamp -Key "worker"
  Stop-KnownServiceProcesses -ServiceName "worker"
  Start-DevScriptDetached -ScriptName "dev-worker.ps1"
}

function Invoke-KeepaliveCycle {
  $postgresReady = Ensure-DevPostgresRunning
  if (-not $postgresReady) {
    if ($script:LastPostgresProbeState -eq "foreign" -or $script:LastPostgresProbeState -eq "unverifiable") {
      Write-KeepaliveLog "private Postgres ownership gate is closed; stopping API and worker until the owned cluster returns"
      Stop-KnownServiceProcesses -ServiceName "api"
      Stop-KnownServiceProcesses -ServiceName "worker"
    }
    return
  }

  if (-not (Test-HttpEndpoint -Url "http://127.0.0.1:7888/health")) {
    Restart-HttpService `
      -ServiceName "api" `
      -ScriptName $apiScriptName `
      -Url "http://127.0.0.1:7888/health" `
      -Port 7888
  }

  Ensure-WorkerRunning

  if (-not (Test-FrontendReady)) {
    Restart-HttpService `
      -ServiceName "frontend" `
      -ScriptName "dev-frontend.ps1" `
      -Url "http://127.0.0.1:5888/src/api/clientContext.ts" `
      -Port 5888
  }
}

function Write-HeartbeatIfDue {
  $now = Get-Date
  if (($now - $lastHeartbeatAt).TotalSeconds -lt 60) {
    return
  }

  $script:lastHeartbeatAt = $now
  $postgresOk = Test-DevPostgresReady
  $apiOk = Test-HttpEndpoint -Url "http://127.0.0.1:7888/health"
  $frontendOk = Test-FrontendReady
  Write-KeepaliveLog "heartbeat postgres=$postgresOk postgresRecoveryFailures=$script:PostgresRecoveryFailureCount api=$apiOk frontend=$frontendOk processInspection=$script:ProcessInspectionAvailable"
}

try {
  Write-KeepaliveLog "dev keepalive started (interval=${IntervalSeconds}s, once=$Once, apiScript=$apiScriptName, postgresProbeFailureThreshold=$PostgresProbeFailureThreshold, postgresRecoveryMaxAttempts=$PostgresRecoveryMaxAttempts)"

  do {
    try {
      Invoke-KeepaliveCycle
      Write-HeartbeatIfDue
    } catch {
      Write-KeepaliveLog "keepalive cycle failed: $($_.Exception.Message)"
    }

    if ($Once) {
      break
    }

    Start-Sleep -Seconds $IntervalSeconds
  } while ($true)
} finally {
  $script:InstanceLock.Dispose()
}
