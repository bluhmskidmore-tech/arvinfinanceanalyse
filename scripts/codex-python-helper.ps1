function Resolve-CodexPython {
  param(
    [string[]]$RequiredModules = @("fastapi", "uvicorn", "dramatiq", "redis", "duckdb", "sqlalchemy", "psycopg")
  )

  $candidates = New-Object System.Collections.Generic.List[string]
  $seen = @{}

  function Add-Candidate {
    param(
      [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
      return
    }
    if (-not (Test-Path -LiteralPath $Path)) {
      return
    }
    if ($seen.ContainsKey($Path)) {
      return
    }

    $seen[$Path] = $true
    [void]$candidates.Add($Path)
  }

  Add-Candidate (Join-Path (Split-Path -Parent $PSScriptRoot) ".venv\Scripts\python.exe")

  $gitCommonDir = & git rev-parse --path-format=absolute --git-common-dir
  if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($gitCommonDir)) {
    Add-Candidate (Join-Path (Split-Path -Parent $gitCommonDir) ".venv\Scripts\python.exe")
  }

  $systemPythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($systemPythonCommand) {
    Add-Candidate $systemPythonCommand.Source
  }

  $check = "import importlib, sys; [importlib.import_module(name) for name in sys.argv[1:]]"
  foreach ($candidate in $candidates) {
    & $candidate -X utf8 -c $check @RequiredModules 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) {
      return $candidate
    }
  }

  throw "No Python interpreter with required modules: $($RequiredModules -join ', ')"
}
