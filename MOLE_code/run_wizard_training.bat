@echo off
setlocal EnableExtensions DisableDelayedExpansion
set MOLE_ENV=TRAINING
cd /d "%~dp0"
call "%~dp0run_wizard.bat" %*
endlocal
