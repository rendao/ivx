@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set VENV_PY=%PROJECT_ROOT%\.venv\Scripts\python.exe

cd /d "%PROJECT_ROOT%"
if exist "%VENV_PY%" (
	"%VENV_PY%" scripts\workflow.py %*
) else (
	python scripts\workflow.py %*
)
exit /b %errorlevel%
