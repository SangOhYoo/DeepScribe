@echo off
title DeepScribe Premium Fullstack Launcher
color 0b
echo ======================================================================
echo  DeepScribe Manga-to-Novel Fullstack Launcher
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Clean up stray processes on Frontend (3000) and Backend (8002) ports
echo [SYSTEM] Checking for stray port conflicts...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8002,3000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" >nul 2>&1
echo [SYSTEM] Port conflict check complete.

:: 2. Check Backend Virtual Environment
if exist .venv goto :activate_env

echo [BACKEND] Virtual environment (.venv) not found. Creating...
python -m venv .venv
if errorlevel 1 goto :venv_create_fail

:activate_env
echo [BACKEND] Activating virtual environment and checking dependencies...
call "%~dp0.venv\Scripts\activate.bat"
if errorlevel 1 goto :activation_fail

python -m pip install -r backend\requirements.txt
if errorlevel 1 goto :pip_fail

:: 3. Proactively check if LLM Server from settings.json is running
echo [LLM SERVER] Verifying local LLM API status...
python -c "import json, socket, urllib.parse; f=open('settings.json', 'r', encoding='utf-8') if open('settings.json', 'r') else None; settings=json.load(f) if f else {}; url=settings.get('api_url', 'http://127.0.0.1:8081/v1/chat/completions'); p_url=urllib.parse.urlparse(url); host=p_url.hostname or '127.0.0.1'; port=p_url.port or 8081; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1.5); s.connect((host, port)); print(f'[SUCCESS] Detected active LLM API server on {host}:{port}')" >nul 2>&1
if errorlevel 1 (
    color 0c
    echo ======================================================================
    echo  [WARNING] Local LLM API server is not running or unreachable!
    echo  Please check settings.json and start llama-server / LM Studio / Ollama.
    echo ======================================================================
    color 0b
    echo.
) else (
    echo [SUCCESS] Local LLM API server is online and ready.
)

:: 4. Check Frontend Node Modules
echo [FRONTEND] Checking node_modules...
if exist "frontend\node_modules" goto :run_services

echo [FRONTEND] node_modules not found. Running npm install...
cd frontend
call npm install
if errorlevel 1 goto :npm_fail
cd ..

:run_services
echo ======================================================================
echo  Starting services... Backend and Frontend will open in new windows.
echo ======================================================================
echo.

:: Launch Backend
echo [BACKEND] Starting Uvicorn FastAPI server on Port: 8002...
start "DeepScribe Backend Server" cmd /k "call .venv\Scripts\activate.bat && python backend\run.py"

:: Launch Frontend
echo [FRONTEND] Starting Vite dev server on Port: 3000...
start "DeepScribe Frontend Web" cmd /k "cd frontend && npm run dev"

:: Launch Browser (delay 3 seconds to let servers start)
timeout /t 3 /nobreak > nul
echo [BROWSER] Opening dashboard at http://127.0.0.1:3000
start "" "http://127.0.0.1:3000"

echo ======================================================================
echo  Fullstack launcher completed successfully.
echo ======================================================================
goto :eof

:venv_create_fail
echo [ERROR] Failed to create python virtual environment. Make sure Python is installed and added to PATH.
pause
exit /b 1

:activation_fail
echo [ERROR] Failed to activate virtual environment.
pause
exit /b 1

:pip_fail
echo [ERROR] Failed to install backend dependencies. Check your network or backend/requirements.txt.
pause
exit /b 1

:npm_fail
echo [ERROR] Failed to install frontend dependencies. Make sure Node.js/NPM is installed.
pause
exit /b 1
