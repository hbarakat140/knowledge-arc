# Knowledge Arc: make a pocket copy of this library (the pocket edition) on a
# stick, a memory card or another drive. Started by
# "arc\Make a pocket copy (Windows).bat". Uses only what comes with Windows
# 10 and 11: no internet, nothing installed. Nothing on this drive is changed.
#
# The list of the pocket copy's files is arc\pocket\arc\system\CHECKSUMS.sha256
# (made when this drive was built). Each file is taken from arc\pocket if it
# is there (the pocket edition's own pages and files), otherwise from this
# drive. Every file is checked on the copy afterwards.
#
#   powershell -File make-pocket-copy.ps1 [-Target F:] [-Yes]

param([string]$Target = '', [switch]$Yes)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$rootFull = [System.IO.Path]::GetFullPath($root).TrimEnd('\')
$kit = Join-Path $root 'arc\pocket'
$list = Join-Path $kit 'arc\system\CHECKSUMS.sha256'

function GB($bytes) { '{0:N1} GB' -f ($bytes / 1e9) }

Write-Host ''
Write-Host '  MAKE A POCKET COPY'
Write-Host '  =================='
Write-Host '  The pocket edition of this library: every guide, the medical and repair'
Write-Host '  collections, a short Wikipedia and the programs, for a phone or a stick'
Write-Host '  of 32 GB or more. Nothing on this drive is changed.'
Write-Host ''

if (-not (Test-Path -LiteralPath $list -PathType Leaf)) {
    Write-Host '  This drive has no pocket copy to make (the folder arc\pocket is missing).' -ForegroundColor Red
    Write-Host '  A pocket copy is made from a copy of the library bigger than pocket.'
    exit 2
}

# The files to copy, where each comes from, and its size.
$entries = New-Object System.Collections.Generic.List[object]
foreach ($line in [System.IO.File]::ReadAllLines($list)) {
    if ($line.Length -lt 67) { continue }
    $rel = $line.Substring(66)
    $win = $rel -replace '/', '\'
    $fromKit = Join-Path $kit $win
    $src = if (Test-Path -LiteralPath $fromKit -PathType Leaf) { $fromKit } else { Join-Path $root $win }
    $entries.Add([pscustomobject]@{ Sha = $line.Substring(0, 64).ToLower(); Rel = $win; Src = $src; Size = [int64]0 })
}
$missing = @($entries | Where-Object { -not (Test-Path -LiteralPath $_.Src -PathType Leaf) })
if ($missing.Count -gt 0) {
    Write-Host "  $($missing.Count) files of the pocket copy are missing from this drive:" -ForegroundColor Red
    $missing | Select-Object -First 10 | ForEach-Object { Write-Host "    $($_.Rel)" }
    Write-Host '  Check this drive first (arc\system\verify.bat) and repair it from another copy.'
    exit 1
}
foreach ($e in $entries) { $e.Size = (Get-Item -LiteralPath $e.Src).Length }
$total = ($entries | Measure-Object -Property Size -Sum).Sum
$biggest = ($entries | Measure-Object -Property Size -Maximum).Maximum
Write-Host "  The pocket copy: $($entries.Count) files, $(GB $total)."
Write-Host ''

# Where to: a drive letter, or a folder.
if (-not $Target) {
    Write-Host '  Plug in the stick or memory card, then type its letter. Drives found:'
    foreach ($d in [System.IO.DriveInfo]::GetDrives()) {
        if (-not $d.IsReady -or $rootFull.StartsWith($d.RootDirectory.FullName.TrimEnd('\'))) { continue }
        if ($d.Name.TrimEnd('\') -eq $env:SystemDrive) { continue }   # the computer's own drive
        if ($d.DriveType -ne 'Removable' -and $d.DriveType -ne 'Fixed') { continue }
        Write-Host ("    {0}  {1,-16} {2} free of {3}, {4}" -f $d.Name.TrimEnd('\'), $d.VolumeLabel,
                    (GB $d.AvailableFreeSpace), (GB $d.TotalSize), $d.DriveFormat)
    }
    $Target = Read-Host '  Letter of the drive to copy to (for example F)'
}
$Target = $Target.Trim().Trim('"')
if (-not $Target) { Write-Host '  No drive chosen.'; exit 1 }
if ($Target -match '^[A-Za-z]:?\\?$') { $Target = $Target.Substring(0, 1).ToUpper() + ':\' }
if ($env:SystemDrive -and $Target.TrimEnd('\') -eq $env:SystemDrive) {
    Write-Host "  $Target is this computer's own drive. Choose the stick or memory card." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath $Target)) {
    if ($Target -match '^[A-Za-z]:\\$') { Write-Host "  There is no drive $Target." -ForegroundColor Red; exit 1 }
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
}
$dest = [System.IO.Path]::GetFullPath($Target).TrimEnd('\')
if ($dest -eq $rootFull -or $dest.StartsWith($rootFull + '\') -or $rootFull.StartsWith($dest + '\')) {
    Write-Host '  That is this drive (or a folder on it). Choose another drive.' -ForegroundColor Red
    exit 1
}

# FAT32 cannot hold a file of 4 GB or more (the short Wikipedia is 14 GB).
$info = New-Object System.IO.DriveInfo ([System.IO.Path]::GetPathRoot($dest + '\'))
if ($info.DriveFormat -match '^FAT' -and $biggest -ge 4294967295) {
    Write-Host "  $($info.Name) is formatted $($info.DriveFormat), which cannot hold files of 4 GB or more." -ForegroundColor Red
    Write-Host '  Format it as exFAT first. This ERASES it: in File Explorer, right-click the drive,'
    Write-Host '  Format..., File system: exFAT, Start. Then run this again.'
    exit 1
}

# Files already there with the same size are kept (a stopped copy carries on).
$todo = @($entries | Where-Object {
    $d = Join-Path $dest $_.Rel
    -not (Test-Path -LiteralPath $d -PathType Leaf) -or (Get-Item -LiteralPath $d).Length -ne $_.Size })
$need = [int64](($todo | Measure-Object -Property Size -Sum).Sum)
if ($need -gt $info.AvailableFreeSpace) {
    Write-Host "  Not enough room on $($info.Name): the copy needs $(GB $need) more, and $(GB $info.AvailableFreeSpace) is free." -ForegroundColor Red
    exit 1
}
Write-Host "  Copy $($todo.Count) files ($(GB $need)) to $dest, then check every file."
if (-not $Yes) {
    $answer = Read-Host '  Start? [Y/n]'
    if ($answer -and $answer -notmatch '^(y|yes)$') { Write-Host '  Stopped.'; exit 1 }
}
Write-Host '  Copying. This can take an hour or more; you can stop it and run it again later.'

$done = [int64]0
$i = 0
foreach ($e in $todo) {
    $i++
    Write-Progress -Activity 'Copying' -Status "$i of $($todo.Count): $($e.Rel)" -PercentComplete ([math]::Min(100, 100 * $done / [math]::Max(1, $need)))
    $d = Join-Path $dest $e.Rel
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $d)) | Out-Null
    [System.IO.File]::Copy($e.Src, $d, $true)
    $done += $e.Size
}
Write-Progress -Activity 'Copying' -Completed
$listDest = Join-Path $dest 'arc\system\CHECKSUMS.sha256'
[System.IO.Directory]::CreateDirectory((Split-Path -Parent $listDest)) | Out-Null
[System.IO.File]::Copy($list, $listDest, $true)

# Check every file on the copy; copy a damaged one once more.
$bad = New-Object System.Collections.Generic.List[string]
$i = 0
foreach ($e in $entries) {
    $i++
    Write-Progress -Activity 'Checking the copy' -Status "$i of $($entries.Count): $($e.Rel)" -PercentComplete (100 * $i / $entries.Count)
    $d = Join-Path $dest $e.Rel
    $ok = (Test-Path -LiteralPath $d -PathType Leaf) -and ((Get-FileHash -LiteralPath $d -Algorithm SHA256).Hash.ToLower() -eq $e.Sha)
    if (-not $ok) {
        [System.IO.Directory]::CreateDirectory((Split-Path -Parent $d)) | Out-Null
        [System.IO.File]::Copy($e.Src, $d, $true)
        $ok = (Get-FileHash -LiteralPath $d -Algorithm SHA256).Hash.ToLower() -eq $e.Sha
    }
    if (-not $ok) { $bad.Add($e.Rel) }
}
Write-Progress -Activity 'Checking the copy' -Completed

Write-Host ''
if ($bad.Count -eq 0) {
    Write-Host "  ALL GOOD: the pocket copy is ready, $($entries.Count) files checked." -ForegroundColor Green
    Write-Host "  On a computer, open ""1 START-HERE"" on $dest. On an Android phone, install the"
    Write-Host '  Kiwix app from arc\software\android on the copy and open the .zim files in it.'
    exit 0
}
Write-Host "  PROBLEM: $($bad.Count) files did not copy correctly:" -ForegroundColor Red
$bad | ForEach-Object { Write-Host "    $_" }
Write-Host '  The stick or card may be failing, or this drive has a damaged file: run'
Write-Host '  arc\system\verify.bat on this drive, then try again or use another stick.'
exit 1
