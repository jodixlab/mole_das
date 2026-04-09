@echo off
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"

call "%~dp0_resolve_mole_python.bat" --nopause
if not errorlevel 1 goto :RUN

echo ERROR: Python runtime unavailable after bootstrap.
if "%~1"=="--nopause" exit /b 1
pause
exit /b 1

:RUN
set "PY=%MOLE_PY%"
"%PY%" "%~dp0mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py"
exit /b %ERRORLEVEL%
