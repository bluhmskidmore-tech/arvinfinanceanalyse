$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
. "$root\scripts\dev-postgres-common.ps1"
$result = Invoke-DevPostgresClusterCommand -Root $root -Command "status"
if ($result.ExitCode -ne 0) {
  throw "dev_postgres_cluster.py status failed"
}

Write-Output $result.JsonLine
exit 0
