$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python -ErrorAction Stop).Source
& $python "$root\scripts\dev_postgres_cluster.py" reset-schema --repo-root $root
