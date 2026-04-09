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
echo.
echo ==============================================
echo  MOLE DAQ RUNNER - SIM MODE (UI)
echo ==============================================
echo.
echo Generating a unique outdir under mole_das_data\sessions...
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "DAY=%%i"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"
set "OUTDIR=..\mole_das_data\sessions\%DAY%\SIM_%STAMP%"

echo.
echo Using config: ..\mole_das_data\configs\sim_session_template.json
echo Outdir: %OUTDIR%
echo.

"%PY%" -u mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py ^
  --config ..\mole_das_data\configs\sim_session_template.json ^
  --outdir %OUTDIR% ^
  --ui --run --auto-start ^
  --driver SIM --sim-seed 1234 --sim-profile ENGINE_TRANSIENT %*
