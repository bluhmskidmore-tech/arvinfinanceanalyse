@echo off
rem Use the shared, maintenance-aware native launcher.
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev-up.ps1"
exit /b %errorlevel%
