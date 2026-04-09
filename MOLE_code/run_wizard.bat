@echo off
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"

if exist "%PY%" goto :RUN

echo [MOLE-DAS] venv not found. Running installer...
if exist "%~dp0INSTALL_MOLE_DAS.bat" goto :CALL_INSTALL

echo ERROR: Installer not found next to run_wizard.bat
if "%~1"=="--nopause" exit /b 1
pause
exit /b 1

:CALL_INSTALL
call "%~dp0INSTALL_MOLE_DAS.bat" --nopause

echo.
if exist "%PY%" goto :RUN

echo ERROR: venv still missing after installer.
echo Run INSTALL_MOLE_DAS.bat manually to see full output.
if "%~1"=="--nopause" exit /b 1
pause
exit /b 1

:RUN
"%PY%" "%~dp0mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py"
exit /b %ERRORLEVEL%
