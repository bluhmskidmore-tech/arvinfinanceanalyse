param(
  [int]$IntervalSeconds = 5,
  [int]$RestartCooldownSeconds = 15,
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
        ($_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app.tasks.worker_bootstrap*")
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
  if ($alreadyRunning) {
    Write-KeepaliveLog "$ScriptName already running (PID=$($alreadyRunning.ProcessId))"
    return
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
  if (-not $script:ProcessInspectionAvailable) {
    Write-KeepaliveLog "launched $ScriptName; process verification unavailable"
    return
  }

  $process = Get-NativeScriptProcess -ScriptName $ScriptName
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
  if (-not $script:ProcessInspectionAvailable) {
    Write-KeepaliveLog "worker process verification unavailable; skipping worker keepalive"
    return
  }

  if ($workerScript) {
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
  if (-not (Test-HttpEndpoint -Url "http://127.0.0.1:7888/health")) {
    Restart-HttpService `
      -ServiceName "api" `
      -ScriptName "dev-api.ps1" `
      -Url "http://127.0.0.1:7888/health" `
      -Port 7888
  }

  Ensure-WorkerRunning

  if (-not (Test-HttpEndpoint -Url "http://127.0.0.1:5888")) {
    Restart-HttpService `
      -ServiceName "frontend" `
      -ScriptName "dev-frontend.ps1" `
      -Url "http://127.0.0.1:5888" `
      -Port 5888
  }
}

function Write-HeartbeatIfDue {
  $now = Get-Date
  if (($now - $lastHeartbeatAt).TotalSeconds -lt 60) {
    return
  }

  $script:lastHeartbeatAt = $now
  $apiOk = Test-HttpEndpoint -Url "http://127.0.0.1:7888/health"
  $frontendOk = Test-HttpEndpoint -Url "http://127.0.0.1:5888"
  Write-KeepaliveLog "heartbeat api=$apiOk frontend=$frontendOk processInspection=$script:ProcessInspectionAvailable"
}

Write-KeepaliveLog "dev keepalive started (interval=${IntervalSeconds}s, once=$Once)"

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
