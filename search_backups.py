import os

repo_root = r"d:\DeepScribe"
for root, dirs, files in os.walk(repo_root):
    # skip .git and .venv
    if ".git" in root or ".venv" in root:
        continue
    for file in files:
        if "ui" in file.lower() or "bak" in file.lower() or "backup" in file.lower() or "temp" in file.lower():
            print(os.path.join(root, file))
