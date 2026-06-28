import os
import glob

print("Searching for .db files:")
for f in glob.glob("**/*.db", recursive=True):
    print(f, os.path.getsize(f) if os.path.exists(f) else 0)
