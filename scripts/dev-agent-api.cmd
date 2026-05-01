@echo off
setlocal

set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..") do set ROOT=%%~fI

cd /d "%ROOT%"

echo [MOSS Agent] Repo root: %ROOT%

set MOSS_AGENT_ENABLED=true
set MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1

echo [MOSS Agent] MOSS_AGENT_ENABLED=%MOSS_AGENT_ENABLED%
echo [MOSS Agent] MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=%MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS%

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\dev-api.ps1"

endlocal
