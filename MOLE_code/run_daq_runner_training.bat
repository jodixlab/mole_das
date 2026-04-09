@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

call "%~dp0_resolve_mole_python.bat" --nopause
if not errorlevel 1 goto RUN

echo ERROR: Python runtime unavailable after bootstrap.
pause
exit /b 1

:RUN
set "PY=%MOLE_PY%"
set MOLE_ENV=TRAINING
"%PY%" -u "mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py" --ui --driver SIM_TRAINING %*
exit /b %ERRORLEVEL%
