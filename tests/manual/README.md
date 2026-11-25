# Manual tests: the Windows launcher and the Kiwix spike

These scripts are run by hand on a Windows computer, not by the test suite. They were written on 25 Nov 2026 for the "one door, one website" redesign (step 0, the Kiwix spike, and step 2, the single double-click). Small windows and Firefox **open on the screen** while they run.

## A scratch drive

A folder laid out like a drive, with the real library program and a few small collections:

```
<D>/1 Open Knowledge Arc (Windows).bat        from launchers/open-knowledge-arc.bat, CRLF
<D>/arc/system/open-knowledge-arc.ps1         from launchers/open-knowledge-arc.ps1, CRLF, ASCII
<D>/arc/software/windows/kiwix/               kiwix-tools_win-x86_64-3.8.1.zip unpacked (catalog T9-001)
<D>/arc/collections/*.zim                     e.g. wikipedia_en_chemistry_mini_2026-10.zim (23 MB, download.kiwix.org)
                                              plus the two from make-test-zims.py
<D>/arc/software/windows/firefox-setup-153.7.0esr.exe   optional (catalog T9-006), for the Firefox test
<D>/arc/software/firefox-user.js              optional, from launchers/
```

A full `assemble.py` scratch build works too.

## The scripts

| Script | What it checks |
|---|---|
| `make-test-zims.py <folder>` | Writes `arcspike.zim` (a shell page that frames another collection, and fetches `/search?format=xml` and `/suggest`) and `noindex.zim` (no full-text index). Run with `.venv-build` (libzim). |
| `cdp.mjs <url> <js>...` | Drives a headless Chrome over the DevTools protocol (Node 22): opens a page, then evaluates each expression and prints the result. Used for the spike: `http://127.0.0.1:8655/content/arcspike/shell.html#<book>/<path>`. |
| `launcher-windows-count.ps1 -Bat <D>\1 Open...bat [-Wait 8] [-Keep]` | Starts the launcher the way a double-click does, lists the **new visible windows** at 1, 2, 4 and 8 seconds (pass: only `powershell|Knowledge Arc`), checks the library answers, closes the small window and checks the library stopped. Sets `ARC_NO_BROWSER=1`. |
| `launcher-windows-cases.ps1 -Repo <repo> -D <D>` | A: double-clicking twice (one window, one server). B: a library left running without its window (replaced cleanly). C: a broken script (falls back to the plain black window, library still opens). D: an error inside the script (a Knowledge Arc message window, not silence). |
| `launcher-windows-firefox.ps1 -D <D>` | With the drive's Firefox installer: first open (unpacks, about 20 s), "Open the library again" while Firefox is open (still one window), after Firefox is closed (opens again), closing the small window stops the library. |

## A whole test drive without downloading (25 Nov 2026)

`stage-test-drive.py <repo> <staging> <bundle> [drive-path=real-file ...]` (run with `.venv-build`'s Python, `-I`) stages every row of an edition: each guide a one-page PDF naming the guide it stands for, each collection a tiny real ZIM under its real name, each HTML book a small page, software as tiny archives; `drive-path=real-file` puts a real file in place of a stand-in (the real Windows kiwix-tools zip and Firefox installer, real collections, the PDFs in `hosted/`). Then `scripts/assemble.py --staging <staging> --drive <folder> --bundle full` builds it. Any folder works, spaces in its path included (assemble unpacks Mozilla's installer under a short temporary path, then moves it onto the drive; only if TEMP's path has spaces and the computer keeps no short names does it stop and say to change TEMP). To give someone a copy to try, mirror the folder (`robocopy /MIR` on Windows).

`shot.mjs <url> <out.png> [js]` (Node 22): opens a page in headless Chrome over the DevTools protocol, runs the JavaScript after 4 s, prints the page title and saves a screenshot. For a phone, change the metrics to 390 x 760, `mobile: true`. Headless Chrome's own `--screenshot` hangs on `127.0.0.1`; this does not.

## Results on 25 Nov 2026 (Windows 11, Windows Terminal as the default console)

All passed: one visible window (the small Knowledge Arc window) after the start; the library answers; closing the window stops it; cases A to D; the Firefox test. Found and fixed on the way: started hidden, PowerShell's standard message box stays invisible, so errors use a plain window (`Show-Message`).

Re-run after the launcher cleanup (25 Nov 2026, afternoon): all pass; Firefox's first open now 14 s (unpacked while the library starts). The Firefox test presses "Open the library again" with a `BM_CLICK` message: UI Automation often shows the WinForms buttons as a plain Pane without the Invoke pattern.

Not yet tested: sharing over Wi-Fi (`-Share`, raises the Windows firewall question), the Mac and Linux launchers, a real exFAT drive.
