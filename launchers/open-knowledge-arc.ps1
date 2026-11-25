# Knowledge Arc for Windows: open the library and show its small window.
# On the drive this file is arc\system\open-knowledge-arc.ps1. It is started,
# hidden, by "1 Open Knowledge Arc (Windows).bat" at the top of the drive (or
# "arc\Share over Wi-Fi (Windows).bat" with -Share). Uses only what comes with
# Windows 10 and 11: Windows PowerShell 5.1 and its window toolkit.
#
# 1. A small window appears at once: "Opening the library...".
# 2. The library program (kiwix-serve, in arc\software\windows\kiwix) starts,
#    hidden, with every collection on the drive. Only this computer can reach
#    it, unless -Share.
# 3. As soon as it answers, one browser window opens: the drive's own Firefox
#    in a fresh temporary profile, else the computer's own browser.
# 4. Closing the small window stops the library. Nothing is left on the computer.
#
# Room for a second program later (the AI helper, docs/architecture.md
# section 13): start it next to the library in Start-Library and stop it in
# Stop-Library.
#
# Keep this file plain ASCII: Windows PowerShell 5.1 reads a file without a
# byte-order mark in the computer's own code page.
#
# The plain way in "1 Open Knowledge Arc (Windows).bat" (used when PowerShell
# cannot run this script) does the same steps: keep the two in step.
#
# Test hook (never needed by a reader): ARC_NO_BROWSER=1 opens no browser and
# writes what it would open to the log.

param([switch]$Share)
$ErrorActionPreference = 'Stop'
$Port = 8642
# One library at a time. Taken first thing: it is also the sign of life that
# "1 Open Knowledge Arc (Windows).bat" waits for before it closes.
$created = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\KnowledgeArcLibrary$Port", [ref]$created)
$Title = 'Knowledge Arc'
$Fallback = 'Open "2 If nothing opens" at the top of the drive instead.'
$Log = Join-Path $env:TEMP 'knowledge-arc.log'                # this window's notes

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic
[System.Windows.Forms.Application]::EnableVisualStyles()

function Write-Log($text) {
    try { Add-Content -LiteralPath $Log -Value ((Get-Date -Format 's') + '  ' + $text) } catch {}
}

function New-ArcWindow($height) {
    # The look shared by the small window and the message window.
    $f = New-Object System.Windows.Forms.Form
    $f.Text = $Title
    $f.StartPosition = 'CenterScreen'
    $f.FormBorderStyle = 'FixedDialog'
    $f.MaximizeBox = $false
    $f.ClientSize = New-Object System.Drawing.Size(460, $height)
    $f.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $f.BackColor = [System.Drawing.Color]::White
    return $f
}

function New-Label($f, $top, $height, $text) {
    $l = New-Object System.Windows.Forms.Label
    $l.Location = New-Object System.Drawing.Point(20, $top)
    $l.Size = New-Object System.Drawing.Size(420, $height)
    $l.Text = $text
    $f.Controls.Add($l)
    return $l
}

function Show-Problem($text) {
    # Logged, then shown in a plain window with an OK button. (Started hidden,
    # this script cannot use Windows' standard message box: it stays invisible.)
    Write-Log "PROBLEM: $text"
    $f = New-ArcWindow 210
    $f.TopMost = $true
    [void](New-Label $f 18 130 $text)
    $ok = New-Object System.Windows.Forms.Button
    $ok.Location = New-Object System.Drawing.Point(340, 160)
    $ok.Size = New-Object System.Drawing.Size(100, 34)
    $ok.Text = 'OK'
    $ok.Add_Click({ $f.Close() })
    $f.Controls.Add($ok)
    $f.AcceptButton = $ok
    [void]$f.ShowDialog()
}

# Started hidden: any error must be shown, never lost.
trap {
    try { Show-Problem "The library could not open: $_`r`n`r`n$Fallback" } catch {}
    exit 1
}

$Local = "http://127.0.0.1:$Port/"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)    # arc\system -> top of the drive
$Kiwix = Join-Path $Root 'arc\software\windows\kiwix\kiwix-serve.exe'
$ServerLog = Join-Path $env:TEMP 'knowledge-arc-server.log'   # the library program's own messages
$script:Server = $null
$script:FfProfile = $null
$script:Firefox = $null
$script:FirefoxLooked = $false
$script:Unpacking = $null

