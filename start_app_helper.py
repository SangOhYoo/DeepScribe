import subprocess
import time
import os

python_exe = r"d:\DeepScribe\.venv\Scripts\python.exe"
if not os.path.exists(python_exe):
    python_exe = "python"

# 1. Populate DB posts
print("Running DB populator helper...")
subprocess.run([python_exe, r"d:\DeepScribe\db_populate_helper.py"], cwd=r"d:\DeepScribe")

# 2. Terminate 8081 processes and start mock llama server
print("Restarting Mock llama server on port 8081...")
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
    print("Mock server started on port 8081.")

# 3. Terminate 7862 processes and start main server
print("Restarting translation server on port 7862...")
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
    print(f"Main server started. PID: {proc.pid}")
else:
    print(f"Error: {bat_path} does not exist.")
