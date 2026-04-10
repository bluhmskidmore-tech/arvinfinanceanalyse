$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"

if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
  throw "Missing virtual environment at .venv. Create it first with: python -m venv .venv"
}

. .\.venv\Scripts\Activate.ps1
python -m dramatiq backend.app.tasks.ingest backend.app.tasks.materialize backend.app.tasks.choice_macro
