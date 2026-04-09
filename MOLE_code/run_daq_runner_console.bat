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
echo ======================================
echo  MOLE-DAS DAQ RUNNER (Console)
echo ======================================
echo.
echo Example:
echo   run_daq_runner_console.bat --config ..\mole_das_data\configs\runner_config.json --ui
echo.

"%PY%" -u "mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py" %*

echo.
pause
exit /b %ERRORLEVEL%
