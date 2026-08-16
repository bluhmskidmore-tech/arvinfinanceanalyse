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
  foreach ($segment in $segments) {
    if ($protectedSegments -contains $segment) {
      return $true
    }
  }
  return $false
}

function Test-ContainsProtectedExtension {
  param([Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item)

  if (-not $Item.PSIsContainer) {
    return $protectedExtensions -contains $Item.Extension.ToLowerInvariant()
  }

  $protectedFile = Get-ChildItem -LiteralPath $Item.FullName -File -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $protectedExtensions -contains $_.Extension.ToLowerInvariant() } |
    Select-Object -First 1

  return $null -ne $protectedFile
}

function Test-AllowProtectedExtensionCleanup {
  param([Parameter(Mandatory = $true)][string]$FullPath)

  $relative = Get-RelativePathText -FullPath $FullPath
  $allowedPrefixes = @(
    ".codex-tmp\pytest-",
    ".codex-tmp/pytest-",
    ".mypy_cache\",
    ".mypy_cache/",
    ".pytest-basetemp\",
    ".pytest-basetemp/",
    "backend\.mypy_cache\",
    "backend/.mypy_cache/",
    "test_output\accounting_asset_movement\",
    "test_output/accounting_asset_movement/",
    "test_output\formal_balance_pipeline\",
    "test_output/formal_balance_pipeline/",
    "frontend\test-results\",
    "frontend/test-results/"
  )

  if (
    $relative -eq ".pytest-basetemp" -or
    $relative -eq ".mypy_cache" -or
    $relative -eq "backend\.mypy_cache" -or
    $relative -eq "backend/.mypy_cache" -or
    $relative -eq "test_output\accounting_asset_movement" -or
    $relative -eq "test_output/accounting_asset_movement" -or
    $relative -eq "test_output\formal_balance_pipeline" -or
    $relative -eq "test_output/formal_balance_pipeline" -or
    $relative -eq "frontend\test-results" -or
    $relative -eq "frontend/test-results"
  ) {
    return $true
  }

  foreach ($prefix in $allowedPrefixes) {
    if ($relative.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
      return $true
    }
  }

  return $false
}

