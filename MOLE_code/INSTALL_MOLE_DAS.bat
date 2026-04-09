@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM MOLE_code-level installer shim.
REM Preferred: run the root installer (one folder up) so requirements.txt is found.

if exist "%~dp0..\INSTALL_MOLE_DAS.bat" goto :RUN_ROOT

echo ERROR: Installer not found in parent folder.
echo.
echo Fix:
echo   - Do NOT run from a stripped MOLE_code folder by itself.
echo   - Keep the full package layout and run INSTALL_MOLE_DAS.bat from the root.
echo.
if "%~1"=="--nopause" exit /b 1
pause
exit /b 1

:RUN_ROOT
call "%~dp0..\INSTALL_MOLE_DAS.bat" %*
exit /b %ERRORLEVEL%
