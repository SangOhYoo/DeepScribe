import os
import subprocess
import sys

def restore_files():
    print("[SYSTEM] Searching git history to find the version with the correct UI layout...")
    try:
        # Get all commit hashes in history
        res = subprocess.run(["git", "log", "--all", "--format=%H"], capture_output=True, check=True)
        commits = res.stdout.decode('utf-8', errors='ignore').strip().split('\n')
        
        # Targets to search for (any of these matching is a strong indicator)
        targets = ["인간의 은밀한 욕망", "심층 소설 집필 및 다중 시점", "프로젝트 기본 정보"]
        
        # Encode targets in UTF-8, CP949, EUC-KR
        target_bytes = []
        for t in targets:
            target_bytes.append((t, t.encode('utf-8')))
            target_bytes.append((t, t.encode('cp949', errors='ignore')))
            target_bytes.append((t, t.encode('euc-kr', errors='ignore')))
            
        found_commit = None
        for commit in commits:
            commit = commit.strip()
            if not commit:
                continue
            
            # Check if ui.py in either path contains target bytes
            for path in ["abyss_writer/ui.py", "ui.py"]:
                res_show = subprocess.run(["git", "show", f"{commit}:{path}"], capture_output=True)
                content = res_show.stdout
                if not content:
                    continue
                
                for name, tb in target_bytes:
                    if tb and tb in content:
                        print(f"[SYSTEM] Found matching commit: {commit} (matched '{name}' in {path})")
                        found_commit = commit
                        break
                if found_commit:
                    break
            if found_commit:
                break
                
        if found_commit:
            print(f"[SYSTEM] Restoring repository to target commit: {found_commit}")
            subprocess.run(["git", "checkout", "-f", found_commit], check=True)
        else:
            print("[SYSTEM] Target layout not found in history. Reverting to stable bb50c700...")
            subprocess.run(["git", "checkout", "-f", "bb50c700"], check=True)
            
    except Exception as e:
        print(f"[SYSTEM] Error during repository restoration: {e}")
        print("[SYSTEM] Falling back to default files...")

def kill_port_owner(port=7860):
    print(f"[SYSTEM] Checking for port conflicts on {port}...")
    try:
        # Get netstat output for the specified port
        output = subprocess.check_output("netstat -ano", shell=True).decode('utf-8', errors='ignore')
        killed = False
        for line in output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    # Don't kill our own process
                    if int(pid) != os.getpid():
                        print(f"[SYSTEM] Killing process on port {port} (PID: {pid})...")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        killed = True
        if not killed:
            print(f"[SYSTEM] No conflicting process found on port {port}.")
    except Exception as e:
        print(f"[SYSTEM] Port check failed: {e}")

def main():
    # 1. Restore the stable June 9th 20:00 version of abyss_writer files (Disabled to preserve manual layout and database model restorations)
    # restore_files()

    # 1.5. Run merge_and_patch.py (Disabled to protect manually updated layout changes)
    # print("[SYSTEM] Running merge_and_patch.py to synchronize and patch ui.py...")
    # try:
    #     with open("d:/DeepScribe/merge_and_patch.py", "r", encoding="utf-8", errors="ignore") as f:
    #         exec(f.read(), globals())
    #     print("[SYSTEM] merge_and_patch.py executed successfully.")
    # except Exception as e:
    #     print(f"[SYSTEM] Error executing merge_and_patch.py: {e}")

    # 2. Prevent port conflicts
    kill_port_owner(7860)

    # 3. Choose python executable (virtual env preferred)
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    python_exe = venv_python if os.path.exists(venv_python) else "python"

    # 4. Start the application with PYTHONPATH set to resolve local modules
    print(f"[SYSTEM] Starting Abyss Writer using {python_exe}...")
    try:
        env = os.environ.copy()
        abyss_writer_dir = os.path.abspath("abyss_writer")
        ncs_writer_dir = os.path.abspath("ncs_writer")
        env["PYTHONPATH"] = abyss_writer_dir + os.pathsep + ncs_writer_dir + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.run([python_exe, os.path.join("abyss_writer", "ui.py")], env=env)
    except KeyboardInterrupt:
        print("\n[SYSTEM] Abyss Writer stopped.")
    except Exception as e:
        print(f"[SYSTEM] Failed to run Abyss Writer: {e}")

if __name__ == "__main__":
    main()
