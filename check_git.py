import subprocess

res = subprocess.run(["git", "status"], capture_output=True)
print("GIT STATUS:")
print(res.stdout.decode('utf-8', errors='ignore'))

res_diff = subprocess.run(["git", "diff"], capture_output=True)
with open("git_diff.txt", "w", encoding="utf-8") as f:
    f.write(res_diff.stdout.decode('utf-8', errors='ignore'))
print("GIT DIFF WRITTEN TO git_diff.txt")
