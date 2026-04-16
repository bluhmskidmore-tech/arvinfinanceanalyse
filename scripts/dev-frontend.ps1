$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "frontend")

if (-not (Test-Path ".\node_modules")) {
 Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host "MOSS frontend: http://127.0.0.1:5888/ (also try http://localhost:5888/)" -ForegroundColor Cyan
Write-Host "API proxy targets http://127.0.0.1:7888 — start backend with .\scripts\dev-api.ps1" -ForegroundColor Gray

npm run dev
