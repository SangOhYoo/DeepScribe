import os

for root, dirs, files in os.walk("d:/DeepScribe"):
    if ".venv" in root or ".git" in root:
        continue
    for f in files:
        if f.endswith(".db") or f.endswith(".sqlite") or "backup" in f.lower():
            path = os.path.join(root, f)
            print(f"Found: {path} (Size: {os.path.getsize(path)} bytes)")
