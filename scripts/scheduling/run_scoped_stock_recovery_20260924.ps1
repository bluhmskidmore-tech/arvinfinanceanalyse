<#
.SYNOPSIS
  Run the existing daily chain using the active physical network adapter.
.DESCRIPTION
  The scheduled task used a literal Wi-Fi address that expired after a network
  change. Resolve the address on each run; do not select the VPN's default route.
  Existing ETL order, receipts, legacy timer ownership and governance are retained.

  The local API is drained under the runtime maintenance lease. The API is
  launched through several PowerShell/cmd/Python wrappers, so discovering only
  the leaf uvicorn process is unsafe: a wrapper can keep a DuckDB reader alive or
  restart the API while the writer is running. This wrapper captures the exact,
  repository-owned API process tree before stopping anything and refuses to stop
  a process whose identity cannot be proven.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$AsOfDate = "",
    [switch]$ResolveOnly,
    [switch]$PublicationOnly,
    [string]$AggregateRunId = "",
    [string]$AggregateReceiptPath = "",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $ResolveOnly) {
    $hostLogDirectory = Join-Path $repoRoot "data\logs"
    [IO.Directory]::CreateDirectory($hostLogDirectory) | Out-Null
    $hostLogPath = "G:\MOSS-stock-recovery\20260924\scoped-recovery-host.log"
    Start-Transcript -Path $hostLogPath -Append -Force | Out-Null
}
if ($PublicationOnly) {
    $recoveryArguments = @{
        PublicationOnly = $true
        AggregateRunId = $AggregateRunId
        AggregateReceiptPath = $AggregateReceiptPath
    }
    if ($AsOfDate) { $recoveryArguments.AsOfDate = $AsOfDate }
    if ($PythonExe) { $recoveryArguments.PythonExe = $PythonExe }
    & (Join-Path $PSScriptRoot "daily_data_refresh.ps1") @recoveryArguments
    exit $LASTEXITCODE
}

. (Join-Path $PSScriptRoot "market_refresh_host_common.ps1")

