param(
  [ValidateSet("start", "stop", "restart", "status", "logs")]
  [string]$Command = "start",
  [string]$WslDistro = "HermesUbuntu",
  [string]$HermesWebuiDir = "/home/hermes/hermes-webui",
  [string]$HermesAgentDir = "/home/hermes/hermes-agent",
  [string]$HermesHome = "/home/hermes/.hermes-moss",
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8787,
  [switch]$FollowLogs
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root ".tmp-servers\hermes-webui.pid"
$stdoutPath = Join-Path $root ".tmp-servers\hermes-webui.out.log"
$stderrPath = Join-Path $root ".tmp-servers\hermes-webui.err.log"
$startScriptPath = Join-Path $root ".tmp-servers\hermes-webui-start.sh"

function ConvertTo-WslPath {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path
  )

  $resolved = [System.IO.Path]::GetFullPath($Path)
  if ($resolved -notmatch "^[A-Za-z]:\\") {
    throw "Only absolute Windows drive paths can be converted to WSL paths: $Path"
  }

  $drive = $resolved.Substring(0, 1).ToLowerInvariant()
  $rest = $resolved.Substring(3).Replace("\", "/")
  return "/mnt/$drive/$rest"
}

function Get-HermesWebuiProcess {
  if (-not (Test-Path $pidFile)) {
    return $null
  }

  $rawPid = (Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if (-not ($rawPid -match "^\d+$")) {
    return $null
  }

  return Get-Process -Id ([int]$rawPid) -ErrorAction SilentlyContinue
}

function Get-HermesWebuiLog {
  $parts = @()
  foreach ($path in @($stderrPath, $stdoutPath)) {
    if (Test-Path $path) {
      $lines = Get-Content -Path $path -Tail 80 -ErrorAction SilentlyContinue
      if ($lines) {
        $parts += "== $path =="
        $parts += $lines
      }
    }
  }
  return ($parts -join [Environment]::NewLine)
}

function Wait-HermesWebuiHealth {
  param(
    [int]$TimeoutSeconds = 40
  )

  $url = "http://127.0.0.1:$Port/health"
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
        return $response.Content
      }
    } catch {
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)

  $recentLog = Get-HermesWebuiLog
  if ($recentLog) {
    throw "Hermes WebUI did not become healthy at $url.`nRecent logs:`n$recentLog"
  }
  throw "Hermes WebUI did not become healthy at $url."
}

function Stop-HermesWebui {
  $process = Get-HermesWebuiProcess
  if ($process) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit(10000) | Out-Null
  }

  & wsl.exe -d $WslDistro -e sh -lc "pkill -f '$HermesWebuiDir/server.py' 2>/dev/null || true; pkill -f '$HermesWebuiDir/bootstrap.py' 2>/dev/null || true"
  Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
}

$workspaceWsl = ConvertTo-WslPath -Path $root
$startScriptWsl = ConvertTo-WslPath -Path $startScriptPath
$HermesPython = "$HermesAgentDir/venv/bin/python"
$stateDir = "$HermesHome/webui"

$shellScript = @"
set -eu
if [ ! -d '$HermesWebuiDir' ]; then
  echo 'Hermes WebUI checkout not found: $HermesWebuiDir' >&2
  echo 'Install it in WSL with: git clone https://github.com/nesquena/hermes-webui.git $HermesWebuiDir' >&2
  exit 1
fi
if [ ! -x '$HermesPython' ]; then
  echo 'Hermes Python not found: $HermesPython' >&2
  exit 1
fi
cd '$HermesWebuiDir'
export HERMES_HOME='$HermesHome'
export HERMES_WEBUI_AGENT_DIR='$HermesAgentDir'
export HERMES_WEBUI_PYTHON='$HermesPython'
export HERMES_WEBUI_DEFAULT_WORKSPACE='$workspaceWsl'
export HERMES_WEBUI_STATE_DIR='$stateDir'
export HERMES_WEBUI_HOST='$BindHost'
export HERMES_WEBUI_PORT='$Port'
exec '$HermesPython' bootstrap.py --no-browser --foreground --host '$BindHost' '$Port'
"@

Write-Host "[Hermes WebUI] WSL distro: $WslDistro" -ForegroundColor Cyan
Write-Host "[Hermes WebUI] Workspace:  $root -> $workspaceWsl" -ForegroundColor DarkGray
Write-Host "[Hermes WebUI] URL:        http://127.0.0.1:$Port" -ForegroundColor DarkGray
Write-Host "[Hermes WebUI] State:      $stateDir" -ForegroundColor DarkGray

switch ($Command) {
"start" {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pidFile) | Out-Null
    Set-Content -Path $startScriptPath -Value $shellScript -Encoding ASCII
    $existing = Get-HermesWebuiProcess
    if ($existing) {
      Wait-HermesWebuiHealth | Out-Null
      Write-Host "[Hermes WebUI] Already running (PID $($existing.Id))." -ForegroundColor Cyan
      break
    }

    $process = Start-Process `
      -FilePath "wsl.exe" `
      -ArgumentList @("-d", $WslDistro, "-e", "sh", $startScriptWsl) `
      -RedirectStandardOutput $stdoutPath `
      -RedirectStandardError $stderrPath `
      -WindowStyle Hidden `
      -PassThru
    Set-Content -Path $pidFile -Value ([string]$process.Id) -Encoding ASCII
    Wait-HermesWebuiHealth | Out-Null
    Write-Host "[Hermes WebUI] Started (PID $($process.Id)). Open http://127.0.0.1:$Port" -ForegroundColor Cyan
  }
  "restart" {
    Stop-HermesWebui
    & powershell -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath `
      -Command start `
      -WslDistro $WslDistro `
      -HermesWebuiDir $HermesWebuiDir `
      -HermesAgentDir $HermesAgentDir `
      -HermesHome $HermesHome `
      -BindHost $BindHost `
      -Port $Port
  }
  "stop" {
    Stop-HermesWebui
    Write-Host "[Hermes WebUI] Stopped." -ForegroundColor Cyan
  }
  "status" {
    $process = Get-HermesWebuiProcess
    if ($process) {
      $health = Wait-HermesWebuiHealth
      Write-Host "[Hermes WebUI] Running (PID $($process.Id))." -ForegroundColor Cyan
      Write-Host $health
    } else {
      Write-Host "[Hermes WebUI] Stopped." -ForegroundColor Cyan
    }
  }
  "logs" {
    if ($FollowLogs) {
      Get-Content -Path $stdoutPath, $stderrPath -Tail 120 -Wait
    } else {
      $log = Get-HermesWebuiLog
      if ($log) {
        Write-Host $log
      } else {
        Write-Host "[Hermes WebUI] No local launcher logs yet." -ForegroundColor Cyan
      }
    }
  }
}
