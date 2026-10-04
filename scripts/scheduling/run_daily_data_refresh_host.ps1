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
    [string]$VendorSourceIp = "",
    [switch]$PublicationOnly,
    [string]$AggregateRunId = "",
    [string]$AggregateReceiptPath = "",
    [string]$PythonExe = "",
    [switch]$BalanceMovementOnly,
    [string]$BalanceMovementReceiptPath = "",
    [string]$BalanceMovementDuckdbPath = "",
    [string]$BalanceMovementGovernanceDir = "",
    [string]$BalanceMovementCurrencyBasis = "CNX"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ($BalanceMovementOnly -and ($PublicationOnly -or $ResolveOnly -or $DryRun)) {
    throw "BalanceMovementOnly cannot be combined with publication, network resolution, or dry-run modes."
}
if (-not $ResolveOnly) {
    $hostLogDirectory = Join-Path $repoRoot "data\logs"
    [IO.Directory]::CreateDirectory($hostLogDirectory) | Out-Null
    $hostLogPrefix = if ($BalanceMovementOnly) { "balance_movement_host" } else { "market_daily_host" }
    $hostLogPath = Join-Path $hostLogDirectory ("{0}_{1}.log" -f $hostLogPrefix, (Get-Date -Format "yyyyMMdd"))
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

if ($ResolveOnly) {
    $resolved = Resolve-VendorSourceIp
    [pscustomobject]@{ vendor_source_ip = $resolved.Address; interface = $resolved.Interface } |
        ConvertTo-Json -Compress
    exit 0
}

. (Join-Path $repoRoot "scripts\dev-env.ps1")
$chainArguments = @{}
if (-not $BalanceMovementOnly) {
    $vendorAddress = $VendorSourceIp
    if (-not $vendorAddress) {
        $resolvedNetwork = Resolve-VendorSourceIp
        $vendorAddress = $resolvedNetwork.Address
    }
    $chainArguments = @{ VendorSourceIp = $vendorAddress; TushareStockGapRepair = $true }
    if ($DryRun) { $chainArguments.DryRun = $true }
    if ($AsOfDate) { $chainArguments.AsOfDate = $AsOfDate }
    if ($PythonExe) { $chainArguments.PythonExe = $PythonExe }
}

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
$refreshName = if ($BalanceMovementOnly) { "Balance movement freshness" } else { "Daily market refresh" }
$maintenanceReason = "${refreshName}: release local API DuckDB readers [$maintenanceCorrelationId]"
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

    if ($BalanceMovementOnly) {
        $watchArguments = @(
            (Join-Path $repoRoot "scripts\balance_movement_freshness_watch.py"),
            "--run-once", "--run-kind", "scheduled",
            "--maintenance-owner-token", [string]$maintenanceState.owner_token,
            "--currency-basis", $BalanceMovementCurrencyBasis
        )
        if ($BalanceMovementReceiptPath) { $watchArguments += @("--receipt-path", $BalanceMovementReceiptPath) }
        if ($BalanceMovementDuckdbPath) { $watchArguments += @("--duckdb-path", $BalanceMovementDuckdbPath) }
        if ($BalanceMovementGovernanceDir) { $watchArguments += @("--governance-dir", $BalanceMovementGovernanceDir) }
        & $runtimePython @watchArguments
    } else {
        & (Join-Path $PSScriptRoot "daily_data_refresh.ps1") @chainArguments
    }
    $refreshExitCode = [int]$LASTEXITCODE
    if ($refreshExitCode -ne 0) {
        $primaryFailure = "$refreshName exited with code $refreshExitCode."
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
