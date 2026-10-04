[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^data_update_[0-9a-f]{32}$')][string]$RunId,
    [switch]$Execute,
    [string]$ReceiptPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runtimeControl = Join-Path $repoRoot "scripts\dev_runtime_control.py"
$markerPath = Join-Path $repoRoot "tmp-governance\runtime-clean\control\maintenance.json"
$originalOwnerEnv = [Environment]::GetEnvironmentVariable('MOSS_DATA_UPDATE_PIT_MAINTENANCE_OWNER_TOKEN', 'Process')
$claim = $null
$recoveryLock = $null
$drainState = [pscustomobject]@{ApiWasDrained=$false;ApiScriptName=$null;KeepaliveEntries=@()}
$workerExit = $null
$workerStopVerified = $true
$completed = $false
$receiptStream = $null
$receipt = [ordered]@{run_id=$RunId;workflow='choice_stock_pit_history';status='blocked';maintenance_entered=$false;worker_started=$false;api_restored=$false;request_submitted=$false;reader_flags_changed=$false;started_at=[DateTime]::UtcNow.ToString('o')}

function Invoke-PitPython {
    param([string[]]$Arguments, [int]$TimeoutSeconds = 180)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $boundedProcess = Join-Path $repoRoot 'scripts\scheduling\pit_request_process.py'
        $output = @(& $runtimePython $boundedProcess --timeout-seconds $TimeoutSeconds -- @Arguments 2>$null)
        $code = [int]$LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    return [pscustomobject]@{ExitCode=$code;Output=$output}
}

function Open-PitReceipt {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $roots = @((Join-Path $repoRoot 'data\logs\'),(Join-Path $repoRoot '.codex-tmp\'))
    if (-not ($roots | Where-Object {$full.StartsWith($_,[StringComparison]::OrdinalIgnoreCase)}) -or [IO.Path]::GetExtension($full) -ne '.json') {
        throw 'PIT host receipt must be new JSON inside repository logs or task evidence.'
    }
    # Reject junctions/symlinks before creation. CreateNew rejects every existing
    # file, including aliases of source, target, backup, or another run receipt.
    $ancestor = [IO.Path]::GetDirectoryName($full)
    while ($ancestor) {
        if ([IO.Directory]::Exists($ancestor) -and ([IO.File]::GetAttributes($ancestor) -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'PIT receipt ancestors cannot be reparse points.'
        }
        $ancestor = [IO.Path]::GetDirectoryName($ancestor)
    }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($full)) | Out-Null
    return [IO.File]::Open($full,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
}

function Assert-PitOwner {
    if ($null -eq $claim -or -not [IO.File]::Exists($markerPath)) { throw 'PIT maintenance ownership is unavailable.' }
    $current = [IO.File]::ReadAllText($markerPath) | ConvertFrom-Json
    if ($current.state -ne 'launch_blocked' -or $current.owner_token -ne $claim.owner_token -or $current.reason -ne $claim.reason) {
        throw 'PIT maintenance ownership changed; no further runtime mutation is allowed.'
    }
}

function Enter-PitMaintenance {
    $reason = "PIT request $RunId [$([Guid]::NewGuid().ToString('N'))]"
    $result = Invoke-PitPython -Arguments @($runtimeControl,'--repo-root',$repoRoot,'enter','--reason',$reason)
    $durable = if ([IO.File]::Exists($markerPath)) { [IO.File]::ReadAllText($markerPath) | ConvertFrom-Json } else { $null }
    if ($null -ne $durable -and $durable.state -eq 'launch_blocked' -and $durable.reason -eq $reason -and $durable.owner_token) {
        $script:claim = $durable
        $receipt.maintenance_entered = $true
    }
    if ($result.ExitCode -ne 0 -or $null -eq $claim) { throw 'PIT maintenance enter failed.' }
    $returned = [string]$result.Output[-1] | ConvertFrom-Json
    if ($returned.owner_token -ne $claim.owner_token) { throw 'PIT maintenance claim was not durable.' }
}

function Leave-PitMaintenance {
    Assert-PitOwner
    $result = Invoke-PitPython -Arguments @($runtimeControl,'--repo-root',$repoRoot,'leave','--owner-token',$claim.owner_token)
    if ($result.ExitCode -ne 0) { throw 'PIT maintenance release failed.' }
    $script:claim = $null
}

function Invoke-PitOwnedDrain {
    param([object]$Tree)
    $operationPath = Join-Path $repoRoot 'tmp-governance\runtime-clean\control\operation.lock'
    $operationLease = $null
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while ($null -eq $operationLease) {
        try { $operationLease = [IO.File]::Open($operationPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None) }
        catch [IO.IOException] {
            if ([DateTime]::UtcNow -ge $deadline) { throw 'Runtime operation lock unavailable before PIT drain.' }
            Start-Sleep -Milliseconds 50
        }
    }
    try {
        Assert-PitOwner
        Drain-ApiProcessTrees -InitialTree $Tree -State $drainState | Out-Null
    } finally { $operationLease.Dispose() }
}

function Invoke-PitReadOnlyCheck {
    param([switch]$AfterWorker)
    $code = @'
import json,sys
from pathlib import Path
from backend.app.governance.settings import get_settings
from backend.app.repositories.data_update_repo import latest_runs
from backend.app.services.data_update_service import choice_stock_pit_preflight
from backend.app.tasks.data_update_choice_stock_pit import recover_choice_stock_pit_result
settings=get_settings()
run=next((r for r in latest_runs(settings.governance_path) if r.get('run_id')==sys.argv[1]),None)
if not run or run.get('workflow')!='choice_stock_pit_history':
    raise ValueError('Exact PIT request is unavailable')
if Path(str(run.get('target_duckdb_path',''))).resolve()!=Path(settings.duckdb_path).resolve():
    raise ValueError('PIT target database changed')
if sys.argv[2]=='after':
    print(json.dumps({'run_id':run['run_id'],'workflow':run['workflow'],'report_date':run['report_date'],'status':run['status']}))
else:
    if run.get('status') not in {'queued','running','completed'}:
        raise ValueError('PIT request is not executable')
    if run['status']=='running':
        # A verified committed receipt closes only governance bookkeeping.
        # Its original pre-import plan is no longer a valid current preview.
        recover_choice_stock_pit_result(settings,run)
    elif run['status']!='completed':
        if not Path(run['target_backup_path']).is_file():
            raise ValueError('Reviewed backup is unavailable')
        preflight=choice_stock_pit_preflight(settings,report_date=run['report_date'],source_duckdb_path=run['source_duckdb_path'],expected_source_sha256=run['expected_source_sha256'])
        if preflight['plan_sha256']!=run['expected_plan_sha256']:
            raise ValueError('Reviewed PIT plan changed')
    print(json.dumps({'run_id':run['run_id'],'workflow':run['workflow'],'report_date':run['report_date'],'status':run['status'],'requested_by':run.get('requested_by'),'read_only_ready':True}))
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $phase = if ($AfterWorker) { 'after' } else { 'before' }
    $result = Invoke-PitPython -Arguments @('-c',"import base64;exec(base64.b64decode('$encoded'))",$RunId,$phase)
    if ($result.ExitCode -ne 0) { throw 'PIT request/source/plan read-only check failed.' }
    $value = [string]$result.Output[-1] | ConvertFrom-Json
    if ($value.run_id -ne $RunId -or $value.workflow -ne 'choice_stock_pit_history') { throw 'PIT request identity mismatch.' }
    return $value
}

try {
    Set-Location -LiteralPath $repoRoot
    . (Join-Path $repoRoot 'scripts\dev-env.ps1')
    $runtimePython = $devEnvPython
    if (-not $runtimePython) { throw 'Repository Python is unavailable.' }
    $preflight = Invoke-PitReadOnlyCheck
    $receipt.report_date = $preflight.report_date
    $receipt.requested_by = $preflight.requested_by
    if (-not $Execute -or $preflight.status -eq 'completed') {
        $receipt.status = if ($preflight.status -eq 'completed') { 'already_completed' } else { 'prepared_only' }
        $completed = $true
    } else {
        . (Join-Path $PSScriptRoot "market_refresh_host_common.ps1")
        if (-not $ReceiptPath) {
            $ReceiptPath = Join-Path $repoRoot ("data\logs\pit-request-host-{0}-{1}.json" -f $RunId,[Guid]::NewGuid().ToString('N'))
        }
        $ReceiptPath = [IO.Path]::GetFullPath($ReceiptPath)
        $receiptStream = Open-PitReceipt -Path $ReceiptPath
        Enter-PitMaintenance
        Assert-PitOwner
        $tree = Get-ApiProcessTree
        Invoke-PitOwnedDrain -Tree $tree
        Assert-PitOwner
        $keepalive = Test-KeepaliveProcessRunning -Entries @($drainState.KeepaliveEntries)
        if (-not $keepalive.Running) { $recoveryLock = Acquire-KeepaliveRecoveryLock }
        $env:MOSS_DATA_UPDATE_PIT_MAINTENANCE_OWNER_TOKEN = [string]$claim.owner_token
        $receipt.worker_started = $true
        # Failure to obtain the containment helper's terminal code is unverified.
        $workerStopVerified = $false
        $result = Invoke-PitPython -Arguments @('-m','backend.app.tasks.data_update_center','--run-id',$RunId)
        $workerExit = $result.ExitCode
        $receipt.worker_exit_code = $workerExit
        $workerStopVerified = $workerExit -ge 0 -and $workerExit -le 255 -and $workerExit -ne 126
        if (-not $workerStopVerified) { throw 'Owned worker termination is unverified; retain maintenance.' }
        $observed = Invoke-PitReadOnlyCheck -AfterWorker
        $receipt.request_status = $observed.status
        if ($workerExit -ne 0 -or $observed.status -ne 'completed' -or $observed.report_date -ne $receipt.report_date) { throw 'Exact PIT request did not complete.' }
        $receipt.status = 'completed'
        $completed = $true
    }
} catch {
    $receipt.status = 'failed'
    $receipt.failure_type = $_.Exception.GetType().Name
    # Detailed provider messages can contain secrets. The data-center request
    # retains its own bounded error receipt; the host emits only the failure type.
} finally {
    if ($null -ne $claim -and -not $workerStopVerified) {
        $receipt.recovery_blocked = 'owned_worker_termination_unverified'
        $receipt.status = 'failed'
        $completed = $false
    } elseif ($null -ne $claim) {
        try {
            Assert-PitOwner
            $keepalive = Test-KeepaliveProcessRunning -Entries @($drainState.KeepaliveEntries)
            if ($drainState.ApiWasDrained -and -not $keepalive.Running -and $null -eq $recoveryLock) {
                $recoveryLock = Acquire-KeepaliveRecoveryLock
            }
            Leave-PitMaintenance
            if ($drainState.ApiWasDrained) {
                Start-CoreApiRecovery -KeepaliveState $keepalive -RuntimePython $runtimePython -RuntimeControl $runtimeControl -RecoveryLockHeld ($null -ne $recoveryLock) -ApiScriptName $drainState.ApiScriptName
                $receipt.api_restored = $true
            }
        } catch {
            $receipt.recovery_failure_type = $_.Exception.GetType().Name
            $receipt.status = 'failed'
            $completed = $false
        }
    }
    if ($null -ne $recoveryLock) { $recoveryLock.Dispose() }
    [Environment]::SetEnvironmentVariable('MOSS_DATA_UPDATE_PIT_MAINTENANCE_OWNER_TOKEN',$originalOwnerEnv,'Process')
    $receipt.lease_released = $null -eq $claim
    $receipt.finished_at = [DateTime]::UtcNow.ToString('o')
    if ($null -ne $receiptStream) {
        try {
            $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($receipt | ConvertTo-Json -Depth 6))
            $receiptStream.Write($bytes,0,$bytes.Length)
            $receiptStream.Flush($true)
        } catch { $receipt.status='failed';$receipt.receipt_write_failed=$true;$completed=$false }
        finally { $receiptStream.Dispose() }
    }
}
$receipt | ConvertTo-Json -Depth 6
if (-not $completed) { exit 1 }
exit 0
