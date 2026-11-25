@echo off
rem Knowledge Arc: double-click to open the library in the web browser.
rem On the drive this file is "1 Open Knowledge Arc (Windows).bat".
rem
rem It hands over to arc\system\open-knowledge-arc.ps1 (Windows' own
rem PowerShell), started hidden: a small Knowledge Arc window says when the
rem library is open, and closing it stops the library. This black window
rem closes by itself.
rem
rem If PowerShell cannot run that script (missing, or blocked by a policy on
rem this computer), the plain way below runs instead: the library starts in
rem this window, which must then stay open while you read.
setlocal EnableDelayedExpansion
set "PORT=8642"
set "URL=http://127.0.0.1:%PORT%/"
if "%~1"==":openbrowser" goto openbrowser
cd /d "%~dp0"

set "ARC_PS1=%~dp0arc\system\open-knowledge-arc.ps1"
if not exist "%ARC_PS1%" goto console
rem The first PowerShell checks that the script may run here (full language,
rem no signing policy) and reads without errors, then starts it hidden
rem (started hidden, it gets no window of its own) and waits up to 20 s for
rem its sign of life: the mutex it holds while its small window is open. If
rem the script stops or stalls before that (a policy, a security prompt no
rem one can see), it is stopped and the plain way below runs instead.
powershell -NoProfile -ExecutionPolicy Bypass -Command "if ($ExecutionContext.SessionState.LanguageMode -ne 'FullLanguage') { exit 5 }; $no = @('AllSigned','Restricted'); if ($no -contains [string](Get-ExecutionPolicy -Scope MachinePolicy) -or $no -contains [string](Get-ExecutionPolicy -Scope UserPolicy)) { exit 3 }; $e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile($env:ARC_PS1, [ref]$null, [ref]$e); if ($e) { exit 4 }; $a = @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',([char]34 + $env:ARC_PS1 + [char]34)); if ($env:ARC_SHARE -eq '1') { $a += '-Share' }; $p = Start-Process powershell -WindowStyle Hidden -ArgumentList $a -PassThru; $m = $null; for ($i = 0; $i -lt 80; $i++) { if ([System.Threading.Mutex]::TryOpenExisting('Local\KnowledgeArcLibrary' + $env:PORT, [ref]$m)) { exit 0 }; if ($p.HasExited) { exit 6 }; Start-Sleep -Milliseconds 250 }; Stop-Process -Id $p.Id -Force; exit 7" && exit /b 0

:console
title Knowledge Arc - keep this window open while you read
rem Only this computer can reach the library, unless started by
rem "arc\Share over Wi-Fi (Windows).bat" (ARC_SHARE=1): then phones and
rem computers on the same network can too.
set "ADDRESS=127.0.0.1"
if "%ARC_SHARE%"=="1" set "ADDRESS=all"
set "KIWIX=arc\software\windows\kiwix\kiwix-serve.exe"

echo.
echo   KNOWLEDGE ARC
echo   =============
echo.

if not exist "%KIWIX%" (
  echo   The library program is missing from this drive:
  echo   %KIWIX%
  echo   Open "2 If nothing opens" instead, or use a copy of the drive.
  echo.
  pause
  exit /b 1
)

rem Every library package on the drive (relative paths: the drive letter can change).
set "ZIMS="
set "COUNT=0"
for %%D in ("arc\site" "arc\collections") do (
  if exist "%%~D\" for %%F in ("%%~D\*.zim") do (
    set ZIMS=!ZIMS! "%%~F"
    set /a COUNT+=1
  )
)
if "%COUNT%"=="0" (
  echo   No library packages were found on this drive.
  echo   Open "2 If nothing opens" for the guides that are here.
  echo.
  pause
  exit /b 1
)

echo   Opening %COUNT% collections. Your web browser will open by itself.
echo.
echo   KEEP THIS WINDOW OPEN while you read.
echo   When you have finished, close this window.
echo.
echo   If the browser does not open, type this address in it:
echo   %URL%
echo.

if "%ARC_SHARE%"=="1" (
  echo   SHARING OVER WI-FI. On a phone or another computer connected to the
  echo   same Wi-Fi, open the web browser and type one of these addresses:
  for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /c:"IPv4"') do (
    for /f "tokens=*" %%B in ("%%A") do echo       http://%%B:%PORT%/
  )
  echo   Windows may ask whether to allow kiwix-serve on networks: choose
  echo   Private networks and click Allow. Without that, phones cannot connect.
  echo.
)

rem The library's home page (one search box for everything), built with the drive.
set "HOMEPAGE="
if exist "arc\system\library-home.html" set HOMEPAGE=-c "arc\system\library-home.html"

rem Open the browser as soon as the library answers (helper runs alongside).
start "" /b cmd /c ""%~f0" :openbrowser"

rem -i 127.0.0.1  only this computer can reach it (no firewall question);
rem               -i all when sharing over Wi-Fi
rem -b            links to the internet show a clear "not available" page
rem -k            a damaged package is skipped instead of stopping everything
"%KIWIX%" -i %ADDRESS% -p %PORT% -b -k %HOMEPAGE% %ZIMS% >"%TEMP%\knowledge-arc-server.log" 2>&1

echo.
echo   The library has stopped. If it stopped by itself, it may already be
echo   open in another window: try %URL% in the browser.
echo.
pause
exit /b 0

:openbrowser
rem The drive's own Firefox. A drive built on a Mac or Linux carries Mozilla's
rem installer still packed: unpack it (nothing is installed) into this
rem computer's temporary folder, once, while the library starts. The
rem installer's /ExtractDir takes no spaces (quoted, it opens its install
rem window instead), so the folder's short name is used, and if that still
rem has a space, the computer's own browser opens instead.
set "FF=%~dp0arc\software\windows\firefox\firefox.exe"
if not exist "%FF%" for %%S in ("%~dp0arc\software\windows\firefox-setup-*.exe") do (
  for %%T in ("%TEMP%") do set "FFDIR=%%~sT\knowledge-arc-%%~nS"
  if "!FFDIR: =!"=="!FFDIR!" (
    if not exist "!FFDIR!\core\firefox.exe" "%%~fS" /ExtractDir=!FFDIR! >nul 2>&1
    if exist "!FFDIR!\core\firefox.exe" set "FF=!FFDIR!\core\firefox.exe"
  )
)
where curl.exe >nul 2>&1 || (timeout /t 3 /nobreak >nul & goto browser)
for /l %%i in (1,1,60) do (
  curl.exe -s -o nul "%URL%" >nul 2>&1 && goto browser
  timeout /t 1 /nobreak >nul
)

:browser
rem The drive's own Firefox (found above), in a fresh temporary profile
rem (nothing is written to the drive); else the computer's own browser.
rem (ARC_NO_BROWSER=1: tests only.)
if "%ARC_NO_BROWSER%"=="1" exit /b 0
if exist "%FF%" (
  set "PROF=%TEMP%\knowledge-arc-firefox-%RANDOM%%RANDOM%"
  mkdir "!PROF!" >nul 2>&1
  copy /y "%~dp0arc\software\firefox-user.js" "!PROF!\user.js" >nul 2>&1
  start "" "%FF%" -no-remote -profile "!PROF!" "%URL%"
  exit /b 0
)
start "" "%URL%"
exit /b 0
