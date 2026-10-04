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
    $hostLogPath = "G:\MOSS-stock-recovery\20260929\scoped-recovery-host.log"
    Start-Transcript -Path $hostLogPath -Append -Force | Out-Null
}
if ($PublicationOnly) {
    throw "PublicationOnly is not supported by the fixed-date 2026-09-28 scoped recovery wrapper."
}

function Resolve-VendorSourceIp {
    $networkCandidates = @(Get-NetIPConfiguration | Where-Object {
        $_.NetAdapter.HardwareInterface -and
        $_.NetAdapter.Status -eq "Up" -and
        $_.IPv4DefaultGateway
    } | Sort-Object @{ Expression = { $_.NetIPv4Interface.InterfaceMetric } }, InterfaceIndex)

    foreach ($candidate in $networkCandidates) {
        $addresses = @(Get-NetIPAddress -InterfaceIndex $candidate.InterfaceIndex -AddressFamily IPv4 |
            Where-Object {
                $_.AddressState -eq "Preferred" -and
                -not $_.SkipAsSource -and
                $_.IPAddress -notlike "169.254.*" -and
                $_.IPAddress -ne "127.0.0.1"
            } | Sort-Object IPAddress)
        if ($addresses.Count -gt 0) {
            return [pscustomobject]@{
                Address = [string]$addresses[0].IPAddress
                Interface = [string]$candidate.InterfaceAlias
            }
        }
    }

    throw "No active physical IPv4 adapter with a default gateway; stock refresh was not started."
}

function Get-ProcessSnapshot {
    param(
        [switch]$IncludeIncomplete
    )

    try {
        $processes = @(Get-CimInstance Win32_Process -ErrorAction Stop)
        if ($IncludeIncomplete) {
            return @($processes | Where-Object { $null -ne $_.ProcessId })
        }
        return @($processes | Where-Object {
            $null -ne $_.ProcessId -and $_.Name -and $_.CommandLine
        })
    } catch {
        throw "Could not inspect the Windows process table; API drain refused: $($_.Exception.Message)"
    }
}

function Get-ApiPortListeners {
    try {
        # A filtered Get-NetTCPConnection call raises when the port has no
        # matches under Windows PowerShell 5.1. Query first and filter locally
        # so a closed port is represented by an empty set, not a false error.
        return @(Get-NetTCPConnection -ErrorAction Stop | Where-Object {
            $_.State -eq "Listen" -and $_.LocalPort -eq 7888
        })
    } catch {
        throw "Could not inspect TCP port 7888; API drain refused: $($_.Exception.Message)"
    }
}

function Test-RepositoryCommand {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process
    )

    $commandLine = [string]$Process.CommandLine
    if ([string]::IsNullOrWhiteSpace($commandLine)) { return $false }
    $normalizedCommand = $commandLine.Replace("/", "\")
    $normalizedRoot = $repoRoot.TrimEnd("\", "/").Replace("/", "\")
    $rootPattern = '(?:^|[\s"])' + [regex]::Escape($normalizedRoot) + '(?=[\\\s"]|$)'
    return [regex]::IsMatch($normalizedCommand, $rootPattern, [Text.RegularExpressions.RegexOptions]::IgnoreCase)
}

function Test-CommandUsesRepositoryScriptEntrypoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandLine,
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    if ([string]::IsNullOrWhiteSpace($CommandLine)) { return $false }
    $normalizedCommand = $CommandLine.Replace("/", "\")
    $expectedPath = (Join-Path $repoRoot $RelativePath).Replace("/", "\")
    $escapedPath = [regex]::Escape($expectedPath)
    $entrypointPattern = '(?:^|\s)-File\s+(?:"' + $escapedPath + '"|' + $escapedPath + ')(?=\s|$)'
    return [regex]::IsMatch(
        $normalizedCommand,
        $entrypointPattern,
        [Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
}

function Test-RepositoryApiEntrypointCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandLine
    )

    return (
        (Test-CommandUsesRepositoryScriptEntrypoint -CommandLine $CommandLine -RelativePath "scripts\dev-api.ps1") -or
        (Test-CommandUsesRepositoryScriptEntrypoint -CommandLine $CommandLine -RelativePath "scripts\dev-agent-api.ps1")
    )
}

function Convert-ProcessIdentityValue {
    param(
        [Parameter(Mandatory = $false)]
        [object]$Value
    )

    if ($null -eq $Value) { return "" }
    if ($Value -is [DateTime]) {
        return $Value.ToUniversalTime().ToString("o", [Globalization.CultureInfo]::InvariantCulture)
    }
    return ([string]$Value).Trim()
}

function Get-ProcessIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process
    )

    $creationDate = Convert-ProcessIdentityValue -Value $Process.CreationDate
    $executablePath = Convert-ProcessIdentityValue -Value $Process.ExecutablePath
    $commandLine = Convert-ProcessIdentityValue -Value $Process.CommandLine
    if ($null -eq $Process.ParentProcessId -or
        [string]::IsNullOrWhiteSpace($creationDate) -or
        [string]::IsNullOrWhiteSpace($executablePath) -or
        [string]::IsNullOrWhiteSpace($commandLine)) {
        throw "API process identity is incomplete for PID $($Process.ProcessId); drain refused."
    }
    return [pscustomobject]@{
        ProcessId = [int]$Process.ProcessId
        ParentProcessId = [int]$Process.ParentProcessId
        CreationDate = $creationDate
        ExecutablePath = $executablePath
        CommandLine = $commandLine
    }
}

