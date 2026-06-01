function Resolve-DevPython {
  param(
    [string[]]$RequiredModules = @("fastapi", "uvicorn", "dramatiq", "redis", "duckdb", "sqlalchemy", "psycopg")
  )

  $root = Split-Path -Parent $PSScriptRoot
  $venvPython = Join-Path $root ".venv\Scripts\python.exe"
  $candidates = @()
  if (Test-Path $venvPython) {
    $candidates += $venvPython
  }
  $systemPythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($systemPythonCommand) {
    $candidates += $systemPythonCommand.Source
  }
  $check = "import importlib, sys; [importlib.import_module(name) for name in sys.argv[1:]]"
  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    & $candidate -X utf8 -c $check @RequiredModules 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) {
      return $candidate
    }
  }
  throw "No Python interpreter with required modules: $($RequiredModules -join ', ')"
}
