@echo off
REM ═══════════════════════════════════════════════════════════════════
REM  Novel Translator - Launch Script
REM  Starts the Gradio-based novel translation web UI
REM ═══════════════════════════════════════════════════════════════════

cd /d D:\DeepScribe

echo.
echo  ╔═══════════════════════════════════════╗
echo  ║   Novel Translator - DeepScribe       ║
echo  ║   Local LLM Novel Translation UI      ║
echo  ╚═══════════════════════════════════════╝
echo.

REM Activate the shared virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
) else (
    echo [WARN] No .venv found, using system Python.
)

REM Install additional dependencies if needed
pip install chardet aiomysql -q 2>nul

echo.
echo [INFO] Starting Novel Translator on http://127.0.0.1:7862
echo [INFO] Press Ctrl+C to stop.
echo.

python -m novel_translator.app

pause