function Get-ProcessIdentityDifferences {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Expected,
        [Parameter(Mandatory = $true)]
        [object]$Actual
    )

    $differences = @()
    if ([int]$Expected.ProcessId -ne [int]$Actual.ProcessId) { $differences += "ProcessId" }
    if ([int]$Expected.ParentProcessId -ne [int]$Actual.ParentProcessId) { $differences += "ParentProcessId" }
    if (-not [string]::Equals(
        [string]$Expected.CreationDate,
        [string]$Actual.CreationDate,
        [StringComparison]::Ordinal
    )) { $differences += "CreationDate" }
    if (-not [string]::Equals(
        [string]$Expected.ExecutablePath,
        [string]$Actual.ExecutablePath,
        [StringComparison]::OrdinalIgnoreCase
    )) { $differences += "ExecutablePath" }
    if (-not [string]::Equals(
        [string]$Expected.CommandLine,
        [string]$Actual.CommandLine,
        [StringComparison]::Ordinal
    )) { $differences += "CommandLine" }
    return @($differences)
}

function Test-DirectRepoVenvPython {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process
    )

    $name = [IO.Path]::GetFileName([string]$Process.Name)
    $executablePath = Convert-ProcessIdentityValue -Value $Process.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($executablePath)) { return $false }
    $venvScripts = (Join-Path $repoRoot ".venv\Scripts\").TrimEnd("\", "/")
    $executableDirectory = [IO.Path]::GetDirectoryName($executablePath).TrimEnd("\", "/")
    return (
        [string]::Equals($executableDirectory, $venvScripts, [StringComparison]::OrdinalIgnoreCase) -and
        $name -match '(?i)^(?:python|pythonw)(?:\.exe)?$'
    )
}

function Test-ApprovedWindowsWrapperExecutable {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process
    )

    $name = [IO.Path]::GetFileName([string]$Process.Name)
    $executablePath = Convert-ProcessIdentityValue -Value $Process.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($executablePath) -or
        $name -notmatch '(?i)^(?:powershell|pwsh|cmd)(?:\.exe)?$') { return $false }
    $approvedWrapperPaths = @()
    $systemRoot = [Environment]::GetEnvironmentVariable("SystemRoot")
    if (-not [string]::IsNullOrWhiteSpace($systemRoot)) {
        $approvedWrapperPaths += Join-Path $systemRoot "System32\cmd.exe"
        $approvedWrapperPaths += Join-Path $systemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    }
    try {
        $pwshCommand = Get-Command pwsh -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $pwshCommand -and $pwshCommand.Source) {
            $approvedWrapperPaths += [string]$pwshCommand.Source
        }
    } catch {
    }
    return @($approvedWrapperPaths | Where-Object {
        [string]::Equals([string]$_, $executablePath, [StringComparison]::OrdinalIgnoreCase)
    }).Count -gt 0
}