# ---- one library at a time ----------------------------------------------

if (-not $created) {
    # Already open from this computer: bring its small window to the front.
    try { [Microsoft.VisualBasic.Interaction]::AppActivate($Title) } catch {}
    if ($Share) {
        Show-Problem 'The library is already open on this computer, but not shared over Wi-Fi. Click "Close the library" in its small window, then double-click "Share over Wi-Fi" again.'
    }
    exit 0
}

function Test-Listening {
    # Something listens on the library's port. Instant: no connection is made
    # (a connection to a closed port takes about a second to fail on Windows).
    $ln = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    return [bool]($ln | Where-Object { $_.Port -eq $Port } | Select-Object -First 1)
}

function Test-Library {
    # True when the library answers on this computer.
    if (-not (Test-Listening)) { return $false }
    try {
        $req = [System.Net.HttpWebRequest]::Create($Local + 'catalog/v2/entries?count=1')
        $req.Timeout = 700
        $req.Proxy = $null
        $resp = $req.GetResponse()
        $resp.Close()
        return $true
    } catch { return $false }
}

# ---- the browser ----------------------------------------------------------

function Get-FirefoxPlace {
    # Where the drive's own Firefox is, or will be once unpacked: @(exe, setup)
    # (setup is $null when there is nothing to unpack), or $null if none. A
    # drive built on a Mac or Linux carries Mozilla's installer still packed:
    # it is unpacked (nothing is installed) into this computer's temporary
    # folder, once. The installer's /ExtractDir takes no spaces (quoted, it
    # opens its install window instead), so the folder's short name is used;
    # if that still has a space, the computer's own browser is used.
    $ff = Join-Path $Root 'arc\software\windows\firefox\firefox.exe'
    if (Test-Path -LiteralPath $ff) { return ,@($ff, $null) }
    $setup = Get-ChildItem -LiteralPath (Join-Path $Root 'arc\software\windows') -Filter 'firefox-setup-*.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $setup) { return $null }
    try {
        $short = (New-Object -ComObject Scripting.FileSystemObject).GetFolder($env:TEMP).ShortPath
    } catch { return $null }
    $dir = Join-Path $short ('knowledge-arc-' + $setup.BaseName)
    if ($dir.Contains(' ')) { return $null }
    $exe = Join-Path $dir 'core\firefox.exe'
    if (Test-Path -LiteralPath $exe) { return ,@($exe, $null) }
    return ,@($exe, $setup.FullName)
}

function Start-FirefoxUnpack {
    # Unpack the drive's Firefox while the library starts (about 20 s the
    # first time), so the browser can open as soon as the library answers.
    $place = Get-FirefoxPlace
    if (-not $place -or -not $place[1]) { return }
    $dir = Split-Path -Parent (Split-Path -Parent $place[0])
    try {
        $script:Unpacking = Start-Process -FilePath $place[1] -ArgumentList "/ExtractDir=$dir" -WindowStyle Hidden -PassThru
    } catch { Write-Log "The drive's Firefox could not be unpacked: $_" }
}

function Find-Firefox {
    # The drive's own Firefox, ready to start, or $null.
    if ($script:Unpacking) {
        # A stalled installer must not freeze the small window: after two
        # minutes, the computer's own browser is used instead.
        if (-not $script:Unpacking.WaitForExit(120000)) { Write-Log "The drive's Firefox is still unpacking: using the computer's browser." }
        $script:Unpacking = $null
    }
    $place = Get-FirefoxPlace
    if ($place -and -not $place[1]) { return $place[0] }
    return $null
}

function Get-ArcFirefox {
    # The Firefox this window started (found by its profile), if it still runs.
    if (-not $script:FfProfile) { return $null }
    Get-CimInstance Win32_Process -Filter "Name = 'firefox.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($script:FfProfile) } | Select-Object -First 1
}

