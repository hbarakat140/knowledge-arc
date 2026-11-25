param([string]$Repo, [string]$D)
$ErrorActionPreference = 'Continue'
function Put-Launchers([string]$extraPs1 = '') {
  foreach ($pair in @(@('launchers\open-knowledge-arc.bat', '1 Open Knowledge Arc (Windows).bat'), @('launchers\open-knowledge-arc.ps1', 'arc\system\open-knowledge-arc.ps1'))) {
    $t = [IO.File]::ReadAllText((Join-Path $Repo $pair[0])).Replace("`r`n", "`n").Replace("`n", "`r`n")
    if ($pair[1] -like '*.ps1') { $t += $extraPs1 }
    [IO.File]::WriteAllText((Join-Path $D $pair[1]), $t, (New-Object Text.ASCIIEncoding))
  }
}
function Small { Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Knowledge Arc' } }
function Kiwix { @(Get-Process kiwix-serve -ErrorAction SilentlyContinue) }
function Close-All { Small | ForEach-Object { [void]$_.CloseMainWindow() }; Start-Sleep 2; Kiwix | Stop-Process -Force -ErrorAction SilentlyContinue
  Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -like '*Open Knowledge Arc*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }
$bat = Join-Path $D '1 Open Knowledge Arc (Windows).bat'
$env:ARC_NO_BROWSER = '1'

"== A: second double-click while open"
Put-Launchers
Start-Process $bat; Start-Sleep 5
Start-Process $bat; Start-Sleep 5
"  small windows: $(@(Small).Count)  kiwix-serve processes: $((Kiwix).Count)"
Close-All

"== B: library left running without its window"
Start-Process -FilePath (Join-Path $D 'arc\software\windows\kiwix\kiwix-serve.exe') -ArgumentList '-p','8642','-i','127.0.0.1',"`"$D\arc\collections\noindex.zim`"" -WindowStyle Hidden
Start-Sleep 2
"  leftover running: $((Kiwix).Count)"
Start-Process $bat; Start-Sleep 6
"  small windows: $(@(Small).Count)  kiwix-serve processes: $((Kiwix).Count)"
"  log: " + ((Get-Content "$env:TEMP\knowledge-arc.log") -join ' / ')
Close-All

"== C: script broken (syntax error): plain way in a visible window"
Put-Launchers "`r`nfunction Broken( {`r`n"
Start-Process $bat; Start-Sleep 6
$cmd = Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -like '*Open Knowledge Arc*' }
"  small windows: $(@(Small).Count)  console fallback running: $([bool]$cmd)  kiwix-serve: $((Kiwix).Count)"
try { "  library answers: " + (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:8642/catalog/v2/entries?count=1').StatusCode } catch { "  no answer" }
Close-All

"== D: runtime error inside the script: a message, not silence"
Put-Launchers "`r`n"
$t = [IO.File]::ReadAllText((Join-Path $D 'arc\system\open-knowledge-arc.ps1')).Replace('function Test-Listening {', "throw 'test failure'`r`nfunction Test-Listening {")
[IO.File]::WriteAllText((Join-Path $D 'arc\system\open-knowledge-arc.ps1'), $t, (New-Object Text.ASCIIEncoding))
Start-Process $bat; Start-Sleep 5
$box = Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Knowledge Arc' }
"  a Knowledge Arc message window is showing: $([bool]$box)  kiwix-serve: $((Kiwix).Count)"
$box | ForEach-Object { [void]$_.CloseMainWindow() }
Start-Sleep 1; Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Knowledge Arc' } | Stop-Process -Force
Put-Launchers
"done"