function Test-ApprovedApiExecutable {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process,
        [hashtable]$ProcessesById = @{}
    )

    $name = [IO.Path]::GetFileName([string]$Process.Name)
    $executablePath = Convert-ProcessIdentityValue -Value $Process.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($executablePath)) { return $false }
    $isVenvPython = Test-DirectRepoVenvPython -Process $Process
    $isVenvRedirectedPython = $false
    $parentId = if ($null -eq $Process.ParentProcessId) { 0 } else { [int]$Process.ParentProcessId }
    if ($name -match '(?i)^(?:python|pythonw)(?:\.exe)?$' -and
        $parentId -gt 0 -and $ProcessesById.ContainsKey($parentId)) {
        $parent = $ProcessesById[$parentId]
        $isVenvRedirectedPython = (
            (Test-DirectRepoVenvPython -Process $parent) -and
            [string]::Equals(
                (Convert-ProcessIdentityValue -Value $parent.CommandLine),
                (Convert-ProcessIdentityValue -Value $Process.CommandLine),
                [StringComparison]::Ordinal
            )
        )
    }
    $isApprovedWrapper = (
        (Test-ApprovedWindowsWrapperExecutable -Process $Process) -and
        (Test-RepositoryApiEntrypointCommand -CommandLine ([string]$Process.CommandLine))
    )
    return ($isVenvPython -or $isVenvRedirectedPython -or $isApprovedWrapper)
}

function Test-ApiListenerIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process,
        [hashtable]$ProcessesById = @{}
    )

    if (-not (Test-RepositoryCommand -Process $Process)) { return $false }
    $commandLine = [string]$Process.CommandLine
    return (
        $commandLine -match '(?i)backend(?:[\\/.])app(?:[\\/.])main:app\b' -and
        $commandLine -match '(?i)(^|\s)--port\s+7888(?:\s|$)' -and
        (Test-ApprovedApiExecutable -Process $Process -ProcessesById $ProcessesById)
    )
}

function Test-ApiWrapperIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process,
        [hashtable]$ProcessesById = @{}
    )

    if (-not (Test-RepositoryCommand -Process $Process) -or
        -not (Test-ApprovedApiExecutable -Process $Process -ProcessesById $ProcessesById)) { return $false }
    $commandLine = [string]$Process.CommandLine
    $apiCommand = $commandLine -match '(?i)(backend(?:[\\/.])app(?:[\\/.])main:app|uvicorn|dev-api|dev-agent-api)'
    $runtimeControlCommand = $commandLine -match '(?i)dev_runtime_control\.py'
    return ($apiCommand -or $runtimeControlCommand)
}

function Test-ApiWrapperSeedIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process,
        [hashtable]$ProcessesById = @{}
    )

    if (-not (Test-RepositoryCommand -Process $Process) -or
        -not (Test-ApprovedApiExecutable -Process $Process -ProcessesById $ProcessesById)) { return $false }
    return (
        [string]$Process.Name -match '(?i)^(?:powershell|pwsh)(?:\.exe)?$' -and
        (Test-RepositoryApiEntrypointCommand -CommandLine ([string]$Process.CommandLine))
    )
}

function Get-VerifiedKeepaliveEntries {
    param(
        [object[]]$Processes = @()
    )

    if ($Processes.Count -eq 0) { $Processes = @(Get-ProcessSnapshot) }
    return @($Processes | Where-Object {
        (Test-RepositoryCommand -Process $_) -and
        (Test-ApprovedWindowsWrapperExecutable -Process $_) -and
        (Test-CommandUsesRepositoryScriptEntrypoint -CommandLine ([string]$_.CommandLine) -RelativePath "scripts\dev-keepalive.ps1")
    } | Group-Object ProcessId | ForEach-Object {
        $keepaliveProcess = $_.Group | Select-Object -First 1
        [pscustomobject]@{
            Process = $keepaliveProcess
            Identity = Get-ProcessIdentity -Process $keepaliveProcess
        }
    })
}

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

function Wait-ApiProcessTreeStopped {
    param(
        [Parameter(Mandatory = $true)]
        [int[]]$ProcessIds,
        [int]$TimeoutSeconds = 30
    )

    $expectedIds = @($ProcessIds | Select-Object -Unique)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        # Use the raw process table here. CommandLine can become unavailable
        # during teardown; filtering it would falsely certify a live PID as
        # stopped.
        $live = @(Get-ProcessSnapshot -IncludeIncomplete | Where-Object { $expectedIds -contains [int]$_.ProcessId })
        $listeners = @(Get-ApiPortListeners)
        if ($live.Count -eq 0 -and $listeners.Count -eq 0) { return }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    $liveIds = @($live | Select-Object -ExpandProperty ProcessId)
    $portIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    throw ("API drain verification timed out; live_process_ids={0}; port_7888_listener_ids={1}" -f
        (($liveIds -join ",")), (($portIds -join ",")))
}