function Test-ShouldSkipForProtectedExtension {
  param([Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item)

  return (
    (Test-ContainsProtectedExtension -Item $Item) -and
    -not (Test-AllowProtectedExtensionCleanup -FullPath $Item.FullName)
  )
}

function Add-CleanupCandidate {
  param(
    [Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item,
    [Parameter(Mandatory = $true)][string]$Reason,
    [Parameter(Mandatory = $true)][datetime]$Cutoff
  )

  $fullPath = (Resolve-Path -LiteralPath $Item.FullName).Path.TrimEnd("\", "/")
  $relativePath = Get-RelativePathText -FullPath $fullPath

  if ($Item.LastWriteTime -gt $Cutoff) {
    return
  }

  $isProtectedPath = Test-ProtectedPath -FullPath $fullPath
  if ($isProtectedPath) {
    $skippedProtected.Add([pscustomobject]@{
      Path = $relativePath
      Reason = $Reason
    }) | Out-Null
    return
  }

  $skipForProtectedExtension = Test-ShouldSkipForProtectedExtension -Item $Item
  if ($skipForProtectedExtension) {
    $skippedProtected.Add([pscustomobject]@{
      Path = $relativePath
      Reason = $Reason
    }) | Out-Null
    return
  }

  if (-not $candidateByPath.ContainsKey($fullPath)) {
    $candidateByPath[$fullPath] = [pscustomobject]@{
      FullPath = $fullPath
      Path = $relativePath
      Reason = $Reason
      LastWriteTime = $Item.LastWriteTime
      IsDirectory = $Item.PSIsContainer
    }
  }
}

function Add-DirectoryChildrenByPattern {
  param(
    [Parameter(Mandatory = $true)][string]$ParentPath,
    [Parameter(Mandatory = $true)][string[]]$NamePatterns,
    [Parameter(Mandatory = $true)][string]$Reason
  )

  if (-not (Test-Path -LiteralPath $ParentPath -PathType Container)) {
    return
  }

  Get-ChildItem -LiteralPath $ParentPath -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object {
      $name = $_.Name
      @($NamePatterns | Where-Object { $name -like $_ }).Count -gt 0
    } |
    ForEach-Object { Add-CleanupCandidate -Item $_ -Reason $Reason -Cutoff $cutoff }
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

function Add-DirectoryChildrenIfPresent {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Reason
  )

  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    return
  }

  Get-ChildItem -LiteralPath $Path -File -Force -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object { Add-CleanupCandidate -Item $_ -Reason $Reason -Cutoff $cutoff }
}

function Get-LatestTreeWriteTime {
  param([Parameter(Mandatory = $true)][string]$Path)

  $item = Get-Item -LiteralPath $Path -Force
  $latest = $item.LastWriteTime

  if (-not $item.PSIsContainer) {
    return $latest
  }

  Get-ChildItem -LiteralPath $Path -Force -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object {
      if ($_.LastWriteTime -gt $latest) {
        $latest = $_.LastWriteTime
      }
    }

  return $latest
}

function Add-DisposableTreeDirectoriesIfPresent {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Reason
  )

  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    return
  }

  $rootItem = Get-Item -LiteralPath $Path -Force
  $rootLatest = Get-LatestTreeWriteTime -Path $rootItem.FullName
  if ($rootLatest -le $cutoff) {
    Add-CleanupCandidate -Item $rootItem -Reason $Reason -Cutoff $cutoff
    return
  }

  Get-ChildItem -LiteralPath $Path -Directory -Force -Recurse -ErrorAction SilentlyContinue |
    Sort-Object { $_.FullName.Length } -Descending |
    ForEach-Object {
      $latest = Get-LatestTreeWriteTime -Path $_.FullName
      if ($latest -le $cutoff) {
        Add-CleanupCandidate -Item $_ -Reason $Reason -Cutoff $cutoff
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

Add-DirectoryChildrenByPattern `
  -ParentPath (Join-Path $repoRootPath ".codex-tmp") `
  -NamePatterns @("pytest-*", "pytest-basetemp*") `
  -Reason ".codex-tmp pytest run output"

Add-DirectoryChildrenByPattern `
  -ParentPath $repoRootPath `
  -NamePatterns @(".pytest-tmp*") `
  -Reason "legacy pytest temp directory"

Add-DirectoryChildrenByPattern `
  -ParentPath (Join-Path $repoRootPath ".pytest-basetemp") `
  -NamePatterns @("*") `
  -Reason "legacy root pytest run output"

Add-DirectoryIfPresent -Path (Join-Path $repoRootPath ".pytest-basetemp") -Reason "legacy root pytest basetemp shell"
Add-DirectoryIfPresent -Path (Join-Path $repoRootPath ".pytest_cache") -Reason "pytest cache"
Add-DirectoryIfPresent -Path (Join-Path $repoRootPath ".ruff_cache") -Reason "ruff cache"
Add-DirectoryIfPresent -Path (Join-Path $repoRootPath ".mypy_cache") -Reason "mypy cache"
Add-DirectoryIfPresent -Path (Join-Path $repoRootPath "backend\.mypy_cache") -Reason "backend mypy cache"
Add-DirectoryChildrenIfPresent -Path (Join-Path $repoRootPath "test_output\accounting_asset_movement") -Reason "test output"
Add-DisposableTreeDirectoriesIfPresent -Path (Join-Path $repoRootPath "test_output\accounting_asset_movement") -Reason "test output"
Add-DirectoryChildrenIfPresent -Path (Join-Path $repoRootPath "test_output\formal_balance_pipeline") -Reason "test output"
Add-DisposableTreeDirectoriesIfPresent -Path (Join-Path $repoRootPath "test_output\formal_balance_pipeline") -Reason "test output"
Add-DirectoryChildrenIfPresent -Path (Join-Path $repoRootPath "frontend\test-results") -Reason "frontend test output"
Add-DisposableTreeDirectoriesIfPresent -Path (Join-Path $repoRootPath "frontend\test-results") -Reason "frontend test output"

Get-ChildItem -LiteralPath $repoRootPath -Directory -Force -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
  ForEach-Object { Add-CleanupCandidate -Item $_ -Reason "Python bytecode cache" -Cutoff $cutoff }

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

  $skipForProtectedExtension = Test-ShouldSkipForProtectedExtension -Item (Get-Item -LiteralPath $resolvedCandidate -Force)
  if ($skipForProtectedExtension) {
    Write-Host ("SKIP`t{0}`tprotected at delete time" -f $candidate.Path)
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
