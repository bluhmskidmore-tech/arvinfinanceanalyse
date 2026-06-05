@echo off
cd /d "%~dp0..\.."
set "MOSS_GOVERNANCE_PATH=%CD%\data\governance"
python "%~dp0moss_mcp_launcher.py" lineage-evidence
exit /b %ERRORLEVEL%