function Initialize-NativeProcessApi {
    if ($null -ne ("MossDailyRefreshNativeProcessV1" -as [type])) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

public static class MossDailyRefreshNativeProcessV1
{
    private const uint PROCESS_TERMINATE = 0x0001;
    private const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint desiredAccess, bool inheritHandle, uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetProcessTimes(
        IntPtr process,
        out System.Runtime.InteropServices.ComTypes.FILETIME creation,
        out System.Runtime.InteropServices.ComTypes.FILETIME exit,
        out System.Runtime.InteropServices.ComTypes.FILETIME kernel,
        out System.Runtime.InteropServices.ComTypes.FILETIME user);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool QueryFullProcessImageName(
        IntPtr process, int flags, StringBuilder imagePath, ref int size);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool TerminateProcess(IntPtr process, uint exitCode);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    private static long FileTimeTicks(System.Runtime.InteropServices.ComTypes.FILETIME value)
    {
        long raw = ((long)value.dwHighDateTime << 32) | (uint)value.dwLowDateTime;
        return DateTime.FromFileTimeUtc(raw).Ticks;
    }

    public static int TerminateVerified(
        uint processId, long expectedCreationUtcTicks, string expectedExecutablePath)
    {
        IntPtr handle = OpenProcess(
            PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION, false, processId);
        if (handle == IntPtr.Zero)
            throw new Win32Exception(Marshal.GetLastWin32Error(), "OpenProcess failed");
        try
        {
            System.Runtime.InteropServices.ComTypes.FILETIME creation, exit, kernel, user;
            if (!GetProcessTimes(handle, out creation, out exit, out kernel, out user))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "GetProcessTimes failed");
            long actualCreationUtcTicks = FileTimeTicks(creation);
            if (Math.Abs(actualCreationUtcTicks - expectedCreationUtcTicks) > 10L)
                throw new InvalidOperationException("process creation time changed after identity verification");

            var imagePath = new StringBuilder(32768);
            int imagePathLength = imagePath.Capacity;
            if (!QueryFullProcessImageName(handle, 0, imagePath, ref imagePathLength))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "QueryFullProcessImageName failed");
            string actualPath = Path.GetFullPath(imagePath.ToString());
            string expectedPath = Path.GetFullPath(expectedExecutablePath);
            if (!String.Equals(actualPath, expectedPath, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("process executable changed after identity verification");

            if (!TerminateProcess(handle, 1U))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "TerminateProcess failed");
            return 0;
        }
        finally
        {
            CloseHandle(handle);
        }
    }
}
'@
}

function Terminate-VerifiedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process
    )

    $processId = [int]$Process.ProcessId
    $creationDate = $Process.CreationDate
    if ($creationDate -isnot [DateTime]) {
        try {
            $creationDate = [DateTime]::Parse(
                [string]$creationDate,
                [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::RoundtripKind
            )
        } catch {
            throw "Could not parse creation time for PID $processId; termination refused."
        }
    }
    $executablePath = Convert-ProcessIdentityValue -Value $Process.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($executablePath)) {
        throw "Executable path is unavailable for PID $processId; termination refused."
    }
    try {
        Initialize-NativeProcessApi
        $returnValue = [MossDailyRefreshNativeProcessV1]::TerminateVerified(
            [uint32]$processId,
            $creationDate.ToUniversalTime().Ticks,
            $executablePath
        )
        if ([int]$returnValue -ne 0) {
            throw "native termination returned $returnValue"
        }
    } catch {
        throw "Handle-bound process termination failed for PID $processId`: $($_.Exception.Message)"
    }
}

