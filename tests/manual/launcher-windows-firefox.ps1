param([string]$D)
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type -Namespace ArcTest -Name Win -MemberDefinition '[DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);'
Remove-Item Env:ARC_NO_BROWSER -ErrorAction SilentlyContinue
function FF { @(Get-CimInstance Win32_Process -Filter "Name='firefox.exe'" | Where-Object { $_.CommandLine -like '*knowledge-arc-firefox-*' }) }
function FFWindows { @(Get-Process firefox -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } | ForEach-Object { $_.MainWindowTitle }) }
function Click-Again {
  $root = [System.Windows.Automation.AutomationElement]::RootElement
  $sp = (Get-Process powershell | Where-Object { $_.MainWindowTitle -eq 'Knowledge Arc' } | Select-Object -First 1).Id
  $cond = New-Object System.Windows.Automation.AndCondition((New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, 'Knowledge Arc')), (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$sp)))
  $win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
  $bc = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, 'Open the library again')
  $btn = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $bc)
  # UI Automation does not always offer the button's Invoke pattern (it sees a plain Pane):
  # send the button a click message instead.
  [void][ArcTest.Win]::PostMessage([IntPtr]$btn.Current.NativeWindowHandle, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero)   # BM_CLICK
}
$t0 = Get-Date
Start-Process (Join-Path $D '1 Open Knowledge Arc (Windows).bat')
for ($i = 0; $i -lt 60 -and (FFWindows).Count -eq 0; $i++) { Start-Sleep 1 }
"first Firefox window after $([int]((Get-Date) - $t0).TotalSeconds) s: $((FFWindows) -join ' | ')"
Start-Sleep 4
"firefox windows: $((FFWindows) -join ' | ')  (arc firefox processes: $((FF).Count))"
"--- click 'Open the library again' while Firefox is open"
Click-Again; Start-Sleep 4
"firefox windows: $((FFWindows) -join ' | ')"
Get-Content "$env:TEMP\knowledge-arc.log" | Select-Object -Last 2
"--- close Firefox, then click again"
FF | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Start-Sleep 3
"firefox windows after closing: $((FFWindows).Count)"
Click-Again
for ($i = 0; $i -lt 20 -and (FFWindows).Count -eq 0; $i++) { Start-Sleep 1 }
Start-Sleep 3
"firefox windows: $((FFWindows) -join ' | ')"
"--- close the small window"
Get-Process powershell | Where-Object { $_.MainWindowTitle -eq 'Knowledge Arc' } | ForEach-Object { [void]$_.CloseMainWindow() }
Start-Sleep 3
"kiwix-serve running: $([bool](Get-Process kiwix-serve -ErrorAction SilentlyContinue))"
FF | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
"--- log"; Get-Content "$env:TEMP\knowledge-arc.log"
