@echo off
setlocal
set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "& '%ROOT%MOLE_code\.venv\Scripts\python.exe' '%ROOT%scripts\release_go_no_go_gate.py' --artifact-dir '%ROOT%RELEASES\clean_release_workflow' %*"
exit /b %ERRORLEVEL%
