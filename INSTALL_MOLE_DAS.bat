@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM ======================================
REM  MOLE-DAS Runtime Installer (Windows)
REM  - Creates / repairs MOLE_code\.venv
REM  - Installs core deps + optional extras
REM  - Uses wheelhouse\ if present (offline)
REM ======================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "CODE=%ROOT%\MOLE_code"
set "VENV=%CODE%\.venv"
set "PY=%VENV%\Scripts\python.exe"

echo.
echo [MOLE-DAS] Root: %ROOT%
echo [MOLE-DAS] Code: %CODE%
echo.

REM ---- Require Python 3.12 (validated build) ----
py -3.12 -V >nul 2>nul
if errorlevel 1 goto :NO_PY312

goto :CHECK_VENV

:NO_PY312
echo [MOLE-DAS] ERROR: Python 3.12 not found.
echo           Install Python 3.12 (64-bit) and re-run this installer.
goto :FAIL

:CHECK_VENV
REM ---- Create / repair venv if missing or stale ----
if exist "%PY%" (
  call :VALIDATE_PY
  if not errorlevel 1 goto :HAVEVENV
  echo [MOLE-DAS] Existing venv is stale or not runnable. Archiving and rebuilding...
  call :ARCHIVE_STALE_VENV
)

echo [MOLE-DAS] Creating virtual environment...
py -3.12 -m venv "%VENV%"
echo.

:HAVEVENV
call :VALIDATE_PY
if not errorlevel 1 goto :UPGRADE_PIP

echo [MOLE-DAS] ERROR: venv not found after creation attempt.
goto :FAIL

:UPGRADE_PIP
REM ---- Upgrade build tooling ----
"%PY%" -m pip install --upgrade pip setuptools wheel

REM ---- Offline wheelhouse support ----
set "PIP_FINDLINKS="
if not exist "%ROOT%\wheelhouse" goto :INSTALL_CORE

dir /b "%ROOT%\wheelhouse\*.whl" >nul 2>nul
if errorlevel 1 goto :INSTALL_CORE

set "PIP_FINDLINKS=--no-index --find-links \"%ROOT%\wheelhouse\""

:INSTALL_CORE
echo.
echo [MOLE-DAS] Installing core requirements...
"%PY%" -m pip install %PIP_FINDLINKS% -r "%ROOT%\requirements.txt"
if errorlevel 1 goto :FAIL_CORE

goto :INSTALL_OPTIONAL

:FAIL_CORE
echo.
echo [MOLE-DAS] ERROR: core dependency install failed.
goto :FAIL

:INSTALL_OPTIONAL
if not exist "%ROOT%\requirements_optional.txt" goto :DONE

echo.
echo [MOLE-DAS] Installing optional extras (sound + enhanced images)...
echo           (If this fails, MOLE still runs â€” you just lose some cosmetics.)
"%PY%" -m pip install %PIP_FINDLINKS% -r "%ROOT%\requirements_optional.txt"

goto :DONE

:DONE
echo.
echo [MOLE-DAS] INSTALL COMPLETE.
if "%~1"=="--nopause" exit /b 0
pause
exit /b 0

:FAIL
echo.
echo [MOLE-DAS] INSTALL FAILED.
echo.
echo Hints:
echo   - Confirm Python 3.12 x64 is installed:  py -0p
echo   - If you're offline, run BUILD_WHEELHOUSE.bat on an online PC first

echo.
if "%~1"=="--nopause" exit /b 1
pause
exit /b 1

:VALIDATE_PY
if not exist "%PY%" exit /b 1
"%PY%" -V >nul 2>nul
if errorlevel 1 exit /b 1
exit /b 0

:ARCHIVE_STALE_VENV
if not exist "%VENV%" exit /b 0
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"
set "STALE=%CODE%\.venv_stale_auto_%STAMP%_%RANDOM%"
move "%VENV%" "%STALE%" >nul 2>nul
if errorlevel 1 (
  echo [MOLE-DAS] WARNING: could not archive stale venv. Rebuild may require manual cleanup.
)
exit /b 0
