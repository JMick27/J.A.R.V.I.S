@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

%PYTHON% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "JARVIS Desktop Assistant" ^
  --icon "jarvis_icon.ico" ^
  --add-data "jarvis_icon.ico;." ^
  --add-data "distribution_config.json;." ^
  jarvis.py

echo.
echo If the build succeeded, your app is in:
echo dist\JARVIS Desktop Assistant\JARVIS Desktop Assistant.exe
pause