function Stop-ApiProcessTree {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Tree
    )

    $processEntries = @($Tree.Processes)
    if ($processEntries.Count -eq 0) { return }
    Write-Host ("Stopping repository API process tree: {0}" -f (($processEntries | ForEach-Object { $_.Process.ProcessId }) -join ","))

    # Preflight every captured identity before stopping any process. A PID can
    # be reused between discovery and the writer, and a wrapper can be replaced
    # while the maintenance lease is held. Both cases fail closed.
    $preflightById = @{}
    foreach ($current in @(Get-ProcessSnapshot)) {
        $preflightById[[int]$current.ProcessId] = $current
    }
    foreach ($entry in $processEntries) {
        $processId = [int]$entry.Process.ProcessId
        if (-not $preflightById.ContainsKey($processId)) {
            throw "Captured API process PID $processId exited before identity verification; API drain refused."
        }
        $actualIdentity = Get-ProcessIdentity -Process $preflightById[$processId]
        $differences = @(Get-ProcessIdentityDifferences -Expected $entry.Identity -Actual $actualIdentity)
        if ($differences.Count -gt 0) {
            throw ("Captured API process PID {0} identity changed before stop ({1}); API drain refused." -f
                $processId, ($differences -join ","))
        }
    }

    $stopFailures = @()
    $stoppedProcessIds = @()
    foreach ($entry in $processEntries) {
        $processId = [int]$entry.Process.ProcessId
        # Re-read the identity directly before each CIM termination call; the
        # preflight above protects the tree as a whole, while this check closes
        # the per-PID reuse window during the stop loop.
        $currentById = @{}
        foreach ($current in @(Get-ProcessSnapshot)) {
            $currentById[[int]$current.ProcessId] = $current
        }
        if (-not $currentById.ContainsKey($processId)) {
            if ($stoppedProcessIds.Count -gt 0) {
                Write-Host "Captured API process PID $processId exited after an ancestor was stopped."
                continue
            }
            throw "Captured API process PID $processId disappeared before stop; API drain refused."
        }
        $actualIdentity = Get-ProcessIdentity -Process $currentById[$processId]
        $differences = @(Get-ProcessIdentityDifferences -Expected $entry.Identity -Actual $actualIdentity)
        if ($differences.Count -gt 0) {
            throw ("Captured API process PID {0} identity changed before stop ({1}); API drain refused." -f
                $processId, ($differences -join ","))
        }
        try {
            # Stop ancestors first so a wrapper cannot restart the API while its
            # listener process is being drained. Termination errors are fatal.
            Terminate-VerifiedProcess -Process $currentById[$processId]
            $stoppedProcessIds += $processId
        } catch {
            $stopFailures += ("PID {0}: {1}" -f $processId, $_.Exception.Message)
        }
    }
    if ($stopFailures.Count -gt 0) {
        throw ("Could not stop every repository API process; {0}" -f ($stopFailures -join "; "))
    }
    Wait-ApiProcessTreeStopped -ProcessIds @($processEntries | ForEach-Object { $_.Process.ProcessId })
}

function Drain-ApiProcessTrees {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InitialTree,
        [Parameter(Mandatory = $true)]
        [object]$State,
        [int]$TimeoutSeconds = 60,
        [int]$QuietMilliseconds = 2000
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $currentTree = $InitialTree
    $apiWasDrained = $false
    $apiScriptName = $null
    $quietSince = $null
    $keepaliveById = @{}
    while ((Get-Date) -lt $deadline) {
        foreach ($entry in @($currentTree.KeepaliveEntries)) {
            $keepaliveById[[int]$entry.Process.ProcessId] = $entry
        }
        $State.KeepaliveEntries = @($keepaliveById.Values)
        $currentProcesses = @($currentTree.Processes)
        if ($currentProcesses.Count -gt 0) {
            $apiWasDrained = $true
            if ([string]::IsNullOrWhiteSpace($apiScriptName)) {
                $apiScriptName = [string]$currentTree.ApiScriptName
            } elseif (-not [string]::Equals(
                $apiScriptName,
                [string]$currentTree.ApiScriptName,
                [StringComparison]::OrdinalIgnoreCase
            )) {
                throw "API entrypoint changed while maintenance drain was active; writer was not started."
            }
            # Update the caller-visible state before termination. If a later
            # quiet-window check fails, finally still knows recovery is needed.
            $State.ApiWasDrained = $true
            $State.ApiScriptName = $apiScriptName
            Stop-ApiProcessTree -Tree $currentTree
            $quietSince = $null
        } elseif ($null -eq $quietSince) {
            $quietSince = Get-Date
        } elseif (((Get-Date) - $quietSince).TotalMilliseconds -ge $QuietMilliseconds) {
            return $State
        }
        Start-Sleep -Milliseconds 250
        $currentTree = Get-ApiProcessTree
    }
    throw "API drain did not remain quiet for ${QuietMilliseconds}ms within ${TimeoutSeconds}s; writer was not started."
}

