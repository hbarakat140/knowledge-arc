# Knowledge Arc: fetch the portable Python that make-arc.bat uses when this
# computer has no Python 3.11 or newer. Nothing is installed: the Python is
# unpacked into %LOCALAPPDATA%\knowledge-arc\python-<version>, and deleting
# that folder removes it. The file to fetch and its sha-256 fingerprint are
# pinned in scripts\portable-python.txt; a file that doesn't match is not used.
# Uses only what Windows 10 and 11 have: PowerShell, curl.exe and tar.exe.
# Run by make-arc.bat; exits 0 when the Python is ready.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

try {
    $release = ''; $version = ''; $pins = @{}
    foreach ($line in Get-Content (Join-Path $PSScriptRoot 'portable-python.txt')) {
        $f = @($line.Trim() -split '\s+')
        if ($line.StartsWith('#') -or $f.Count -lt 2) { continue }
        if ($f[0] -eq 'release') { $release = $f[1] }
        elseif ($f[0] -eq 'version') { $version = $f[1] }
        elseif ($f.Count -eq 3) { $pins[$f[0]] = $f }
    }
    # Windows on ARM runs the x86_64 build by emulation (libzim has no ARM version for Windows).
    $pin = $pins['windows-x86_64']
    $base = Join-Path $env:LOCALAPPDATA 'knowledge-arc'
    $target = Join-Path $base "python-$version"
    if (Test-Path (Join-Path $target 'python.exe')) { exit 0 }

    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    if (-not (Test-Path $tar)) {
        throw "this Windows has no tar.exe (Windows 10 before April 2018). Update Windows, or install Python 3.11 or newer from https://www.python.org/downloads/"
    }
    New-Item -ItemType Directory -Force $base | Out-Null
    $name = $pin[2]
    $url = "https://github.com/astral-sh/python-build-standalone/releases/download/$release/" + [uri]::EscapeDataString($name)
    $part = Join-Path $base "$name.part"
    Write-Host ""
    Write-Host "This computer has no Python 3.11 or newer. Fetching a portable Python $version"
    Write-Host "(about 22 MB, once; nothing is installed) ..."
    if (Test-Path $curl) {
        & $curl -fsSL --retry 3 -o $part $url
        if ($LASTEXITCODE) { throw "the download failed. Check the internet connection and try again." }
    } else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $part
    }
    $sha = (Get-FileHash -Algorithm SHA256 $part).Hash.ToLower()
    if ($sha -ne $pin[1]) {
        Remove-Item -Force $part
        throw "the downloaded file does not match its fingerprint (sha-256), so it was not used."
    }
    $tmp = Join-Path $base "python-$version.part"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    New-Item -ItemType Directory $tmp | Out-Null
    & $tar -xzf $part -C $tmp
    if ($LASTEXITCODE) { throw "the downloaded file could not be unpacked." }
    Move-Item (Join-Path $tmp 'python') $target
    Remove-Item -Recurse -Force $tmp
    Remove-Item -Force $part
    Set-Content -Encoding ASCII (Join-Path $target 'knowledge-arc-portable.txt') `
        "The portable Python that Knowledge Arc's make-arc fetched. Delete this folder to remove it."
    Write-Host "Python $version is ready in $target"
    Write-Host "(delete that folder to remove it)."
    exit 0
} catch {
    Write-Host ""
    Write-Host "Could not fetch a portable Python: $($_.Exception.Message)"
    exit 1
}
