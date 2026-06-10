@echo off
chcp 65001 >nul
echo ========================================================
echo        NCS Competency Standard Writing System
echo ========================================================
echo.
cd /d "%~dp0"
echo [SYSTEM] Checking for stray port conflicts on port 7870...
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 7870 -ErrorAction SilentlyContinue; if ($conn) { Write-Host '[SYSTEM] Found conflicting process. Terminating...'; $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
echo [SYSTEM] Port conflict check complete.
echo [LLM SERVER] Verifying local LLM API status...
python -c "import socket; host='127.0.0.1'; port=8081; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1.5); s.connect((host, port)); print('[SUCCESS] Detected active LLM API server')" >nul 2>&1
if errorlevel 1 (
    echo ======================================================================
    echo  [WARNING] Local LLM API server at Port 8081 is not running!
    echo ======================================================================
    echo.
) else (
    echo [SUCCESS] Local LLM API server is online and ready.
)
if exist ".venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
) else (
    echo [WARNING] Virtual environment not found.
)
cd ncs_writer
echo [SYSTEM] Starting NCS Writer Server...
python main.py
pause
