$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"
Assert-DevBootstrapStorageReady -ProbeLabel "dev-api"
. "$root\scripts\dev-python.ps1"
$python = Resolve-DevPython

$args = @("--host", "127.0.0.1", "--port", "7888")
if ($env:MOSS_DEV_RELOAD -eq "1") {
  $args += "--reload"
}

& $python -m uvicorn backend.app.main:app @args
