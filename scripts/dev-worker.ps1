$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. "$root\scripts\dev-env.ps1"
Assert-DevBootstrapStorageReady -ProbeLabel "dev-worker"
$env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS = "1"
. "$root\scripts\dev-python.ps1"
$python = Resolve-DevPython
$workerProcesses = if ([string]::IsNullOrWhiteSpace($env:MOSS_DEV_WORKER_PROCESSES)) {
  "1"
} else {
  $env:MOSS_DEV_WORKER_PROCESSES
}
$workerThreads = if ([string]::IsNullOrWhiteSpace($env:MOSS_DEV_WORKER_THREADS)) {
  "4"
} else {
  $env:MOSS_DEV_WORKER_THREADS
}

& $python -m dramatiq --processes $workerProcesses --threads $workerThreads backend.app.tasks.worker_bootstrap
