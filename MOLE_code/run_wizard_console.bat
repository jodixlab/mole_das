@echo off
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [MOLE-DAS] venv not found. Running installer...
  if exist "%~dp0INSTALL_MOLE_DAS.bat" call "%~dp0INSTALL_MOLE_DAS.bat"
)

if not exist "%PY%" (
  echo ERROR: venv still missing after installer.
  pause
  exit /b 1
)

echo.
echo ======================================
echo  MOLE-DAS WIZARD (Console)
echo ======================================
echo.

"%PY%" -u "%~dp0mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py"
set "RC=%ERRORLEVEL%"

echo.
echo Exit code: %RC%
echo.
pause
exit /b %RC%
