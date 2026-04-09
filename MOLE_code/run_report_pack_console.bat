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
