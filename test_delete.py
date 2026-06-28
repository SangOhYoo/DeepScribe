import subprocess
import time
import os

python_exe = r"d:\DeepScribe\.venv\Scripts\python.exe"
if not os.path.exists(python_exe):
    python_exe = "python"

# 1. 그누보드 단편 테스트 게시글 생성
print("Populating short test posts into database...")
subprocess.run([python_exe, r"d:\DeepScribe\create_short_test_posts.py"], cwd=r"d:\DeepScribe")

# 2. 8081 포트 (mock llama.cpp) 프로세스 종료 후 재시작
print("Restarting Mock llama.cpp server on port 8081...")
kill_8081 = [
    "powershell", "-NoProfile", "-Command",
    "$conn = Get-NetTCPConnection -LocalPort 8081 -ErrorAction SilentlyContinue; if ($conn) { $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
]
subprocess.run(kill_8081, capture_output=True)
time.sleep(0.5)

mock_server_path = r"d:\DeepScribe\tests\mock_server.py"
if os.path.exists(mock_server_path):
    subprocess.Popen(
        [python_exe, mock_server_path, "8081"],
        cwd=r"d:\DeepScribe",
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print("Mock llama.cpp server started.")

# 3. 7862 포트 (Gradio Translator) 프로세스 종료 후 재시작
print("Restarting Gradio Translator server on port 7862...")
kill_7862 = [
    "powershell", "-NoProfile", "-Command",
    "$conn = Get-NetTCPConnection -LocalPort 7862 -ErrorAction SilentlyContinue; if ($conn) { $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
]
subprocess.run(kill_7862, capture_output=True)
time.sleep(1)

bat_path = r"d:\DeepScribe\run_novel_translator.bat"
if os.path.exists(bat_path):
    proc = subprocess.Popen(
        [bat_path],
        cwd=r"d:\DeepScribe",
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print(f"Translator server started in new console. PID: {proc.pid}")
else:
    print(f"Error: {bat_path} does not exist.")

