@echo off
cd /d "%~dp0..\.."
set "MOSS_DUCKDB_PATH=%CD%\data\moss.duckdb"
python "%~dp0moss_mcp_launcher.py" data-catalog
exit /b %ERRORLEVEL%
