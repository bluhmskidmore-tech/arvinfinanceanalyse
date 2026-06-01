# Extract mock data from client.ts
# Removes lines 266-1080 (orphaned/dead inline mock data) and keeps the rest intact
# Run from f:\MOSS-V3 directory:  powershell -File frontend/src/api/_cleanup_mock_extraction.ps1

$file = "f:\MOSS-V3\frontend\src\api\client.ts"
$lines = [System.IO.File]::ReadAllLines($file)

Write-Host "Original line count: $($lines.Length)"

# Keep lines 1-265 (0-indexed: 0-264) — imports, utilities, comment
# Remove lines 266-1080 (0-indexed: 265-1079) — orphaned mock data
# Keep lines 1081+ (0-indexed: 1080+) — live code (reduceLatestManualAdjustments and everything after)

$keepBefore = $lines[0..264]
$keepAfter  = $lines[1080..($lines.Length - 1)]

$newLines = $keepBefore + @("") + $keepAfter

Write-Host "New line count: $($newLines.Length)"
Write-Host "Removed $($lines.Length - $newLines.Length) lines"

# Preserve original encoding
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($file, $newLines, $utf8NoBom)

Write-Host "Done. Wrote $($newLines.Length) lines to $file"
