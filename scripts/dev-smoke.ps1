$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"

if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
  throw "Missing virtual environment at .venv. Create it first with: python -m venv .venv"
}

. .\.venv\Scripts\Activate.ps1

$smokeRoot = Join-Path $root "sample_data\smoke-runtime"
$smokeArchive = Join-Path $root "data\smoke-archive"
$smokeGovernance = Join-Path $root "data\smoke-governance"
$smokeDuckdb = Join-Path $root "data\smoke.duckdb"

Remove-Item $smokeRoot,$smokeArchive,$smokeGovernance,$smokeDuckdb -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $smokeRoot | Out-Null

$sampleFiles = @(
  "TYWLSHOW-20251231.xls",
  "ZQTZSHOW-20251231.xls"
)

foreach ($name in $sampleFiles) {
  Copy-Item (Join-Path $root "data_input\$name") (Join-Path $smokeRoot $name) -Force
}

$env:MOSS_DATA_INPUT_ROOT = $smokeRoot
$env:MOSS_LOCAL_ARCHIVE_PATH = $smokeArchive
$env:MOSS_GOVERNANCE_PATH = $smokeGovernance
$env:MOSS_DUCKDB_PATH = $smokeDuckdb

$health = Invoke-RestMethod "http://127.0.0.1:7888/health"
if ($health.status -ne "ok") {
  throw "Health check failed"
}

$ingest = python -c "from backend.app.tasks.ingest import ingest_demo_manifest; import json; print(json.dumps(ingest_demo_manifest.fn(), ensure_ascii=False))"
$materialize = python -c "from backend.app.tasks.materialize import materialize_cache_view; import json; print(json.dumps(materialize_cache_view.fn(), ensure_ascii=False))"

Write-Output "HEALTH_OK"
Write-Output $ingest
Write-Output $materialize
