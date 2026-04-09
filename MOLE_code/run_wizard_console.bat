@echo off
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"

call "%~dp0_resolve_mole_python.bat"
if errorlevel 1 (
  echo ERROR: Python runtime unavailable after bootstrap.
  pause
  exit /b 1
)

set "PY=%MOLE_PY%"

echo.
echo ======================================
echo  MOLE-DAS WIZARD (Console)
echo ======================================
echo.

"%PY%" -u "%~dp0mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py"
set "RC=%ERRORLEVEL%"

echo.
echo Exit code: %RC%
echo.
pause
exit /b %RC%
