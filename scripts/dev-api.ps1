$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"

if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
  throw "Missing virtual environment at .venv. Create it first with: python -m venv .venv"
}

. .\.venv\Scripts\Activate.ps1

$args = @("--host", "127.0.0.1", "--port", "7888")
if ($env:MOSS_DEV_RELOAD -eq "1") {
  $args += "--reload"
}

python -m uvicorn backend.app.main:app @args
