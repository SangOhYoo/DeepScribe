import subprocess

def run_cmd(args):
    print(f"Running: {' '.join(args)}")
    res = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    print("STDOUT:")
    print(res.stdout)
    print("STDERR:")
    print(res.stderr)
    return res.returncode == 0

def main():
    # 1. git status
    run_cmd(["git", "status"])
    
    # 2. Add modified files
    # We modified: novel_translator/app.py
    if not run_cmd(["git", "add", "novel_translator/app.py"]):
        print("Failed to stage novel_translator/app.py")
        return
        
    # 3. Commit
    msg = "Fix Gnuboard Integration UI: Remove corrupted inline SortableJS code and implement CDN SortableJS loading"
    if not run_cmd(["git", "commit", "-m", msg]):
        print("Failed to commit changes (possibly nothing to commit)")
        
    # 4. Push
    if not run_cmd(["git", "push", "origin", "main"]):
        print("Failed to push changes to GitHub")
        return
        
    print("Git push completed successfully!")

if __name__ == "__main__":
    main()
