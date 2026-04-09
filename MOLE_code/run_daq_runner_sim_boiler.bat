@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"

if exist "%PY%" goto RUN

echo [MOLE-DAS] venv not found. Running installer...
if exist "%~dp0INSTALL_MOLE_DAS.bat" call "%~dp0INSTALL_MOLE_DAS.bat" --nopause

if exist "%PY%" goto RUN

echo ERROR: venv missing after installer.
echo Run INSTALL_MOLE_DAS.bat manually to see full output.
pause
exit /b 1

:RUN
echo.
echo ==============================================
echo  MOLE DAQ RUNNER - SIM MODE (BOILER_STEADY)
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
echo SIM profiles:
echo   ENGINE_TRANSIENT ^(default^) 
echo   BOILER_STEADY
echo   FLARE_SPIKY
echo   CAL_CYCLE
echo.
echo Optional SIM faults:
echo   --sim-dropout-every 20   ^(every 20th sample comm fails^)
echo   --sim-stuck-after 60     ^(freeze after 60 samples^)
echo   --sim-drift-per-k 0.05   ^(add drift per sample^)
echo.

"%PY%" -u mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py ^
  --config ..\mole_das_data\configs\sim_session_template.json ^
  --outdir %OUTDIR% ^
  --run --auto-start ^
  --driver SIM --sim-seed 1234 --sim-profile BOILER_STEADY %*

pause