# Preserve the date-specific recovery classifier.
function Get-ApiProcessTree {
    $listeners = @(Get-ApiPortListeners)
    $processes = @(Get-ProcessSnapshot)
    $byId = @{}
    foreach ($process in $processes) {
        $byId[[int]$process.ProcessId] = $process
    }
    $keepaliveEntries = @(Get-VerifiedKeepaliveEntries -Processes $processes)
    $listenerPids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($listenerPids.Count -gt 1) {
        throw ("Port 7888 has multiple listeners ({0}); API identity is ambiguous and the writer was not started." -f ($listenerPids -join ","))
    }
    if ($listenerPids.Count -eq 0) {
        # A wrapper can survive after uvicorn has already lost its socket. It
        # still owns DuckDB readers, so discover it from its repository API
        # command line and drain its owned tree before writing.
        $apiCandidates = @($processes | Where-Object {
            (Test-ApiListenerIdentity -Process $_ -ProcessesById $byId) -or
            (Test-ApiWrapperSeedIdentity -Process $_ -ProcessesById $byId)
        })
        if ($apiCandidates.Count -eq 0) {
            $unverifiableApiLikeProcesses = @($processes | Where-Object {
                (Test-RepositoryCommand -Process $_) -and
                ([string]$_.CommandLine -match '(?i)(backend(?:[\\/.])app(?:[\\/.])main:app|dev_runtime_control\.py|scripts[\\/]dev-(?:agent-)?api\.ps1)') -and
                -not (Test-ApprovedApiExecutable -Process $_ -ProcessesById $byId)
            })
            if ($unverifiableApiLikeProcesses.Count -gt 0) {
                throw ("Repository-like API processes have unverifiable executable identity ({0}); writer was not started." -f
                    (($unverifiableApiLikeProcesses | Select-Object -ExpandProperty ProcessId) -join ","))
            }
            return [pscustomobject]@{
                Processes = @()
                ListenerProcessId = $null
                KeepaliveEntries = $keepaliveEntries
                ApiScriptName = $null
            }
        }
        # A dev-agent-api tree can legitimately contain both the outer agent
        # wrapper and its inner dev-api wrapper. Collapse candidates to their
        # single top-most owned root; unrelated roots remain ambiguous.
        $candidateIds = @{}
        foreach ($candidate in $apiCandidates) {
            $candidateIds[[int]$candidate.ProcessId] = $true
        }
        $candidateRoots = @($apiCandidates | Where-Object {
            $ancestorId = [int]$_.ParentProcessId
            $hasCandidateAncestor = $false
            $seenAncestors = @{}
            while ($ancestorId -gt 0 -and $byId.ContainsKey($ancestorId) -and -not $seenAncestors.ContainsKey($ancestorId)) {
                $seenAncestors[$ancestorId] = $true
                if ($candidateIds.ContainsKey($ancestorId)) {
                    $hasCandidateAncestor = $true
                    break
                }
                if (-not (Test-ApiWrapperIdentity -Process $byId[$ancestorId] -ProcessesById $byId)) { break }
                $ancestorId = [int]$byId[$ancestorId].ParentProcessId
            }
            -not $hasCandidateAncestor
        })
        if ($candidateRoots.Count -ne 1) {
            throw ("Port 7888 is closed but repository API processes have {0} unrelated roots ({1}); API identity is ambiguous and the writer was not started." -f
                $candidateRoots.Count, (($apiCandidates | Select-Object -ExpandProperty ProcessId) -join ","))
        }
        $listenerPid = [int]$candidateRoots[0].ProcessId
    } else {
        $listenerPid = [int]$listenerPids[0]
    }
    if (-not $byId.ContainsKey($listenerPid)) {
        throw "Port 7888 listener PID $listenerPid is not present in the process table; API identity is unverifiable."
    }
    $listenerProcess = $byId[$listenerPid]
    $hasListenerIdentity = Test-ApiListenerIdentity -Process $listenerProcess -ProcessesById $byId
    if ($listeners.Count -gt 0 -and -not $hasListenerIdentity) {
        throw "Port 7888 listener PID $listenerPid is not the repository API; API drain refused."
    }
    if ($listeners.Count -eq 0 -and -not $hasListenerIdentity -and
        -not (Test-ApiWrapperSeedIdentity -Process $listenerProcess -ProcessesById $byId)) {
        throw "Repository API wrapper PID $listenerPid is not an approved dev-api entrypoint; API drain refused."
    }

    $related = @{}
    $related[$listenerPid] = [pscustomobject]@{
        Process = $listenerProcess
        Identity = Get-ProcessIdentity -Process $listenerProcess
        Distance = 0
    }

    # Capture owned ancestors. The first non-repository parent is deliberately
    # excluded (for example WmiPrvSE); it is outside this task's ownership.
    $current = $listenerProcess
    $distance = 0
    while ($current.ParentProcessId -and [int]$current.ParentProcessId -gt 0) {
        $parentId = [int]$current.ParentProcessId
        if ($related.ContainsKey($parentId)) { break }
        if (-not $byId.ContainsKey($parentId)) { break }
        $parent = $byId[$parentId]
        if (-not (Test-ApiWrapperIdentity -Process $parent -ProcessesById $byId)) { break }
        $distance -= 1
        $related[$parentId] = [pscustomobject]@{
            Process = $parent
            Identity = Get-ProcessIdentity -Process $parent
            Distance = $distance
        }
        $current = $parent
    }

    # Capture owned descendants as well. This covers uvicorn reload/workers and
    # cmd/powershell wrappers that sit below the process visible on the port.
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($process in $processes) {
            $processId = [int]$process.ProcessId
            $parentId = [int]$process.ParentProcessId
            if ($related.ContainsKey($processId) -or -not $related.ContainsKey($parentId)) { continue }
            if (-not (Test-ApiWrapperIdentity -Process $process -ProcessesById $byId)) { continue }
            $related[$processId] = [pscustomobject]@{
                Process = $process
                Identity = Get-ProcessIdentity -Process $process
                Distance = ([int]$related[$parentId].Distance + 1)
            }
            $changed = $true
        }
    }

    $apiCommands = @($related.Values | ForEach-Object { [string]$_.Identity.CommandLine })
    $hasAgentApiEntrypoint = @($apiCommands | Where-Object {
        Test-CommandUsesRepositoryScriptEntrypoint -CommandLine $_ -RelativePath "scripts\dev-agent-api.ps1"
    }).Count -gt 0
    $hasRegularApiEntrypoint = @($apiCommands | Where-Object {
        Test-CommandUsesRepositoryScriptEntrypoint -CommandLine $_ -RelativePath "scripts\dev-api.ps1"
    }).Count -gt 0
    if ($hasAgentApiEntrypoint) {
        $apiScriptName = "dev-agent-api.ps1"
    } elseif ($hasRegularApiEntrypoint) {
        $apiScriptName = "dev-api.ps1"
    } else {
        throw "Repository API process tree has no verified dev-api entrypoint; drain refused."
    }

    return [pscustomobject]@{
        Processes = @($related.Values | Sort-Object Distance, @{ Expression = { $_.Process.ProcessId } })
        ListenerProcessId = $listenerPid
        KeepaliveEntries = $keepaliveEntries
        ApiScriptName = $apiScriptName
    }
}


