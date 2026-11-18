@echo off
rem Double-click to check that every file on this drive is intact.
title Checking the drive
echo Checking every file on this drive. On a large drive this can take an hour or more.
echo You can keep using the computer while it runs.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify.ps1"
echo.
pause
