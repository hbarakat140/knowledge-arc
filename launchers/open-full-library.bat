@echo off
rem Knowledge Arc: double-click to open the full library in the web browser.
rem On the drive this file is "2 Open full library (Windows).bat".
rem Starts the Kiwix server from this drive (only this computer can see it),
rem then opens the browser. Closing this window stops the library.
setlocal EnableDelayedExpansion
set "PORT=8642"
set "URL=http://127.0.0.1:%PORT%/"
rem Only this computer can reach the library, unless started by
rem "arc\Share over Wi-Fi (Windows).bat" (ARC_SHARE=1): then phones and
rem computers on the same network can too.
set "ADDRESS=127.0.0.1"
if "%ARC_SHARE%"=="1" set "ADDRESS=all"
if "%~1"==":openbrowser" goto openbrowser

cd /d "%~dp0"
title Knowledge Arc - keep this window open while you read
set "KIWIX=arc\software\windows\kiwix\kiwix-serve.exe"

echo.
echo   KNOWLEDGE ARC: FULL LIBRARY
echo   ===========================
echo.

if not exist "%KIWIX%" (
  echo   The library program is missing from this drive:
  echo   %KIWIX%
  echo   Use "1 START-HERE" instead, or a copy of the drive.
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
  echo   Use "1 START-HERE" for the guides that are here.
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
"%KIWIX%" -i %ADDRESS% -p %PORT% -b -k %HOMEPAGE% %ZIMS% >"%TEMP%\knowledge-arc.log" 2>&1

echo.
echo   The library has stopped. If it stopped by itself, it may already be
echo   open in another window: try %URL% in the browser.
echo.
pause
exit /b 0

:openbrowser
where curl.exe >nul 2>&1 || (timeout /t 3 /nobreak >nul & goto browser)
for /l %%i in (1,1,60) do (
  curl.exe -s -o nul "%URL%" >nul 2>&1 && goto browser
  timeout /t 1 /nobreak >nul
)

:browser
rem The drive's own Firefox, in a fresh temporary profile (nothing is written
rem to the drive or kept on the computer); else the computer's own browser.
set "FF=%~dp0arc\software\windows\firefox\firefox.exe"
if exist "%FF%" (
  set "PROF=%TEMP%\knowledge-arc-firefox-%RANDOM%%RANDOM%"
  mkdir "!PROF!" >nul 2>&1
  copy /y "%~dp0arc\software\firefox-user.js" "!PROF!\user.js" >nul 2>&1
  start "" "%FF%" -no-remote -profile "!PROF!" "%URL%"
  exit /b 0
)
start "" "%URL%"
exit /b 0
