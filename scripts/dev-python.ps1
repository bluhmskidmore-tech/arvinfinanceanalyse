function Resolve-DevPython {
  param(
    [string[]]$RequiredModules = @("fastapi", "uvicorn", "dramatiq", "redis", "duckdb", "sqlalchemy", "psycopg"),
    [string[]]$FallbackProjectRoots = @()
  )

  $root = Split-Path -Parent $PSScriptRoot
  $explicit = $false
  if ($env:MOSS_PYTHON) {
    $candidates = @($env:MOSS_PYTHON)
    $explicit = $true
  } elseif ($env:VIRTUAL_ENV) {
    $candidates = @(Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
    $explicit = $true
  } else {
    $candidates = @(
      (Join-Path $root "backend\.venv\Scripts\python.exe"),
      (Join-Path $root ".venv\Scripts\python.exe")
    )
    foreach ($fallbackRoot in $FallbackProjectRoots) {
      if (-not [string]::IsNullOrWhiteSpace($fallbackRoot)) {
        $candidates += @(
          (Join-Path $fallbackRoot "backend\.venv\Scripts\python.exe"),
          (Join-Path $fallbackRoot ".venv\Scripts\python.exe")
        )
      }
    }
  }
  $check = 'import importlib, json, sys; assert sys.version_info[:2] == (3, 11); [importlib.import_module(name) for name in sys.argv[1:]]; print(json.dumps(dict(path=sys.executable, version=list(sys.version_info[:3]))))'
  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
    try {
      $probe = & $candidate -X utf8 -c $check @RequiredModules 2>$null
    } catch {
      # Required-module and version failures may surface as native errors in PowerShell 5.1.
      continue
    }
    if ($LASTEXITCODE -ne 0) { continue }
    try {
      $observed = $probe | ConvertFrom-Json
      if ($observed.path -and $observed.version[0] -eq 3 -and $observed.version[1] -eq 11) {
        Write-Host "Runtime Python: $($observed.path) ($($observed.version -join '.'))"
        return $observed.path
      }
    } catch {
      # A failed or noisy interpreter probe is not an eligible environment.
    }
  }
  $selection = if ($explicit) { "Explicit Python selection is unusable: $($candidates -join ', ')." } else { "No compatible project Python environment was found." }
  throw "$selection Python 3.11 with required modules ($($RequiredModules -join ', ')) is required. Use the documented locked backend install or select an existing interpreter with MOSS_PYTHON."
}
