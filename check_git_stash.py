import subprocess
res = subprocess.run(["git", "stash", "list"], capture_output=True, text=True)
print("Stash list:")
print(res.stdout)
