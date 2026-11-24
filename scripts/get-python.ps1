# Knowledge Arc: the portable Python that make-arc.bat uses when this computer
# has no Python 3.11 or newer. Nothing is installed: the Python is unpacked
# into %LOCALAPPDATA%\knowledge-arc\python-<version>, and deleting that folder
# removes it. The file to fetch and its sha-256 fingerprint are pinned in
# scripts\portable-python.txt; a file that doesn't match is not used.
# Uses only what Windows 10 (April 2018 or later) and 11 have: PowerShell,
# curl.exe and tar.exe. Windows on ARM runs the x86_64 build by emulation
# (libzim has no ARM version for Windows).
#
#   get-python.ps1              fetch it if needed; print the path of python.exe
#   get-python.ps1 -Installed   print the path only if already there
# The path is the only thing on stdout; messages go to stderr.
param([switch]$Installed)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
function Say($text) { [Console]::Error.WriteLine($text) }

try {
    $release = ''; $version = ''; $pin = $null
    foreach ($line in Get-Content (Join-Path $PSScriptRoot 'portable-python.txt')) {
        $f = @($line.Trim() -split '\s+')
        if ($f[0] -eq 'release') { $release = $f[1] }
        elseif ($f[0] -eq 'version') { $version = $f[1] }
        elseif ($f[0] -eq 'windows-x86_64') { $pin = $f }
    }
    $base = Join-Path $env:LOCALAPPDATA 'knowledge-arc'
    $target = Join-Path $base "python-$version"
    $python = Join-Path $target 'python.exe'
    if (Test-Path $python) { Write-Output $python; exit 0 }
    if ($Installed) { exit 1 }

    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    if (-not ((Test-Path $curl) -and (Test-Path $tar))) {
        throw "this Windows has no curl.exe or tar.exe (Windows 10 before April 2018). Update Windows, or install Python 3.11 or newer from https://www.python.org/downloads/"
    }
    New-Item -ItemType Directory -Force $base | Out-Null
    $name = $pin[2]
    $url = "https://github.com/astral-sh/python-build-standalone/releases/download/$release/" + [uri]::EscapeDataString($name)
    $part = Join-Path $base "$name.part"
    Say ""
    Say "This computer has no Python 3.11 or newer. Fetching a portable Python $version"
    Say "(about 22 MB, once; nothing is installed) ..."
    # curl.exe and tar.exe are given names relative to the cache folder: tar.exe
    # can't open a full path holding a character outside the code page (a user
    # name such as Lukasz written with a Polish L).
    Set-Location -LiteralPath $base
    & $curl -fsSL --retry 3 -o "$name.part" $url
    if ($LASTEXITCODE) { throw "the download failed. Check the internet connection and try again." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $part).Hash.ToLower() -ne $pin[1]) {
        Remove-Item -Force -LiteralPath $part
        throw "the downloaded file does not match its fingerprint (sha-256), so it was not used."
    }
    $tmp = Join-Path $base "python-$version.part"
    if (Test-Path -LiteralPath $tmp) { Remove-Item -Recurse -Force -LiteralPath $tmp }
    New-Item -ItemType Directory $tmp | Out-Null
    & $tar -xzf "$name.part" -C "python-$version.part"
    if ($LASTEXITCODE) { throw "the downloaded file could not be unpacked." }
    Move-Item (Join-Path $tmp 'python') $target
    Remove-Item -Recurse -Force $tmp
    Remove-Item -Force $part
    Set-Content -Encoding ASCII (Join-Path $target 'knowledge-arc-portable.txt') `
        "The portable Python that Knowledge Arc's make-arc fetched. Delete this folder to remove it."
    Say "Python $version is ready in $target (delete that folder to remove it)."
    Write-Output $python
    exit 0
} catch {
    Say ""
    Say "Could not fetch a portable Python: $($_.Exception.Message)"
    exit 1
}