if ($ResolveOnly) {
    $resolved = Resolve-VendorSourceIp
    [pscustomobject]@{ vendor_source_ip = $resolved.Address; interface = $resolved.Interface } |
        ConvertTo-Json -Compress
    exit 0
}

. (Join-Path $repoRoot "scripts\dev-env.ps1")
$resolvedNetwork = Resolve-VendorSourceIp
$vendorAddress = $resolvedNetwork.Address
$chainArguments = @{ VendorSourceIp = $vendorAddress; TushareStockGapRepair = $true }
if ($DryRun) { $chainArguments.DryRun = $true }
if ($AsOfDate) { $chainArguments.AsOfDate = $AsOfDate }
if ($PythonExe) { $chainArguments.PythonExe = $PythonExe }

# The local API retains DuckDB read handles. Always acquire maintenance before
# discovering or stopping API processes, so keepalive cannot launch a new reader
# in the gap between discovery and the lease.
$maintenanceState = $null
$apiTree = $null
$drainState = [pscustomobject]@{
    ApiWasDrained = $false
    ApiScriptName = $null
    KeepaliveEntries = @()
}
$refreshExitCode = 0
$primaryFailure = $null
$recoveryFailures = @()
$runtimePython = if ($PythonExe) { $PythonExe } else { $devEnvPython }
$runtimeControl = Join-Path $repoRoot "scripts\dev_runtime_control.py"
$maintenanceCorrelationId = [Guid]::NewGuid().ToString("N")
$maintenanceReason = "Daily market refresh: release local API DuckDB readers [$maintenanceCorrelationId]"
$maintenanceMarkerPath = Join-Path $repoRoot "tmp-governance\runtime-clean\control\maintenance.json"
$maintenanceAcquired = $false
$maintenanceReleased = $false
$keepaliveState = [pscustomobject]@{
    Running = $false
    Missing = $true
    IdentityChanged = $false
}
$keepaliveRecoveryLock = $null
try {
    if (-not $DryRun) {
        # Windows PowerShell can promote native stderr to a terminating error
        # under ErrorActionPreference=Stop. Capture it without aborting so a
        # claim already written by `enter` can still be identified and released.
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $maintenanceOutput = @(& $runtimePython $runtimeControl enter --reason $maintenanceReason 2>&1)
            $maintenanceEnterExitCode = [int]$LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        $maintenanceJson = @($maintenanceOutput | Where-Object { [string]$_ -match '^\s*\{.*\}\s*$' } | Select-Object -Last 1)
        $returnedState = $null
        if ($maintenanceJson.Count -eq 1) {
            try { $returnedState = ([string]$maintenanceJson[0]) | ConvertFrom-Json } catch { $returnedState = $null }
        }
        $markerState = Read-MaintenanceMarker -Path $maintenanceMarkerPath
        if ($null -ne $returnedState -and -not [string]::IsNullOrWhiteSpace([string]$returnedState.owner_token)) {
            if ($null -eq $markerState -or
                [string]$markerState.owner_token -ne [string]$returnedState.owner_token -or
                [string]$markerState.reason -ne $maintenanceReason) {
                throw "Maintenance enter returned an owner token but maintenance.json was not durable."
            }
            $maintenanceState = $returnedState
            $maintenanceAcquired = $true
            if ($maintenanceEnterExitCode -ne 0) {
                throw "Maintenance enter exited with code $maintenanceEnterExitCode after writing a claim; claim adopted for cleanup."
            }
        } elseif ($null -ne $markerState -and [string]$markerState.reason -eq $maintenanceReason) {
            # enter_maintenance writes atomically before printing JSON. If the
            # command output was truncated, the per-run correlation ID in our
            # exact reason still proves ownership even if an older owner's
            # marker existed before this enter call. Adopt and release it.
            $maintenanceState = $markerState
            $maintenanceAcquired = $true
            throw "Maintenance enter wrote maintenance.json but did not return a valid owner token; claim adopted for cleanup."
        } elseif ($maintenanceEnterExitCode -ne 0) {
            throw "Could not acquire market refresh maintenance ownership."
        } else {
            throw "Market refresh maintenance ownership did not return a valid durable claim."
        }

        # Discovery happens only after the maintenance marker is durable.
        $apiTree = Get-ApiProcessTree
        Drain-ApiProcessTrees -InitialTree $apiTree -State $drainState | Out-Null
    }

    & "G:\MOSS-stock-recovery\20260924\run_scoped_recovery.ps1" -VendorSourceIp $vendorAddress -PythonExe $runtimePython
    $refreshExitCode = [int]$LASTEXITCODE
    if ($refreshExitCode -ne 0) {
        $primaryFailure = "daily_data_refresh.ps1 exited with code $refreshExitCode."
    }
} catch {
    $primaryFailure = $_.Exception.Message
    if ($refreshExitCode -eq 0) { $refreshExitCode = 1 }
} finally {
    if ($maintenanceAcquired -and $null -ne $maintenanceState -and $maintenanceState.owner_token) {
        if (-not $DryRun -and [bool]$drainState.ApiWasDrained) {
            try {
                # Revalidate the original keepalive while maintenance still
                # blocks all launchers. If it is gone or its PID was reused,
                # claim its instance lock before releasing maintenance.
                $keepaliveState = Test-KeepaliveProcessRunning -Entries @($drainState.KeepaliveEntries)
                if (-not $keepaliveState.Running) {
                    try {
                        $keepaliveRecoveryLock = Acquire-KeepaliveRecoveryLock
                    } catch {
                        # A replacement keepalive can legitimately take the
                        # instance lock during a long refresh. Prove its fresh
                        # identity before assigning recovery ownership to it.
                        $replacementEntries = @(Get-VerifiedKeepaliveEntries)
                        $replacementState = Test-KeepaliveProcessRunning -Entries $replacementEntries
                        if ($replacementState.Running) {
                            $keepaliveState = $replacementState
                            $drainState.KeepaliveEntries = $replacementEntries
                        } else {
                            throw
                        }
                    }
                }
            } catch {
                $recoveryFailures += ("keepalive recovery claim: " + $_.Exception.Message)
            }
        }
        try {
            & $runtimePython $runtimeControl leave --owner-token $maintenanceState.owner_token
            if ($LASTEXITCODE -ne 0) { throw "Could not release market refresh maintenance ownership." }
            $maintenanceReleased = $true
        } catch {
            $recoveryFailures += ("maintenance release: " + $_.Exception.Message)
        }

        if ($maintenanceReleased -and -not $DryRun -and [bool]$drainState.ApiWasDrained) {
            try {
                Start-CoreApiRecovery -KeepaliveState $keepaliveState -RuntimePython $runtimePython -RuntimeControl $runtimeControl `
                    -RecoveryLockHeld ($null -ne $keepaliveRecoveryLock) -ApiScriptName ([string]$drainState.ApiScriptName)
            } catch {
                $recoveryFailures += ("core API recovery: " + $_.Exception.Message)
            }
        }
        if ($null -ne $keepaliveRecoveryLock) {
            $keepaliveRecoveryLock.Dispose()
            $keepaliveRecoveryLock = $null
        }
    }
}

if ($null -ne $primaryFailure -or $recoveryFailures.Count -gt 0) {
    # Write directly to stderr so reporting a failure cannot overwrite the
    # refresh process exit code in Windows PowerShell's native-command state.
    [Console]::Error.WriteLine((Format-FailureMessage -PrimaryFailure $primaryFailure -RecoveryFailures $recoveryFailures))
    if ($refreshExitCode -le 0) { $refreshExitCode = 1 }
    exit $refreshExitCode
}
exit 0
