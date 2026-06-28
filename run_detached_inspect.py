import subprocess
import time
import os

python_exe = r"d:\DeepScribe\.venv\Scripts\python.exe"
if not os.path.exists(python_exe):
    python_exe = "python"

proc = subprocess.Popen(
    [python_exe, r"d:\DeepScribe\inspect_db_posts.py"],
    cwd=r"d:\DeepScribe",
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print(f"Spawned inspect process with PID {proc.pid}")
time.sleep(2)
