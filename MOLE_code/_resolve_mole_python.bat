@echo off
setlocal EnableExtensions DisableDelayedExpansion

cd /d "%~dp0"
set "MOLE_PY=%~dp0.venv\Scripts\python.exe"
set "MOLE_INSTALLER=%~dp0..\INSTALL_MOLE_DAS.bat"

call :VALIDATE
if not errorlevel 1 goto :SUCCESS

echo [MOLE-DAS] Python runtime missing or stale. Running installer...
if exist "%MOLE_INSTALLER%" call "%MOLE_INSTALLER%" --nopause

call :VALIDATE
if not errorlevel 1 goto :SUCCESS

echo [MOLE-DAS] ERROR: Python runtime unavailable after bootstrap.
endlocal & set "MOLE_PY=" & exit /b 1

:SUCCESS
endlocal & set "MOLE_PY=%MOLE_PY%" & exit /b 0

:VALIDATE
if not exist "%MOLE_PY%" exit /b 1
"%MOLE_PY%" -V >nul 2>nul
if errorlevel 1 exit /b 1
exit /b 0
