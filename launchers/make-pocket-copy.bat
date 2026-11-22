@echo off
rem Knowledge Arc: make a pocket copy of this library on a stick, a memory card
rem or a phone's storage. On the drive this file is
rem "arc\Make a pocket copy (Windows).bat". Needs no internet and nothing
rem installed: it runs arc\system\make-pocket-copy.ps1 with Windows' own
rem PowerShell. See arc\system\MAINTENANCE.txt.
title Make a pocket copy
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0system\make-pocket-copy.ps1" %*
echo.
pause
