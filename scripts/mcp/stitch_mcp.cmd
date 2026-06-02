@echo off
REM CD to repo root from script location then run Stitch MCP launcher.
cd /d "%~dp0..\.."
node "%~dp0stitch_mcp_launcher.mjs"
exit /b %ERRORLEVEL%
