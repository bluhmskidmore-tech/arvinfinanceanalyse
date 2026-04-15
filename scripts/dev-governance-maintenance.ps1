$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"
Assert-DevBootstrapStorageReady -ProbeLabel "dev-governance-maintenance"
. "$root\scripts\dev-python.ps1"
$python = Resolve-DevPython

$governanceDir = $env:MOSS_GOVERNANCE_PATH
if (-not $governanceDir) {
  $governanceDir = Join-Path $root "data\governance"
}

& $python "$root\scripts\compact_source_preview_governance.py" --governance-dir $governanceDir
if ($LASTEXITCODE -ne 0) {
  throw "Source preview governance compaction failed"
}

& $python "$root\scripts\build_source_manifest_layers.py" --governance-dir $governanceDir
if ($LASTEXITCODE -ne 0) {
  throw "Source manifest layering failed"
}
