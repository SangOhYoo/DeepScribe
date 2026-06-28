import os
import time

brain_dir = r"C:\Users\SangO\.gemini\antigravity\brain"
for folder in os.listdir(brain_dir):
    path = os.path.join(brain_dir, folder)
    if os.path.isdir(path):
        print(f"Folder: {folder}, Modified: {time.ctime(os.path.getmtime(path))}")
