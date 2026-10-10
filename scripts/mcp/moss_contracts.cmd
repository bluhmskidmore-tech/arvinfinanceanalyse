@echo off
REM CD to repo root from script location then run launcher (helps when MCP cwd != workspace)
cd /d "%~dp0..\.."
REM Prefer the repo venv (docs/MCP_RUNBOOK.md); a bare `python` is often an unrelated venv without duckdb.
set "MOSS_MCP_PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%MOSS_MCP_PYTHON%" set "MOSS_MCP_PYTHON=python"
"%MOSS_MCP_PYTHON%" "%~dp0moss_mcp_launcher.py" metric-contracts
exit /b %ERRORLEVEL%
