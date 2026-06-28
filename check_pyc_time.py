import os
import time

pyc_path = r"d:\DeepScribe\abyss_writer\__pycache__\ui.cpython-313.pyc"
if os.path.exists(pyc_path):
    mtime = os.path.getmtime(pyc_path)
    print("PYC modified time:", time.ctime(mtime))
else:
    print("PYC file not found.")
