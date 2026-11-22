@echo off
rem Make your own Knowledge Arc (Windows): double-click this file.
rem It runs make-arc.py, which asks which drive and which edition.
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 make-arc.py %*
  goto end
)
python --version >nul 2>&1
if %errorlevel%==0 (
  python make-arc.py %*
  goto end
)
echo.
echo   Python 3 is needed to make an arc. Install it from https://www.python.org/downloads/
echo   (tick "Add python.exe to PATH" during the installation), then double-click this file again.
:end
echo.
pause