function Remove-FirefoxProfile {
    # The session's temporary profile, once its Firefox has closed.
    if ($script:FfProfile -and -not (Get-ArcFirefox)) {
        Remove-Item -LiteralPath $script:FfProfile -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Remove-OldProfiles {
    # Profiles left by earlier sessions (the small window was closed before
    # Firefox), once no Firefox uses them any more.
    $old = @(Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter 'knowledge-arc-firefox-*' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^knowledge-arc-firefox-[0-9a-f]{12}$' })
    if ($old.Count -eq 0) { return }
    $inUse = @(Get-CimInstance Win32_Process -Filter "Name = 'firefox.exe'" -ErrorAction SilentlyContinue | ForEach-Object { $_.CommandLine })
    foreach ($d in $old) {
        if (-not ($inUse | Where-Object { $_ -and $_.Contains($d.Name) })) {
            Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Test-FirefoxOpen {
    # Is the Firefox this window started still running? Then bring it to the front.
    $p = Get-ArcFirefox
    if ($p) {
        try { [Microsoft.VisualBasic.Interaction]::AppActivate([int]$p.ProcessId) } catch {}
        return $true
    }
    return $false
}

function Open-Browser {
    if ($env:ARC_NO_BROWSER -eq '1') {
        $ff = Find-Firefox
        Write-Log ("TEST: would open " + $(if ($ff) { "$ff" } else { 'the computer''s browser' }) + " at $Local")
        return
    }
    if (-not $script:FirefoxLooked) { $script:Firefox = Find-Firefox; $script:FirefoxLooked = $true }
    if ($script:Firefox) {
        if (Test-FirefoxOpen) { return }   # already open: brought to the front
        if (-not $script:FfProfile) {
            # One fresh profile for this session: nothing is written to the drive.
            $script:FfProfile = Join-Path $env:TEMP ('knowledge-arc-firefox-' + [guid]::NewGuid().ToString('N').Substring(0, 12))
            New-Item -ItemType Directory -Path $script:FfProfile -Force | Out-Null
            $userjs = Join-Path $Root 'arc\software\firefox-user.js'
            if (Test-Path -LiteralPath $userjs) { Copy-Item -LiteralPath $userjs -Destination (Join-Path $script:FfProfile 'user.js') }
        }
        try {
            Start-Process -FilePath $script:Firefox -ArgumentList @('-no-remote', '-profile', ('"' + $script:FfProfile + '"'), $Local)
            return
        } catch { Write-Log "The drive's Firefox did not start: $_" }
    }
    Start-Process $Local   # the computer's own browser
}

# ---- the library ----------------------------------------------------------

function Get-Collections {
    # Every library package on the drive, as paths relative to the top (the
    # drive letter can change).
    $list = @()
    foreach ($d in @('arc\site', 'arc\collections')) {
        $full = Join-Path $Root $d
        if (Test-Path -LiteralPath $full) {
            $list += Get-ChildItem -LiteralPath $full -Filter '*.zim' | ForEach-Object { "$d\$($_.Name)" }
        }
    }
    return $list
}

function Stop-Leftover {
    # A library from this drive still running without its window (the window
    # was killed): stop it, so this one starts clean.
    Get-Process -Name 'kiwix-serve' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and ($_.Path -ieq $Kiwix) } |
        ForEach-Object { try { $_.Kill(); $_.WaitForExit(5000) | Out-Null } catch {} }
}

function Start-Library {
    if (-not (Test-Path -LiteralPath $Kiwix)) {
        return "The library program is missing from this drive ($Kiwix). $Fallback Or use another copy of the drive."
    }
    $zims = Get-Collections
    if ($zims.Count -eq 0) {
        return "No library packages were found on this drive. Open ""2 If nothing opens"" at the top of the drive for the guides that are here."
    }
    Stop-Leftover
    if (Test-Library) {
        return "Another program on this computer is already using the library's address ($Local). Close it, or restart the computer, and try again."
    }
    $address = if ($Share) { 'all' } else { '127.0.0.1' }
    # -b  links to the internet show a clear "not available" page
    # -k  a damaged package is skipped instead of stopping everything
    $kargs = @('-i', $address, '-p', "$Port", '-b', '-k')
    $homePage = 'arc\system\library-home.html'
    if (Test-Path -LiteralPath (Join-Path $Root $homePage)) { $kargs += @('-c', ('"' + $homePage + '"')) }
    $kargs += ($zims | ForEach-Object { '"' + $_ + '"' })
    Write-Log ("Starting the library: " + $zims.Count + " collections" + $(if ($Share) { ', shared over Wi-Fi' } else { '' }))
    try {
        $script:Server = Start-Process -FilePath $Kiwix -ArgumentList $kargs -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $ServerLog -RedirectStandardError ($ServerLog + '.err')
    } catch {
        return "Windows did not let the library program start ($_). $Fallback"
    }
    return $null
}

function Stop-Library {
    if ($script:Server -and -not $script:Server.HasExited) {
        try { $script:Server.Kill(); $script:Server.WaitForExit(5000) | Out-Null } catch {}
    }
}

function Get-ShareAddresses {
    [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
        Where-Object { $_.OperationalStatus -eq 'Up' -and $_.NetworkInterfaceType -ne 'Loopback' } |
        ForEach-Object { $_.GetIPProperties().UnicastAddresses } |
        Where-Object { $_.Address.AddressFamily -eq 'InterNetwork' -and -not $_.Address.ToString().StartsWith('169.254.') } |
        ForEach-Object { "http://$($_.Address):$Port/" }
}

# ---- the small window -----------------------------------------------------

$form = New-ArcWindow 230
$heading = New-Label $form 18 30 'Opening the library...'
$heading.Font = New-Object System.Drawing.Font('Segoe UI', 13, [System.Drawing.FontStyle]::Bold)
$body = New-Label $form 54 110 'This can take a minute on a big drive. Your web browser will open by itself.'

$again = New-Object System.Windows.Forms.Button
$again.Location = New-Object System.Drawing.Point(20, 178)
$again.Size = New-Object System.Drawing.Size(200, 36)
$again.Text = 'Open the library again'
$again.Enabled = $false
$again.Add_Click({ Open-Browser })
$form.Controls.Add($again)

$close = New-Object System.Windows.Forms.Button
$close.Location = New-Object System.Drawing.Point(240, 178)
$close.Size = New-Object System.Drawing.Size(200, 36)
$close.Text = 'Close the library'
$close.Add_Click({ $form.Close() })
$form.Controls.Add($close)

$script:Started = $null
$script:SlowSaid = $false
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 500
$timer.Add_Tick({
    # Until the library answers; then the timer stops.
    if ($script:Server -and $script:Server.HasExited) {
        $timer.Stop()
        $heading.Text = 'The library did not start.'
        $body.Text = "Open ""2 If nothing opens"" at the top of the drive: it has the guides and other ways to read the collections. Details for a helper: $Log and $ServerLog"
        Write-Log 'The library stopped by itself.'
        return
    }
    if (Test-Library) {
        $timer.Stop()
        $heading.Text = 'The library is open in your browser.'
        $text = 'Keep this window open while you read. You can make it small. Close it when you have finished: that stops the library.'
        if ($Share) {
            $text = "Shared over Wi-Fi. On a phone or another computer on the same Wi-Fi, open the web browser and type:`r`n" + ((Get-ShareAddresses) -join "`r`n") + "`r`nKeep this window open."
        } else {
            $text += "`r`n`r`nThe browser did not open? Type 127.0.0.1:$Port in its address bar."
        }
        $body.Text = $text
        $again.Enabled = $true
        Write-Log 'The library answers.'
        $form.Refresh()   # the first time, the drive's Firefox may still be unpacking
        Open-Browser
        return
    }
    if (-not $script:SlowSaid -and ((Get-Date) - $script:Started).TotalSeconds -ge 60) {
        $script:SlowSaid = $true
        $body.Text = 'Still opening. A big or slow drive can take a few minutes. If nothing happens, close this window and open "2 If nothing opens" at the top of the drive.'
    }
})

$form.Add_Shown({
    $form.Activate()
    $why = Start-Library
    if ($why) {
        $heading.Text = 'The library could not start.'
        $body.Text = $why
        Write-Log "PROBLEM: $why"
        return
    }
    Start-FirefoxUnpack
    $script:Started = Get-Date
    $timer.Start()
    Remove-OldProfiles
})
$form.Add_FormClosed({ $timer.Stop(); Remove-FirefoxProfile; Write-Log 'Closed.' })

try {
    Remove-Item -LiteralPath $Log, $ServerLog, ($ServerLog + '.err') -ErrorAction SilentlyContinue
    Write-Log "Knowledge Arc on $Root"
    [void]$form.ShowDialog()
} catch {
    Show-Problem "Something went wrong while opening the library: $_`r`n`r`n$Fallback"
} finally {
    Stop-Library
    $mutex.ReleaseMutex()
}
