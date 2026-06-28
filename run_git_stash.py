import subprocess

res = subprocess.run(["git", "stash", "list"], capture_output=True)
print("GIT STASH LIST:")
print(res.stdout.decode('utf-8', errors='ignore'))
