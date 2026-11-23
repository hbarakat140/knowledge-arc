@echo off
rem Make your own Knowledge Arc (Windows): double-click this file.
rem It runs make-arc.py, which asks which drive and which edition.
rem Python: this computer's own if it is 3.11 or newer; otherwise a portable
rem Python fetched once by scripts\get-python.ps1 into
rem %LOCALAPPDATA%\knowledge-arc (nothing installed; delete that folder to
rem remove it). Set ARC_PORTABLE_PYTHON=1 to use the portable one anyway.
cd /d "%~dp0"
set "PY="
set "OLDPY="
set "PYVER="
for /f "tokens=2" %%v in ('findstr /b /c:"version " scripts\portable-python.txt') do set "PYVER=%%v"
set "PORTABLE=%LOCALAPPDATA%\knowledge-arc\python-%PYVER%\python.exe"
if exist "%PORTABLE%" goto portable
if defined ARC_PORTABLE_PYTHON goto fetch

rem This computer's Python, if it is new enough (3.11 or newer).
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1 && set "PY=python"
)
if defined PY goto run
rem An older one (3.9, 3.10) is kept as a fallback: it builds without search.
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "OLDPY=py -3"
if not defined OLDPY (
  python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "OLDPY=python"
)

:fetch
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\get-python.ps1"
if exist "%PORTABLE%" goto portable
if defined OLDPY (
  set "PY=%OLDPY%"
  goto run
)
echo.
echo   Python is needed to make an arc, and none could be fetched.
echo   Check the internet connection and double-click this file again, or install
echo   Python 3.11 or newer from https://www.python.org/downloads/
echo   (tick "Add python.exe to PATH" during the installation).
goto end

:portable
"%PORTABLE%" make-arc.py %*
goto end

:run
%PY% make-arc.py %*

:end
echo.
pause
