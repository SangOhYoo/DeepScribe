@echo off
echo [1/3] Terminating existing processes on port 7862 and 8081...
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 7862 -ErrorAction SilentlyContinue; if ($conn) { $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 8081 -ErrorAction SilentlyContinue; if ($conn) { $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"

timeout /t 1 /nobreak > nul

echo [2/3] Starting Mock llama.cpp server on port 8081...
start "Mock llama.cpp Server" .venv\Scripts\python.exe tests\mock_server.py 8081

timeout /t 1 /nobreak > nul

echo [3/3] Starting Novel Translator Gradio Server on port 7862...
start "Gradio Translator Server" run_novel_translator.bat

echo Clean server startup completed!
echo Please wait a few seconds for the Gradio interface to bind, then test the translation flow.
pause
