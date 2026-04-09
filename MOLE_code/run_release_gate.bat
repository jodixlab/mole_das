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