function Test-KeepaliveProcessRunning {
    param(
        [object[]]$Entries = @()
    )

    $result = [pscustomobject]@{
        Running = $false
        Missing = $false
        IdentityChanged = $false
    }
    if ($Entries.Count -eq 0) { return $result }
    $live = @{}
    foreach ($process in @(Get-ProcessSnapshot)) {
        $live[[int]$process.ProcessId] = $process
    }
    foreach ($entry in $Entries) {
        $processId = [int]$entry.Process.ProcessId
        if (-not $live.ContainsKey($processId)) {
            $result.Missing = $true
            continue
        }
        try {
            $actualIdentity = Get-ProcessIdentity -Process $live[$processId]
        } catch {
            $result.IdentityChanged = $true
            continue
        }
        $differences = @(Get-ProcessIdentityDifferences -Expected $entry.Identity -Actual $actualIdentity)
        if ($differences.Count -gt 0) {
            $result.IdentityChanged = $true
            continue
        }
        $result.Running = $true
    }
    return $result
}

function Acquire-KeepaliveRecoveryLock {
    $lockDirectory = Join-Path $repoRoot "tmp-governance\runtime-clean\logs"
    [IO.Directory]::CreateDirectory($lockDirectory) | Out-Null
    $lockPath = Join-Path $lockDirectory "dev-keepalive.instance.lock"
    try {
        return [IO.File]::Open(
            $lockPath,
            [IO.FileMode]::OpenOrCreate,
            [IO.FileAccess]::ReadWrite,
            [IO.FileShare]::None
        )
    } catch {
        throw "Could not claim the dev keepalive recovery lock: $($_.Exception.Message)"
    }
}

