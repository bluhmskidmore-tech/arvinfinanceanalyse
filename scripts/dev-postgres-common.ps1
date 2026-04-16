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
  $stdoutRaw = ""
  $stderrText = ""

  try {
    $stdoutRaw = & $python (Join-Path $Root "scripts\dev_postgres_cluster.py") $Command "--repo-root" $Root 2>&1
    $stdoutLines = @($stdoutRaw | ForEach-Object { [string]$_ })
    $stdoutText = ($stdoutLines | Out-String).Trim()
    $jsonLine = @($stdoutLines | Where-Object { $_ -match '^\s*\{.*\}\s*$' } | Select-Object -Last 1)
    if (-not $jsonLine) {
      throw ("dev_postgres_cluster.py {0} did not emit a JSON status payload. stdout={1} stderr={2}" -f $Command, $stdoutText, $stderrText)
    }

    $payload = $jsonLine | ConvertFrom-Json
    return [pscustomobject]@{
      ExitCode = $LASTEXITCODE
      Payload = $payload
      JsonLine = [string]$jsonLine
      Stdout = $stdoutText
      Stderr = $stderrText
    }
  } finally {
  }
}
