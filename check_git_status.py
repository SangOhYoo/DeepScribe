import subprocess
import os

with open("git_status_output.txt", "w", encoding="utf-8") as f:
    f.write("=== FILES IN ENGINE ===\n")
    try:
        files = os.listdir("abyss_writer/engine")
        f.write(str(files) + "\n")
    except Exception as e:
        f.write(f"Error listing engine: {e}\n")
        
    f.write("=== RUNNING DIR /A ON ENGINE ===\n")
    res = subprocess.run(["cmd", "/c", "dir", "/a", "abyss_writer\\engine"], capture_output=True, text=True)
    f.write(res.stdout + "\n" + res.stderr + "\n")
    
    f.write("=== GIT SHOW HEAD:abyss_writer/engine ===\n")
    res2 = subprocess.run(["git", "ls-tree", "HEAD", "abyss_writer/engine/"], capture_output=True, text=True)
    f.write(res2.stdout + "\n" + res2.stderr + "\n")

