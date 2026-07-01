@echo off
setlocal
cd /d "%~dp0"

set "ATLAS_EXE=%~dp0dist\JARVIS Desktop Assistant\JARVIS Desktop Assistant.exe"

if exist "%ATLAS_EXE%" (
    start "" "%ATLAS_EXE%"
    exit /b 0
)

echo Packaged ATLAS executable was not found. Falling back to Python source.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" jarvis.py
) else (
    python jarvis.py
)

if errorlevel 1 (
    echo.
    echo ATLAS closed with an error. The console will stay open so you can read it.
    pause
)
