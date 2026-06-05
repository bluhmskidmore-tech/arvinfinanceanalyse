@echo off
REM CD to repo root from script location then run launcher (helps when MCP cwd != workspace)
cd /d "%~dp0..\.."
python "%~dp0moss_mcp_launcher.py" metric-contracts
exit /b %ERRORLEVEL%
