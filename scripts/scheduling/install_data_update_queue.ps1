# Install the data-center queue consumer. Existing market timers are preserved.
[CmdletBinding(SupportsShouldProcess = $true)]
param([string]$RepoRoot = "", [switch]$Unregister)

$ErrorActionPreference = "Stop"
$taskName = "MOSS-DataUpdateQueue"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if (-not $Unregister -and -not $WhatIfPreference) {
    . (Join-Path $RepoRoot "scripts\dev-python.ps1")
    $pythonExe = Resolve-DevPython -RequiredModules @("duckdb")
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Repository Python not found." }
}
if ($Unregister) {
    if ($PSCmdlet.ShouldProcess($taskName, "Unregister scheduled task")) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    return
}

$wrapper = Join-Path $RepoRoot "scripts\scheduling\drain_data_updates.ps1"
if (-not [IO.File]::Exists($wrapper)) { throw "Data update queue launcher not found." }
$powershellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$action = New-ScheduledTaskAction -Execute $powershellExe `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$wrapper`"" `
    -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 6)
if ($PSCmdlet.ShouldProcess($taskName, "Register data-center consumer every five minutes")) {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "Process explicitly requested financial report dates; wait for required files." `
        -Force | Out-Null
}
