$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
. "$root\scripts\dev-postgres-common.ps1"
$result = Invoke-DevPostgresClusterCommand -Root $root -Command "up"
if ($result.ExitCode -ne 0) {
  throw "dev_postgres_cluster.py up failed"
}

$payload = $result.Payload
if (-not $payload.running) {
  throw "Local PostgreSQL dev cluster did not reach running=true."
}

Write-Output $result.JsonLine
exit 0
