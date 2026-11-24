@echo off
rem Make your own Knowledge Arc (Windows): double-click this file.
rem It runs make-arc.py, which asks which drive and which edition.
rem Python: the portable one if it was fetched before, else this computer's own
rem if it is 3.11 or newer, else a portable Python fetched once by
rem scripts\get-python.ps1 into %LOCALAPPDATA%\knowledge-arc (nothing
rem installed; delete that folder to remove it). Set ARC_PORTABLE_PYTHON=1 to
rem use the portable one anyway. Ends with make-arc.py's exit code.
cd /d "%~dp0"
set "PY="
set "OLDPY="
set "CODE=1"
rem The portable Python's path is built here, not read back from PowerShell:
rem a user name outside the console's code page would not survive that trip.
rem Same layout as get-python.ps1 (tests\test_make_arc.py keeps them equal).
set "PYVER="
for /f "tokens=2" %%v in ('findstr /b /c:"version " scripts\portable-python.txt') do set "PYVER=%%v"
set "PORTABLE=%LOCALAPPDATA%\knowledge-arc\python-%PYVER%\python.exe"
if exist "%PORTABLE%" goto run_portable
if defined ARC_PORTABLE_PYTHON goto fetch
call :find 11 PY
if defined PY goto run
rem An older one (3.9, 3.10) is kept as a fallback: it builds without search.
call :find 9 OLDPY

:fetch
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\get-python.ps1" >nul
if exist "%PORTABLE%" goto run_portable
if not defined OLDPY (
  echo.
  echo   Python is needed to make an arc, and none could be fetched.
  echo   Check the internet connection and double-click this file again, or install
  echo   Python 3.11 or newer from https://www.python.org/downloads/
  echo   ^(tick "Add python.exe to PATH" during the installation^).
  goto end
)
set "PY=%OLDPY%"
goto run

:run_portable
"%PORTABLE%" make-arc.py %*
set "CODE=%ERRORLEVEL%"
goto end

:run
%PY% make-arc.py %*
set "CODE=%ERRORLEVEL%"

:end
echo.
pause
exit /b %CODE%

rem :find <minor> <variable>: the first of py -3, python that is 3.<minor> or newer.
:find
for %%c in ("py -3" python) do (
  if not defined %2 (
    %%~c -c "import sys; sys.exit(sys.version_info < (3, %1))" >nul 2>&1 && set "%2=%%~c"
  )
)
exit /b
