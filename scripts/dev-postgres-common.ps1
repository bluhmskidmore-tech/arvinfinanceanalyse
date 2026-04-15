$ErrorActionPreference = "Stop"

function Invoke-DevPostgresClusterCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [Parameter(Mandatory = $true)]
    [ValidateSet("up", "down", "status", "print-env", "reset-schema")]
    [string]$Command
  )

  $python = (Get-Command python -ErrorAction Stop).Source
  $stdoutFile = [System.IO.Path]::GetTempFileName()
  $stderrFile = [System.IO.Path]::GetTempFileName()

  try {
    $proc = Start-Process `
      -FilePath $python `
      -ArgumentList @((Join-Path $Root "scripts\dev_postgres_cluster.py"), $Command, "--repo-root", $Root) `
      -WorkingDirectory $Root `
      -NoNewWindow `
      -PassThru `
      -Wait `
      -RedirectStandardOutput $stdoutFile `
      -RedirectStandardError $stderrFile

    $stdoutLines = @()
    if (Test-Path $stdoutFile) {
      $stdoutLines = @(Get-Content -Path $stdoutFile -Encoding UTF8)
    }
    $stdoutText = ($stdoutLines | Out-String).Trim()
    $stderrRaw = if (Test-Path $stderrFile) { Get-Content -Path $stderrFile -Raw -Encoding UTF8 } else { "" }
    $stderrText = [string]$stderrRaw
    if ($stderrText) {
      $stderrText = $stderrText.Trim()
    }
    $jsonLine = @($stdoutLines | Where-Object { $_ -match '^\s*\{.*\}\s*$' } | Select-Object -Last 1)
    if (-not $jsonLine) {
      throw ("dev_postgres_cluster.py {0} did not emit a JSON status payload. stdout={1} stderr={2}" -f $Command, $stdoutText, $stderrText)
    }

    $payload = $jsonLine | ConvertFrom-Json
    return [pscustomobject]@{
      ExitCode = $proc.ExitCode
      Payload = $payload
      JsonLine = [string]$jsonLine
      Stdout = $stdoutText
      Stderr = $stderrText
    }
  } finally {
    Remove-Item -Path $stdoutFile, $stderrFile -Force -ErrorAction SilentlyContinue
  }
}
