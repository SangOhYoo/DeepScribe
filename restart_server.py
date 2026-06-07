import subprocess, sys

# Kill old server
result = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "$conn = Get-NetTCPConnection -LocalPort 7860 -ErrorAction SilentlyContinue; if ($conn) { $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"],
    capture_output=True, text=True
)
print("Kill result:", result.stdout, result.stderr)

import time
time.sleep(1)

# Start new server
proc = subprocess.Popen(
    [r"D:\DeepScribe\.venv\Scripts\python.exe", r"D:\DeepScribe\abyss_writer\main.py"],
    cwd=r"D:\DeepScribe\abyss_writer"
)
print(f"Started new server PID: {proc.pid}")
