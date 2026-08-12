<#
run.ps1 - Single entry point for scoring a MOSS agent-eval task.

Purpose:
  Wraps scripts/agent_eval/validate_task.py with `--measure --require-measured`,
  writes scorecard.json and result.json into an output directory, prints the
  scorecard path/status/score, and passes the validator exit code through
  (0 = pass, 1 = fail, 2 = invalid input). Wrapper-level setup errors
  (no usable interpreter, missing task file) also exit 2.

Windows caveat (why this script does interpreter discovery):
  On some machines a bare `python` on PATH resolves to an unrelated virtualenv
  (wrong version, missing packages), so this script never invokes `python`
  directly. Discovery order:
    1. uv run --project backend -- python
       Probed with `uv --version`, then a real `uv run ... -c "import sys"`
       check, because uv may exist while the backend environment is broken or
       not synced (note: the probe lets uv sync backend deps if it decides to).
    2. py -3.11  (Windows launcher; the project pins Python 3.11)
    3. $env:MOSS_PYTHON  (explicit override: full path to a python executable)
  No user-specific absolute path is hardcoded here on purpose.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts/agent_eval/run.ps1 `
    -Task scripts/agent_eval/tasks/<task>.json [-BaseRef <git-ref>] [-OutDir <dir>]

  -Task    (required) path to the task JSON file.
  -BaseRef (optional) git ref forwarded as --base-ref for changed-file diffing.
  -OutDir  (optional) output directory; default .codex-tmp/agent-eval/runs/<timestamp>.

Note: measuring runs the task's declared checks (e.g. npm test/typecheck), so a
full run can take several minutes.
#>

param(
    [string]$Task,
    [string]$BaseRef,
    [string]$OutDir
)

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Resolve-InputPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Path))
}

function Test-InterpreterCommand {
    param([string]$Exe, [string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Exe @Arguments *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

if (-not $Task) {
    [Console]::Error.WriteLine('run.ps1: -Task is required.')
    [Console]::Error.WriteLine('Usage: powershell -ExecutionPolicy Bypass -File scripts/agent_eval/run.ps1 -Task <task.json> [-BaseRef <ref>] [-OutDir <dir>]')
    exit 2
}

$taskPath = Resolve-InputPath $Task
if (-not (Test-Path -LiteralPath $taskPath -PathType Leaf)) {
    [Console]::Error.WriteLine("run.ps1: task file not found: $taskPath")
    exit 2
}

if (-not $OutDir) {
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $OutDir = Join-Path $repoRoot ".codex-tmp\agent-eval\runs\$timestamp"
} else {
    $OutDir = Resolve-InputPath $OutDir
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# --- Interpreter discovery (see header) ---
$backendProject = Join-Path $repoRoot 'backend'
$interpreterExe = $null
$interpreterArgs = @()
$interpreterTier = $null

if (Test-InterpreterCommand 'uv' @('--version')) {
    $uvRunArgs = @('run', '--project', $backendProject, '--', 'python')
    if (Test-InterpreterCommand 'uv' ($uvRunArgs + @('-c', 'import sys'))) {
        $interpreterExe = 'uv'
        $interpreterArgs = $uvRunArgs
        $interpreterTier = 'uv run --project backend -- python'
    } else {
        Write-Host 'run.ps1: uv is installed but "uv run --project backend" is not usable; trying py -3.11.'
    }
} else {
    Write-Host 'run.ps1: uv not found; trying py -3.11.'
}

if (-not $interpreterExe) {
    if (Test-InterpreterCommand 'py' @('-3.11', '-c', 'import sys')) {
        $interpreterExe = 'py'
        $interpreterArgs = @('-3.11')
        $interpreterTier = 'py -3.11'
    } else {
        Write-Host 'run.ps1: py -3.11 not usable; trying MOSS_PYTHON.'
    }
}

if (-not $interpreterExe) {
    $mossPython = $env:MOSS_PYTHON
    if ($mossPython -and (Test-InterpreterCommand $mossPython @('-c', 'import sys'))) {
        $interpreterExe = $mossPython
        $interpreterArgs = @()
        $interpreterTier = "MOSS_PYTHON ($mossPython)"
    }
}

if (-not $interpreterExe) {
    [Console]::Error.WriteLine('run.ps1: no usable Python interpreter found. Fix one of:')
    [Console]::Error.WriteLine('  1. Install uv and sync the backend env:  uv sync --project backend')
    [Console]::Error.WriteLine('  2. Install Python 3.11 with the Windows launcher so `py -3.11` works')
    [Console]::Error.WriteLine('  3. Set MOSS_PYTHON to a Python 3.11+ executable, e.g.:')
    [Console]::Error.WriteLine('     $env:MOSS_PYTHON = "C:\path\to\python.exe"')
    exit 2
}

# --- Run the validator from the repo root ---
$validateScript = Join-Path $PSScriptRoot 'validate_task.py'
$scorecardPath = Join-Path $OutDir 'scorecard.json'
$resultPath = Join-Path $OutDir 'result.json'

$validateArgs = @(
    $validateScript,
    '--task', $taskPath,
    '--measure',
    '--require-measured',
    '--repo-root', $repoRoot,
    '--out', $scorecardPath,
    '--result-out', $resultPath
)
if ($BaseRef) {
    $validateArgs += @('--base-ref', $BaseRef)
}
$fullArgs = $interpreterArgs + $validateArgs

Write-Host "run.ps1: interpreter tier -> $interpreterTier"
Write-Host "run.ps1: running -> $interpreterExe $($fullArgs -join ' ')"

# stderr from the validator (e.g. the unprobed-gates report) is intentionally
# left unredirected so it shows up in the console as-is.
Push-Location $repoRoot
try {
    & $interpreterExe @fullArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if (Test-Path -LiteralPath $scorecardPath -PathType Leaf) {
    $scorecard = Get-Content -LiteralPath $scorecardPath -Raw | ConvertFrom-Json
    Write-Host ''
    Write-Host "run.ps1: scorecard -> $scorecardPath"
    Write-Host "run.ps1: result    -> $resultPath"
    Write-Host "run.ps1: status    -> $($scorecard.status)"
    Write-Host "run.ps1: score     -> $($scorecard.score)"
} else {
    Write-Host "run.ps1: no scorecard written (validator exited $exitCode before scoring)."
}

exit $exitCode
