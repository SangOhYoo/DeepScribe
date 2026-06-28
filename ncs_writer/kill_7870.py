import os
import subprocess

def kill_port_7870():
    try:
        # Get connections on 7870
        cmd = "netstat -ano | findstr :7870"
        out = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        pids = set()
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 5:
                # The last item is the PID
                pid = parts[-1]
                pids.add(int(pid))
        
        for pid in pids:
            print(f"Killing PID {pid} on port 7870")
            subprocess.run(f"taskkill /F /PID {pid}", shell=True)
    except Exception as e:
        print(f"No process detected on port 7870 or error occurred: {e}")

if __name__ == "__main__":
    kill_port_7870()
