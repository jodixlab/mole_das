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
echo ===============================
echo   MOLE-DAS RELEASE GATE
echo ===============================
echo.

"%PY%" "mole_release_gate.py" --strict-hash
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo RELEASE GATE: PASS
) else if "%RC%"=="2" (
  echo RELEASE GATE: PASS WITH WARNINGS
) else (
  echo RELEASE GATE: FAIL (code %RC%)
)

echo.
pause
exit /b %RC%
