# Checks every file on this drive against arc\system\CHECKSUMS.sha256.
# Started by verify.bat. Uses only what comes with Windows 10 and 11.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$list = Join-Path $PSScriptRoot 'CHECKSUMS.sha256'

if (-not (Test-Path -LiteralPath $list)) {
    Write-Host 'CHECKSUMS.sha256 is missing. Cannot check this drive.' -ForegroundColor Red
    exit 2
}

$lines = @(Get-Content -LiteralPath $list -Encoding UTF8 | Where-Object { $_.Trim() -ne '' })
$total = $lines.Count
$ok = 0
$bad = New-Object System.Collections.Generic.List[string]
$missing = New-Object System.Collections.Generic.List[string]
$i = 0

foreach ($line in $lines) {
    $i++
    $expected = $line.Substring(0, 64).ToLower()
    $rel = $line.Substring(66)
    $path = Join-Path $root ($rel -replace '/', '\')
    Write-Progress -Activity 'Checking files' -Status "$i of $total : $rel" -PercentComplete (100 * $i / $total)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $missing.Add($rel)
        continue
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
    if ($actual -eq $expected) { $ok++ } else { $bad.Add($rel) }
}
Write-Progress -Activity 'Checking files' -Completed

Write-Host ''
if ($bad.Count -eq 0 -and $missing.Count -eq 0) {
    Write-Host "ALL GOOD: $ok of $total files are intact." -ForegroundColor Green
    exit 0
}
Write-Host "PROBLEM: $ok of $total files are intact." -ForegroundColor Red
if ($bad.Count -gt 0) {
    Write-Host "Damaged ($($bad.Count)): replace these from another copy of the drive:" -ForegroundColor Red
    $bad | ForEach-Object { Write-Host "  $_" }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing ($($missing.Count)):" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  $_" }
}
exit 1
