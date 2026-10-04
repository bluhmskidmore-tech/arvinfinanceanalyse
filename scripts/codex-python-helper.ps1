function Resolve-CodexPython {
  param(
    [string[]]$RequiredModules = @("fastapi", "uvicorn", "dramatiq", "redis", "duckdb", "sqlalchemy", "psycopg")
  )

  . (Join-Path $PSScriptRoot "dev-python.ps1")
  $root = Split-Path -Parent $PSScriptRoot
  $fallbackProjectRoots = @()
  if (-not $env:MOSS_PYTHON -and -not $env:VIRTUAL_ENV) {
    try {
      $gitCommonDir = & git -C $root rev-parse --path-format=absolute --git-common-dir 2>$null
      if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($gitCommonDir) -and (Test-Path -LiteralPath $gitCommonDir -PathType Container)) {
        $commonRoot = Split-Path -Parent $gitCommonDir
        if ([System.IO.Path]::GetFullPath($commonRoot) -ne [System.IO.Path]::GetFullPath($root)) {
          $fallbackProjectRoots = @($commonRoot)
        }
      }
    } catch {
      # Git discovery is optional; the shared resolver still validates project environments.
    }
  }
  return (Resolve-DevPython -RequiredModules $RequiredModules -FallbackProjectRoots $fallbackProjectRoots)
}
