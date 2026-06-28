import subprocess

with open("git_info_output.txt", "w", encoding="utf-8") as f:
    f.write("=== GIT STATUS ===\n")
    res = subprocess.run(["git", "status"], capture_output=True, text=True)
    f.write(res.stdout + "\n" + res.stderr + "\n")
    
    f.write("\n=== GIT LOG ===\n")
    res2 = subprocess.run(["git", "log", "-n", "30", "--oneline", "--date=local", "--pretty=format:%h - %ad : %s"], capture_output=True, text=True)
    f.write(res2.stdout + "\n" + res2.stderr + "\n")
    
    f.write("\n=== GIT DIFF ===\n")
    res3 = subprocess.run(["git", "diff"], capture_output=True, text=True)
    f.write(res3.stdout + "\n" + res3.stderr + "\n")
