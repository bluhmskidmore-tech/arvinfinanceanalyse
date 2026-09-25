param(
  [string]$RepoRoot = "",
  [switch]$Apply,
  [switch]$IncludeScreenshots,
  [int]$RetentionDays = 7,
  [int]$ScreenshotRetentionDays = 14
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = Split-Path -Parent $PSScriptRoot
}

$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path.TrimEnd("\", "/")
$repoRootPrefix = $repoRootPath + [System.IO.Path]::DirectorySeparatorChar
$cutoff = (Get-Date).AddDays(-1 * $RetentionDays)
$screenshotCutoff = (Get-Date).AddDays(-1 * $ScreenshotRetentionDays)

$protectedSegments = @(
  ".git",
  ".gitnexus",
  ".omx",
  ".venv",
  "data",
  "data_input",
  "node_modules",
  "tmp-governance"
)

$protectedExtensions = @(
  ".csv",
  ".db",
  ".duckdb",
  ".jsonl",
  ".parquet",
  ".pkl",
  ".sqlite",
  ".sqlite3",
  ".wal",
  ".xls",
  ".xlsx"
)

$candidateByPath = @{}
$skippedProtected = New-Object System.Collections.Generic.List[object]

function Get-RelativePathText {
  param([Parameter(Mandatory = $true)][string]$FullPath)

  $trimmed = $FullPath.TrimEnd("\", "/")
  if ($trimmed.Equals($repoRootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    return "."
  }
  if (-not $trimmed.StartsWith($repoRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Candidate path escapes repository root: $FullPath"
  }
  return $trimmed.Substring($repoRootPrefix.Length)
}

function Test-ProtectedPath {
  param([Parameter(Mandatory = $true)][string]$FullPath)

  $relative = Get-RelativePathText -FullPath $FullPath
  if ($relative -eq ".") {
    return $false
  }
  $segments = $relative -split "[\\/]+"
  $firstSegment = $segments[0]
  if (
    $firstSegment -in @(".codex-tmp", "test_output", ".pytest-basetemp") -or
    $firstSegment -like ".pytest-tmp*" -or
    ($firstSegment -eq "frontend" -and $segments.Count -gt 1 -and $segments[1] -eq "test-results")
  ) {
    return $true
  }
  foreach ($segment in $segments) {
    if ($protectedSegments -contains $segment) {
      return $true
    }
  }
  return $false
}

function Test-IsReparsePoint {
  param([Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item)

  return (($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Test-ProtectedEvidenceName {
  param([Parameter(Mandatory = $true)][string]$Name)

  return (
    $Name -match "(?i)(^|[._-])(manifest|audit|evidence|acceptance|golden|release|review)([._-]|$)" -or
    $Name -match "(?i)^raw-results$"
  )
}

function Get-TreeSafetyIssue {
  param(
    [Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item,
    [Parameter(Mandatory = $true)][datetime]$Cutoff
  )

  $pending = New-Object System.Collections.Generic.Stack[string]
  $pending.Push($Item.FullName)
  while ($pending.Count -gt 0) {
    $currentPath = $pending.Pop()
    try {
      $current = Get-Item -LiteralPath $currentPath -Force -ErrorAction Stop
    }
    catch {
      return "unable to inspect candidate tree"
    }

    if (Test-IsReparsePoint -Item $current) {
      return "reparse point in candidate tree"
    }
    if (Test-ProtectedPath -FullPath $current.FullName) {
      return "protected path in candidate tree"
    }
    if (Test-ProtectedEvidenceName -Name $current.Name) {
      return "protected evidence name in candidate tree"
    }
    if ($current.LastWriteTime -gt $Cutoff) {
      return "recent descendant in candidate tree"
    }

    if (-not $current.PSIsContainer) {
      if ($protectedExtensions -contains $current.Extension.ToLowerInvariant()) {
        return "protected extension in candidate tree"
      }
      continue
    }

    try {
      $children = @(Get-ChildItem -LiteralPath $current.FullName -Force -ErrorAction Stop)
    }
    catch {
      return "unable to inspect candidate tree"
    }
    foreach ($child in $children) {
      if (Test-IsReparsePoint -Item $child) {
        return "reparse point in candidate tree"
      }
      $pending.Push($child.FullName)
    }
  }

  return $null
}

function Add-CleanupCandidate {
  param(
    [Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item,
    [Parameter(Mandatory = $true)][string]$Reason,
    [Parameter(Mandatory = $true)][datetime]$Cutoff
  )

  if (Test-IsReparsePoint -Item $Item) {
    $skippedProtected.Add([pscustomobject]@{ Path = Get-RelativePathText -FullPath $Item.FullName; Reason = "reparse point" }) | Out-Null
    return
  }

  $fullPath = (Resolve-Path -LiteralPath $Item.FullName).Path.TrimEnd("\", "/")
  $relativePath = Get-RelativePathText -FullPath $fullPath
  if (Test-ProtectedPath -FullPath $fullPath) {
    $skippedProtected.Add([pscustomobject]@{ Path = $relativePath; Reason = $Reason }) | Out-Null
    return
  }

  $safetyIssue = Get-TreeSafetyIssue -Item $Item -Cutoff $Cutoff
  if ($null -ne $safetyIssue) {
    $skippedProtected.Add([pscustomobject]@{ Path = $relativePath; Reason = $safetyIssue }) | Out-Null
    return
  }

  if (-not $candidateByPath.ContainsKey($fullPath)) {
    $candidateByPath[$fullPath] = [pscustomobject]@{
      FullPath = $fullPath
      Path = $relativePath
      Reason = $Reason
      LastWriteTime = $Item.LastWriteTime
      IsDirectory = $Item.PSIsContainer
      Cutoff = $Cutoff
    }
  }
}

function Add-DirectoryIfPresent {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Reason
  )

  if (Test-Path -LiteralPath $Path -PathType Container) {
    Add-CleanupCandidate -Item (Get-Item -LiteralPath $Path -Force) -Reason $Reason -Cutoff $cutoff
  }
}

function Add-PythonBytecodeCachesSafely {
  $pending = New-Object System.Collections.Generic.Stack[string]
  $pending.Push($repoRootPath)
  while ($pending.Count -gt 0) {
    $currentPath = $pending.Pop()
    try {
      $directories = @(Get-ChildItem -LiteralPath $currentPath -Directory -Force -ErrorAction Stop)
    }
    catch {
      $skippedProtected.Add([pscustomobject]@{
        Path = Get-RelativePathText -FullPath $currentPath
        Reason = "unable to inspect directory tree"
      }) | Out-Null
      continue
    }

    foreach ($directory in $directories) {
      if (Test-IsReparsePoint -Item $directory) { continue }
      if (Test-ProtectedPath -FullPath $directory.FullName) { continue }
      if (Test-ProtectedEvidenceName -Name $directory.Name) { continue }
      if ($directory.Name -eq "__pycache__") {
        Add-CleanupCandidate -Item $directory -Reason "Python bytecode cache" -Cutoff $cutoff
        continue
      }
      $pending.Push($directory.FullName)
    }
  }
}

function Add-DirectFilesByPattern {
  param(
    [Parameter(Mandatory = $true)][string]$ParentPath,
    [Parameter(Mandatory = $true)][string]$Pattern,
    [Parameter(Mandatory = $true)][string]$Reason,
    [Parameter(Mandatory = $true)][datetime]$Cutoff
  )

  if (-not (Test-Path -LiteralPath $ParentPath -PathType Container)) {
    return
  }

  Get-ChildItem -LiteralPath $ParentPath -File -Force -Filter $Pattern -ErrorAction SilentlyContinue |
    ForEach-Object { Add-CleanupCandidate -Item $_ -Reason $Reason -Cutoff $Cutoff }
}

Add-DirectoryIfPresent -Path (Join-Path $repoRootPath ".pytest_cache") -Reason "pytest cache"
Add-DirectoryIfPresent -Path (Join-Path $repoRootPath ".ruff_cache") -Reason "ruff cache"
Add-DirectoryIfPresent -Path (Join-Path $repoRootPath ".mypy_cache") -Reason "mypy cache"
Add-DirectoryIfPresent -Path (Join-Path $repoRootPath "backend\.mypy_cache") -Reason "backend mypy cache"

Add-PythonBytecodeCachesSafely

Add-DirectFilesByPattern -ParentPath $repoRootPath -Pattern "*.log" -Reason "root log file" -Cutoff $cutoff
Add-DirectFilesByPattern -ParentPath (Join-Path $repoRootPath "frontend") -Pattern "*.log" -Reason "frontend log file" -Cutoff $cutoff

if ($IncludeScreenshots) {
  Add-DirectFilesByPattern -ParentPath $repoRootPath -Pattern "*.png" -Reason "root screenshot" -Cutoff $screenshotCutoff
  Add-DirectFilesByPattern -ParentPath (Join-Path $repoRootPath "frontend") -Pattern "*.png" -Reason "frontend screenshot" -Cutoff $screenshotCutoff
}

$mode = if ($Apply) { "APPLY" } else { "DRY-RUN" }
$candidates = @($candidateByPath.Values | Sort-Object Path)

Write-Host "$mode cleanup-dev-artifacts"
Write-Host "RepoRoot: $repoRootPath"
Write-Host "RetentionDays: $RetentionDays"
Write-Host "ScreenshotRetentionDays: $ScreenshotRetentionDays"
Write-Host "IncludeScreenshots: $($IncludeScreenshots.IsPresent)"
Write-Host "Candidates: $($candidates.Count)"
Write-Host "Skipped protected: $($skippedProtected.Count)"

foreach ($candidate in $candidates) {
  Write-Host ("{0}`t{1}`t{2}" -f $mode, $candidate.Path, $candidate.Reason)
}

if ($skippedProtected.Count -gt 0) {
  foreach ($skip in @($skippedProtected | Select-Object -First 20)) {
    Write-Host ("SKIP`t{0}`t{1}" -f $skip.Path, $skip.Reason)
  }
}

if (-not $Apply) {
  Write-Host "Dry run complete. Pass -Apply to remove listed candidates."
  exit 0
}

foreach ($candidate in $candidates) {
  if (-not (Test-Path -LiteralPath $candidate.FullPath)) {
    continue
  }

  $resolvedCandidate = (Resolve-Path -LiteralPath $candidate.FullPath).Path.TrimEnd("\", "/")
  Get-RelativePathText -FullPath $resolvedCandidate | Out-Null
  if (Test-ProtectedPath -FullPath $resolvedCandidate) {
    Write-Host ("SKIP`t{0}`tprotected at delete time" -f $candidate.Path)
    continue
  }

  $resolvedItem = Get-Item -LiteralPath $resolvedCandidate -Force
  $safetyIssue = Get-TreeSafetyIssue -Item $resolvedItem -Cutoff $candidate.Cutoff
  if ($null -ne $safetyIssue) {
    Write-Host ("SKIP {0} {1} at delete time" -f $candidate.Path, $safetyIssue)
    continue
  }

  try {
    Remove-Item -LiteralPath $resolvedCandidate -Recurse:$candidate.IsDirectory -Force -ErrorAction Stop
  }
  catch [System.UnauthorizedAccessException] {
    Write-Host ("SKIP`t{0}`tpermission denied at delete time" -f $candidate.Path)
    continue
  }
  catch [System.IO.IOException] {
    Write-Host ("SKIP`t{0}`tpath busy at delete time" -f $candidate.Path)
    continue
  }
}

Write-Host "Cleanup apply complete."
