import subprocess
import os

try:
    print("Terminating old process 41464...")
    res = subprocess.run(["taskkill", "/F", "/PID", "41464"], capture_output=True, text=True)
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)
except Exception as e:
    print("Error:", e)