function Wait-CoreApiHealth {
    param(
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ""
    do {
        try {
            $health = Invoke-WebRequest -Uri "http://127.0.0.1:7888/health" -UseBasicParsing -TimeoutSec 3
            if ($health.StatusCode -ge 200 -and $health.StatusCode -lt 300) {
                try {
                    $ready = Invoke-WebRequest -Uri "http://127.0.0.1:7888/health/ready" -UseBasicParsing -TimeoutSec 3
                    if ($ready.StatusCode -ge 200 -and $ready.StatusCode -lt 300) { return }
                    $lastError = "ready returned HTTP $($ready.StatusCode)"
                } catch {
                    $lastError = "ready: $($_.Exception.Message)"
                }
            } else {
                $lastError = "health returned HTTP $($health.StatusCode)"
            }
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    if ([string]::IsNullOrWhiteSpace($lastError)) { $lastError = "no successful health response" }
    throw "Core API health recovery timed out: $lastError"
}

function Start-CoreApiRecovery {
    param(
        [Parameter(Mandatory = $true)]
        [object]$KeepaliveState,
        [Parameter(Mandatory = $true)]
        [string]$RuntimePython,
        [Parameter(Mandatory = $true)]
        [string]$RuntimeControl,
        [Parameter(Mandatory = $true)]
        [bool]$RecoveryLockHeld,
        [Parameter(Mandatory = $true)]
        [ValidateSet("dev-api.ps1", "dev-agent-api.ps1")]
        [string]$ApiScriptName
    )

    # A live keepalive owns service recovery. Waiting here avoids racing it
    # with a second dev-up/dev-api recovery actor.
    if ($KeepaliveState.Running) {
        Write-Host "Waiting for the existing dev keepalive to restore core API health."
        Wait-CoreApiHealth
        return
    }
    if (-not $RecoveryLockHeld) {
        throw "No verified dev keepalive owns recovery and the keepalive recovery lock is unavailable; refusing a second recovery actor."
    }

    $existingTree = Get-ApiProcessTree
    if (@($existingTree.Processes).Count -gt 0) {
        # A failed/partial drain can leave an old wrapper alive briefly after
        # its listener has already exited. While holding the recovery lock,
        # reuse the tree if it becomes healthy; if the exact tree disappears,
        # continue into the owned launch below instead of waiting to timeout
        # with the service still down.
        $existingDeadline = (Get-Date).AddSeconds(45)
        $existingLastError = "existing repository API tree is not healthy"
        do {
            try {
                $health = Invoke-WebRequest -Uri "http://127.0.0.1:7888/health" -UseBasicParsing -TimeoutSec 3
                if ($health.StatusCode -ge 200 -and $health.StatusCode -lt 300) {
                    $ready = Invoke-WebRequest -Uri "http://127.0.0.1:7888/health/ready" -UseBasicParsing -TimeoutSec 3
                    if ($ready.StatusCode -ge 200 -and $ready.StatusCode -lt 300) { return }
                    $existingLastError = "ready returned HTTP $($ready.StatusCode)"
                } else {
                    $existingLastError = "health returned HTTP $($health.StatusCode)"
                }
            } catch {
                $existingLastError = $_.Exception.Message
            }
            Start-Sleep -Milliseconds 500
            $existingTree = Get-ApiProcessTree
            if (@($existingTree.Processes).Count -eq 0) { break }
        } while ((Get-Date) -lt $existingDeadline)
        if (@($existingTree.Processes).Count -gt 0) {
            throw "Existing repository API tree remained unhealthy during owned recovery: $existingLastError"
        }
    }
    $powershellExe = (Get-Command powershell -ErrorAction Stop).Source
    $apiScript = Join-Path $repoRoot ("scripts\" + $ApiScriptName)
    if (-not (Test-Path -LiteralPath $apiScript -PathType Leaf)) {
        throw "Core API recovery script is missing: $apiScript"
    }
    $recoveryLogDirectory = Join-Path $repoRoot "tmp-governance\runtime-clean\logs"
    [IO.Directory]::CreateDirectory($recoveryLogDirectory) | Out-Null
    $stdoutPath = Join-Path $recoveryLogDirectory "daily-refresh-api-recovery.out.log"
    $stderrPath = Join-Path $recoveryLogDirectory "daily-refresh-api-recovery.err.log"
    Remove-Item -LiteralPath $stdoutPath,$stderrPath -Force -ErrorAction SilentlyContinue
    Write-Host "Starting core API recovery (health/readiness only)."
    $apiArguments = @($powershellExe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $apiScript)
    if ($ApiScriptName -eq "dev-api.ps1") {
        $apiArguments += "-SkipStartupStorageMigrations"
    }
    $runtimePayload = @{
        argv = $apiArguments
        cwd = $repoRoot
    } | ConvertTo-Json -Compress
    $runtimeCommand = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($runtimePayload))
    # The caller continues holding dev-keepalive.instance.lock until health is
    # restored. That shared lock, rather than runtime_control's short spawn
    # lock, keeps the host and keepalive from becoming concurrent recoverers.
    Start-Process -FilePath $RuntimePython -ArgumentList @(
        $RuntimeControl, "--repo-root", $repoRoot, "run", "--command-base64", $runtimeCommand
    ) -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath | Out-Null
    Wait-CoreApiHealth
}

function Format-FailureMessage {
    param(
        [string]$PrimaryFailure,
        [string[]]$RecoveryFailures = @()
    )

    $message = if ([string]::IsNullOrWhiteSpace($PrimaryFailure)) {
        "Market refresh failed during runtime preparation."
    } else {
        "Market refresh primary failure: $PrimaryFailure"
    }
    if ($RecoveryFailures.Count -gt 0) {
        $message += "`nMarket refresh recovery failure(s): " + ($RecoveryFailures -join "; ")
    }
    return $message
}

function Read-MaintenanceMarker {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        $state = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json
        if ($null -ne $state -and $state.state -eq "launch_blocked" -and
            -not [string]::IsNullOrWhiteSpace([string]$state.owner_token)) {
            return $state
        }
    } catch {
    }
    return $null
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

    & "G:\MOSS-stock-recovery\20260929\run_scoped_recovery.ps1" -VendorSourceIp $vendorAddress -PythonExe $runtimePython
    $refreshExitCode = [int]$LASTEXITCODE
    if ($refreshExitCode -ne 0) {
        $primaryFailure = "run_scoped_recovery.ps1 exited with code $refreshExitCode."
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
