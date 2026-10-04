# Shared script-level coordination. This file does not start services or open databases.
function Get-DevRuntimeDirectory {
  $current = $root
  foreach ($part in @("tmp-governance", "runtime-clean", "control")) {
    $current = Join-Path $current $part
    if (([System.IO.Directory]::Exists($current) -or [System.IO.File]::Exists($current)) -and
        (([System.IO.File]::GetAttributes($current) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
      throw "Runtime state must not traverse links or junctions"
    }
  }
  return $current
}

function Assert-DevRuntimeAllowed {
  $marker = Join-Path (Get-DevRuntimeDirectory) "maintenance.json"
  if ([System.IO.File]::Exists($marker) -or [System.IO.Directory]::Exists($marker)) {
    throw "Maintenance blocks runtime changes. Existing processes are not certified drained."
  }
}

function Invoke-DevRuntimeAction {
  param([Parameter(Mandatory = $true)][scriptblock]$Action)
  $directory = Get-DevRuntimeDirectory
  [System.IO.Directory]::CreateDirectory($directory) | Out-Null
  $lockPath = Join-Path $directory "operation.lock"
  $deadline = [DateTime]::UtcNow.AddSeconds(30)
  $lease = $null
  while ($null -eq $lease) {
    try {
      $lease = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    } catch [System.IO.IOException] {
      if ([DateTime]::UtcNow -ge $deadline) { throw "Runtime operation lock unavailable" }
      Start-Sleep -Milliseconds 50
    }
  }
  try {
    Assert-DevRuntimeAllowed
    # Bounded actions only. The action must not invoke another guarded helper.
    & $Action
  } finally {
    $lease.Dispose()
  }
}

function Get-DevRuntimePython {
  . (Join-Path $root "scripts\dev-python.ps1")
  return Resolve-DevPython
}

function Get-DevFrontendPlan {
  $runtimePython = Get-DevRuntimePython
  $json = & $runtimePython (Join-Path $root "scripts\dev_runtime_control.py") --repo-root $root frontend-plan
  if ($LASTEXITCODE -ne 0) { throw "Selected frontend build is unavailable; recovery refused" }
  return ($json | ConvertFrom-Json)
}

function Invoke-DevRuntimeProcess {
  param([Parameter(Mandatory = $true)][string[]]$Command)
  $payload = @{ argv = @($Command); cwd = (Get-Location).Path } | ConvertTo-Json -Compress
  $encoded = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($payload))
  $runtimePython = Get-DevRuntimePython
  & $runtimePython (Join-Path $root "scripts\dev_runtime_control.py") --repo-root $root run --command-base64 $encoded
  if ($LASTEXITCODE -ne 0) { throw "Guarded runtime process exited with code $LASTEXITCODE" }
}
