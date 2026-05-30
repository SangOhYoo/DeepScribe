@echo off
echo ======================================================
echo  DeepScribe Web UI Launcher
echo ======================================================

cd /d "%~dp0"

if exist .venv goto :activate_env

echo Virtual environment not found. Creating...
python -m venv .venv
if errorlevel 1 goto :venv_create_fail

:activate_env
echo Checking and installing dependencies...
call "%~dp0.venv\Scripts\activate.bat"
if errorlevel 1 goto :activation_fail

python -m pip install -r requirements.txt
if errorlevel 1 goto :pip_fail

echo Opening web browser at http://127.0.0.1:5000
start "" "http://127.0.0.1:5000"

echo Starting DeepScribe UI server...
python -m deepscribe.ui
goto :eof

:venv_create_fail
echo Failed to create virtual environment. Ensure Python is installed and added to PATH.
pause
exit /b 1

:activation_fail
echo Failed to activate virtual environment.
pause
exit /b 1

:pip_fail
echo Failed to install dependencies. Check your internet connection.
pause
exit /b 1
