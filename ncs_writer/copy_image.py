import shutil
import os

src = r"C:\Users\SangO\.gemini\antigravity\brain\27935dfe-e066-4903-8314-dd62fb008d2b\ncs_training_illustration_1781093175739.png"
dst = r"d:\DeepScribe\ncs_writer\ncs_training_illustration.png"

if os.path.exists(src):
    shutil.copy(src, dst)
    print("SUCCESS: Image copied successfully")
else:
    print("ERROR: Source image not found")
