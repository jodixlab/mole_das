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
"%PY%" "mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py" %*
exit /b %ERRORLEVEL%
