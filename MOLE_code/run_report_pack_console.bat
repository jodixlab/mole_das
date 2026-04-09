@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

call "%~dp0_resolve_mole_python.bat"
if not errorlevel 1 goto RUN

echo ERROR: Python runtime unavailable after bootstrap.
pause
exit /b 1

:RUN
set "PY=%MOLE_PY%"
echo.
echo ==========================================
echo  MOLE DAS - Report Pack v1 (Console)
echo ==========================================
echo.
echo Provide the full path to a session folder (contains runner_config.json).
echo Example:
echo   D:\MOLE_DAS\mole_das_data\sessions\2026-02-02\RUN_2026_02_02_0929
echo.
set /p SESSION_DIR=Session folder path: 

if "%SESSION_DIR%"=="" (
  echo.
  echo No session folder provided.
  pause
  exit /b 1
)

echo.
echo Running report pack...
"%PY%" "%~dp0mole_report_pack_v1.py" --session-dir "%SESSION_DIR%"

echo.
pause
exit /b %ERRORLEVEL%
