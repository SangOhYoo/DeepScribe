import subprocess
res = subprocess.run(["git", "status"], capture_output=True)
with open("g_status.txt", "w", encoding="utf-8") as f:
    f.write(res.stdout.decode('utf-8', errors='ignore'))
    f.write(res.stderr.decode('utf-8', errors='ignore'))
