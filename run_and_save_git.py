import subprocess

def run_cmd(args):
    try:
        res = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        return res.stdout + "\n" + res.stderr
    except Exception as e:
        return f"Error running {' '.join(args)}: {e}"

with open("git_debug_output.txt", "w", encoding="utf-8") as f:
    f.write("=== GIT SHOW FILES IN HEAD ===\n")
    f.write(run_cmd(["git", "ls-tree", "-r", "HEAD", "--name-only"]))
    
    f.write("\n=== GIT LOG FOR context_router.py ===\n")
    f.write(run_cmd(["git", "log", "--all", "--", "abyss_writer/engine/context_router.py"]))
    
    f.write("\n=== GIT SHOW ALL BRANCHES ===\n")
    f.write(run_cmd(["git", "branch", "-a"]))
    
    f.write("\n=== GIT STATUS ===\n")
    f.write(run_cmd(["git", "status"]))
