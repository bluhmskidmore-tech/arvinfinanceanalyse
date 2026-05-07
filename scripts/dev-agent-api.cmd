@echo off
setlocal

set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..") do set ROOT=%%~fI

cd /d "%ROOT%"

echo [MOSS Agent] Repo root: %ROOT%

set MOSS_AGENT_ENABLED=true
set MOSS_AGENT_PROVIDER=hermes
set MOSS_DEV_API_SCRIPT=dev-agent-api.ps1
set MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1

echo [MOSS Agent] MOSS_AGENT_ENABLED=%MOSS_AGENT_ENABLED%
echo [MOSS Agent] MOSS_AGENT_PROVIDER=%MOSS_AGENT_PROVIDER%
echo [MOSS Agent] MOSS_DEV_API_SCRIPT=%MOSS_DEV_API_SCRIPT%
echo [MOSS Agent] MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=%MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS%

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\dev-api.ps1"

endlocal
