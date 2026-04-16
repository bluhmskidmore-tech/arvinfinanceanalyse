$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

$env:MOSS_ENVIRONMENT = "development"
$env:MOSS_POSTGRES_DSN = "postgresql://moss:moss@127.0.0.1:55432/moss"
$env:MOSS_GOVERNANCE_SQL_DSN = $env:MOSS_POSTGRES_DSN
$env:MOSS_REDIS_DSN = "redis://localhost:6379/0"
$env:MOSS_DUCKDB_PATH = Join-Path $root "data\moss.duckdb"
$env:MOSS_GOVERNANCE_PATH = Join-Path $root "data\governance"
$env:MOSS_OBJECT_STORE_MODE = "local"
$env:MOSS_LOCAL_ARCHIVE_PATH = Join-Path $root "data\archive"
$env:MOSS_MINIO_ENDPOINT = "localhost:9000"
$env:MOSS_MINIO_ACCESS_KEY = "minioadmin"
$env:MOSS_MINIO_SECRET_KEY = "minioadmin"
$env:MOSS_MINIO_BUCKET = "moss-artifacts"

$clusterHelper = Join-Path $root "scripts\dev_postgres_cluster.py"
if (Test-Path $clusterHelper) {
  $python = (Get-Command python -ErrorAction Stop).Source
  $json = & $python $clusterHelper print-env --repo-root $root
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to load local PostgreSQL dev cluster environment"
  }
  $mapping = $json | ConvertFrom-Json
  foreach ($property in $mapping.PSObject.Properties) {
    Set-Item -Path ("Env:" + $property.Name) -Value ([string]$property.Value)
  }
}

function Assert-DevBootstrapStorageReady {
  param(
    [string]$ProbeLabel = "dev-entrypoint"
  )

  $duckdbPath = [string]$env:MOSS_DUCKDB_PATH
  if ([string]::IsNullOrWhiteSpace($duckdbPath)) {
    throw "[$ProbeLabel] MOSS_DUCKDB_PATH is empty after loading dev-env.ps1"
  }

  $python = (Get-Command python -ErrorAction Stop).Source
  $probe = @'
import os
import sys
from pathlib import Path

import duckdb

probe_label = os.environ.get("MOSS_DEV_STORAGE_PROBE_LABEL", "dev-entrypoint")
duckdb_path = Path(os.environ["MOSS_DUCKDB_PATH"]).expanduser()
seed_tables = (
    "fact_formal_bond_analytics_daily",
    "zqtz_bond_daily_snapshot",
    "fact_formal_zqtz_balance_daily",
    "fact_formal_tyw_balance_daily",
)

if not duckdb_path.exists():
    raise SystemExit(f"[{probe_label}] Missing MOSS_DUCKDB_PATH: {duckdb_path}")

try:
    conn = duckdb.connect(str(duckdb_path), read_only=True)
except duckdb.Error as exc:
    raise SystemExit(f"[{probe_label}] Failed to open DuckDB at {duckdb_path}: {exc}") from exc

try:
    for table_name in seed_tables:
        row = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_name = ?
            limit 1
            """,
            [table_name],
        ).fetchone()
        if row is None:
            continue
        populated = conn.execute(f"select 1 from {table_name} limit 1").fetchone()
        if populated is not None:
            print(f"[{probe_label}] Dev storage ready: {duckdb_path} -> {table_name}")
            raise SystemExit(0)
finally:
    conn.close()

raise SystemExit(
    f"[{probe_label}] Dev storage bootstrap resolved to an empty DuckDB: {duckdb_path}. "
    "Run scripts/dev-postgres-up.ps1 or repopulate repo data/."
)
'@

  $previousProbeLabel = $env:MOSS_DEV_STORAGE_PROBE_LABEL
  $env:MOSS_DEV_STORAGE_PROBE_LABEL = $ProbeLabel
  $probeFile = [System.IO.Path]::ChangeExtension([System.IO.Path]::GetTempFileName(), ".py")
  try {
    Set-Content -Path $probeFile -Value $probe -Encoding UTF8
    $probeOutput = & $python $probeFile 2>&1
    if ($LASTEXITCODE -ne 0) {
      if ($probeOutput) {
        throw ($probeOutput | Out-String).Trim()
      }
      throw "[$ProbeLabel] Dev storage probe failed for $duckdbPath"
    }
    if ($probeOutput) {
      Write-Host (($probeOutput | Out-String).Trim()) -ForegroundColor DarkGray
    }
  } finally {
    if ($null -eq $previousProbeLabel) {
      Remove-Item Env:MOSS_DEV_STORAGE_PROBE_LABEL -ErrorAction SilentlyContinue
    } else {
      $env:MOSS_DEV_STORAGE_PROBE_LABEL = $previousProbeLabel
    }
    Remove-Item -Path $probeFile -Force -ErrorAction SilentlyContinue
  }
}
