param(
  [ValidateRange(1, 65535)]
  [int]$Port = 5890
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. "$root\scripts\dev-runtime-common.ps1"
Assert-DevRuntimeAllowed

$nodeExecutable = (Get-Command node -ErrorAction Stop).Source
& $nodeExecutable (Join-Path $root "scripts\dev-frontend-source.mjs") --port $Port
exit $LASTEXITCODE
