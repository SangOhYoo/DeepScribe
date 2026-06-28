import os
import glob

app_data_dir = r"C:\Users\SangO\.gemini\antigravity"
print("Searching in:", app_data_dir)
for root, dirs, files in os.walk(app_data_dir):
    for file in files:
        if file.endswith(".db") or "abyss" in file.lower() or "backup" in file.lower():
            full_path = os.path.join(root, file)
            print(full_path, os.path.getsize(full_path))
