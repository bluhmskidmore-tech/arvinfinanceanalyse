$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"
. "$root\scripts\dev-python.ps1"
$python = Resolve-DevPython
& $python -m dramatiq backend.app.tasks.worker_bootstrap
