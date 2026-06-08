$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "frontend")

function Test-NodePackageResolvable {
  param(
    [Parameter(Mandatory = $true)]
    [string]$packageName
  )

  $probe = 'const $packageName = process.argv[1]; require.resolve($packageName);'
  node -e $probe $packageName > $null 2>&1
  return ($LASTEXITCODE -eq 0)
}

function Ensure-FrontendOptionalNativeDependencies {
  $platform = (node -p "process.platform" 2>$null).Trim()
  if ($platform -ne "linux") {
    return
  }

  $packageName = "@rolldown/binding-linux-x64-gnu"
  if (Test-NodePackageResolvable -packageName $packageName) {
    return
  }

  Write-Host "WSL/Linux Vite native dependency missing: $packageName. Repairing optional dependencies..." -ForegroundColor Yellow
  npm install --include=optional

  if (-not (Test-NodePackageResolvable -packageName $packageName)) {
    throw "WSL/Linux Vite native dependency missing after npm install: $packageName"
  }
}

if (-not (Test-Path ".\node_modules")) {
 Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
}
Ensure-FrontendOptionalNativeDependencies

Write-Host "MOSS frontend: http://127.0.0.1:5888/ (also try http://localhost:5888/)" -ForegroundColor Cyan
Write-Host "API proxy targets http://127.0.0.1:7888 — start backend with .\scripts\dev-api.ps1" -ForegroundColor Gray

if (-not $env:VITE_DATA_SOURCE) {
  $env:VITE_DATA_SOURCE = "real"
}
Write-Host "Frontend data source: $env:VITE_DATA_SOURCE" -ForegroundColor Gray

npm run dev
