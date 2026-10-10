$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# This is the only full-stack development entry point that enables the Agent.
$agentEnvironmentNames = @(
  "MOSS_AGENT_ENABLED",
  "MOSS_AGENT_DEV_SCOPE_BYPASS",
  "MOSS_DEV_API_SCRIPT",
  "VITE_MOSS_AGENT_FRONTEND_ENABLED"
)
$originalAgentEnvironment = @{}
foreach ($name in $agentEnvironmentNames) {
  $originalAgentEnvironment[$name] = Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue
}

$devUpExitCode = 1
try {
  $env:MOSS_AGENT_ENABLED = "true"
  $env:MOSS_AGENT_DEV_SCOPE_BYPASS = "true"
  $env:MOSS_DEV_API_SCRIPT = "dev-agent-api.ps1"
  $env:VITE_MOSS_AGENT_FRONTEND_ENABLED = "true"

  Write-Host "[MOSS Agent] Starting the Agent development stack." -ForegroundColor Cyan
  Write-Host "[MOSS Agent] API script=$($env:MOSS_DEV_API_SCRIPT) frontend enabled=$($env:VITE_MOSS_AGENT_FRONTEND_ENABLED)" -ForegroundColor DarkGray

  & "$root\scripts\dev-up.ps1"
  $devUpExitCode = $LASTEXITCODE
} finally {
  foreach ($name in $agentEnvironmentNames) {
    $originalValue = $originalAgentEnvironment[$name]
    if ($null -eq $originalValue) {
      Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    } else {
      Set-Item -Path "Env:$name" -Value $originalValue.Value
    }
  }
}

exit $devUpExitCode
