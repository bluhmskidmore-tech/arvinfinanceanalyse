$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$root = $repoRoot
$logDirectory = Join-Path $PSScriptRoot "logs"
[IO.Directory]::CreateDirectory($logDirectory) | Out-Null
$logPath = Join-Path $logDirectory ("data-update-queue-{0}.log" -f (Get-Date -Format "yyyyMMdd"))
$utf8NoBom = [Text.UTF8Encoding]::new($false)
$runId = [Guid]::NewGuid().ToString("N")
$exitCode = 1
$stage = "launcher"
$runtimeProcessStarted = $false
$outputLogState = @{ failed = $false }
$sanitizeLogText = {
  param([AllowEmptyString()][string]$Value)
  $sanitized = [regex]::Replace(
    $Value,
    '(?i)(\b[a-z][a-z0-9+.-]*://[^:\s/@]+:)[^@\s/]+(@)',
    '$1***$2'
  )
  return [regex]::Replace(
    $sanitized,
    '(?i)\b([A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|ACCESS_KEY)[A-Z0-9_]*\s*[=:]\s*)\S+',
    '$1***'
  )
}

[IO.File]::AppendAllText(
  $logPath,
  ("{0} run_id={1} stage=launcher status=started{2}" -f [DateTimeOffset]::Now.ToString("o"), $runId, [Environment]::NewLine),
  $utf8NoBom
)

try {
  . (Join-Path $root "scripts\dev-runtime-common.ps1")
  $stage = "guard"
  Assert-DevRuntimeAllowed
  [IO.File]::AppendAllText(
    $logPath,
    ("{0} run_id={1} stage=guard status=ok{2}" -f [DateTimeOffset]::Now.ToString("o"), $runId, [Environment]::NewLine),
    $utf8NoBom
  )

  $stage = "startup"
  Set-Location -LiteralPath $repoRoot
  $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
  if (-not [IO.File]::Exists($pythonExe)) {
    $pythonExe = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
  }
  if (-not [IO.File]::Exists($pythonExe)) { throw "Repository Python not found." }
  $env:PATH = "$(Split-Path -Parent $pythonExe);$env:PATH"
  . (Join-Path $root "scripts\dev-env.ps1")
  $env:PYTHONIOENCODING = "utf-8"
  [IO.File]::AppendAllText(
    $logPath,
    ("{0} run_id={1} stage=startup status=ok{2}" -f [DateTimeOffset]::Now.ToString("o"), $runId, [Environment]::NewLine),
    $utf8NoBom
  )

  $stage = "worker"
  $runtimeProcessStarted = $true
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    Invoke-DevRuntimeProcess -Command @(
      $pythonExe,
      "-m",
      "backend.app.tasks.data_update_center"
    ) *>&1 | ForEach-Object {
      $stream = if ($_ -is [Management.Automation.ErrorRecord]) { "stderr" } else { "stdout" }
      $text = & $sanitizeLogText ([string]$_)
      try {
        [IO.File]::AppendAllText(
          $logPath,
          ("{0} run_id={1} stage=worker stream={2} {3}{4}" -f [DateTimeOffset]::Now.ToString("o"), $runId, $stream, $text, [Environment]::NewLine),
          $utf8NoBom
        )
      } catch {
        $outputLogState.failed = $true
        throw
      }
      if ($stream -eq "stderr") {
        [Console]::Error.WriteLine($text)
      } else {
        [Console]::Out.WriteLine($text)
      }
    }
    $exitCode = [int]$LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
} catch {
  if ($outputLogState.failed) {
    $exitCode = 1
  } elseif ($runtimeProcessStarted -and $LASTEXITCODE -is [int] -and $LASTEXITCODE -ne 0) {
    $exitCode = [int]$LASTEXITCODE
  } else {
    $exitCode = 1
  }
  $failureKind = if ($outputLogState.failed) { "log_write" } else { "execution" }
  $message = & $sanitizeLogText ([string]$_.Exception.Message)
  [IO.File]::AppendAllText(
    $logPath,
    ("{0} run_id={1} stage={2} status=failed failure_kind={3} exit_code={4} error={5}{6}" -f [DateTimeOffset]::Now.ToString("o"), $runId, $stage, $failureKind, $exitCode, $message, [Environment]::NewLine),
    $utf8NoBom
  )
  [Console]::Error.WriteLine($message)
} finally {
  try {
    $status = if ($exitCode -eq 0) { "completed" } else { "failed" }
    [IO.File]::AppendAllText(
      $logPath,
      ("{0} run_id={1} stage=launcher status={2} exit_code={3}{4}" -f [DateTimeOffset]::Now.ToString("o"), $runId, $status, $exitCode, [Environment]::NewLine),
      $utf8NoBom
    )
  } catch {
    [Console]::Error.WriteLine("Data update queue logging failed: {0}" -f $_.Exception.Message)
    $exitCode = 1
  }
}

exit $exitCode
