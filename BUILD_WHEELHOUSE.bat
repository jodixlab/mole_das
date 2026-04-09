@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM ======================================
REM  MOLE-DAS Wheelhouse Builder (Windows)
REM  Downloads all dependencies into wheelhouse\
REM ======================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo.
echo [MOLE-DAS] Building offline wheelhouse in:
echo   %ROOT%\wheelhouse
echo.

echo [MOLE-DAS] This must be run on Windows with Python 3.12 x64 and internet.
echo.

py -3.12 -V >nul 2>nul
if errorlevel 1 goto :NO_PY312

goto :DO_DOWNLOAD

:NO_PY312
echo ERROR: Python 3.12 not found (py -3.12).
echo Install Python 3.12 x64 and retry.
pause
exit /b 1

:DO_DOWNLOAD
if not exist "%ROOT%\wheelhouse" mkdir "%ROOT%\wheelhouse"

echo.
echo [MOLE-DAS] Downloading core wheels...
py -3.12 -m pip download --only-binary=:all: -r "%ROOT%\requirements.txt" -d "%ROOT%\wheelhouse"

if not exist "%ROOT%\requirements_optional.txt" goto :DONE

echo.
echo [MOLE-DAS] Downloading optional wheels...
py -3.12 -m pip download --only-binary=:all: -r "%ROOT%\requirements_optional.txt" -d "%ROOT%\wheelhouse"

:DONE
echo.
echo [MOLE-DAS] Wheelhouse build complete.
echo.
pause
exit /b 0
