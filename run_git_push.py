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
    # 1. Add files
    files = [
        "ncs_writer/ui.py",
        "ncs_writer/generator.py",
        "ncs_writer/database.py",
        "run_ncs_writer.bat"
    ]
    if not run_cmd(["git", "add"] + files):
        print("Failed to stage files")
        return
        
    # 2. Commit
    msg = "Optimize NCS Writer: Add Project Management & History Tracking, Refine Multi-Item Hierarchy Prompts"
    if not run_cmd(["git", "commit", "-m", msg]):
        print("Failed to commit changes")
        return
        
    # 3. Push
    if not run_cmd(["git", "push", "origin", "main"]):
        print("Failed to push changes to GitHub")
        return
        
    print("Git push completed successfully!")

if __name__ == "__main__":
    main()
