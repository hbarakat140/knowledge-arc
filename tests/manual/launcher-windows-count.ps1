param([string]$Bat, [int]$Wait = 8, [switch]$Share, [switch]$Keep)
Add-Type @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Text;
public class Wins {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  public static List<string> List() {
    var r = new List<string>();
    EnumWindows((h, l) => { if (IsWindowVisible(h)) { var s = new StringBuilder(256); GetWindowText(h, s, 256);
      uint p; GetWindowThreadProcessId(h, out p); if (s.Length > 0) r.Add(p + "|" + s.ToString()); } return true; }, IntPtr.Zero);
    return r;
  }
}
"@
function Snap { [Wins]::List() | ForEach-Object { $pid_, $t = $_.Split('|', 2); $n = (Get-Process -Id $pid_ -ErrorAction SilentlyContinue).ProcessName; "$n|$t" } }
$before = Snap
$env:ARC_NO_BROWSER = '1'
if ($Share) { $env:ARC_SHARE = '1' }
Start-Process -FilePath $Bat
foreach ($t in 1, 2, 4, $Wait) {
  Start-Sleep -Seconds ([Math]::Max(1, $t - ($(if ($t -eq 1) {0} else {$last}))))
  $last = $t
  $new = Snap | Where-Object { $before -notcontains $_ }
  "t=${t}s new visible windows: " + ($new -join ' ;; ')
}
$k = Get-Process kiwix-serve -ErrorAction SilentlyContinue
"kiwix-serve running: " + [bool]$k
try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:8642/catalog/v2/entries?count=1').StatusCode } catch { "no answer: $_" }
if (-not $Keep) {
  $f = Get-Process powershell | Where-Object { $_.MainWindowTitle -eq 'Knowledge Arc' }
  "small window processes: " + ($f | ForEach-Object Id)
  $f | ForEach-Object { [void]$_.CloseMainWindow() }
  Start-Sleep 3
  "after closing, kiwix-serve running: " + [bool](Get-Process kiwix-serve -ErrorAction SilentlyContinue)
  "after closing, powershell small window: " + [bool](Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Knowledge Arc' })
}
"--- log"; Get-Content "$env:TEMP\knowledge-arc.log" -ErrorAction SilentlyContinue
