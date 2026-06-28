import os
import signal
import sys

# 현재 실행 중인 자기 자신의 프로세스 ID
current_pid = os.getpid()

try:
    import psutil
except ImportError:
    # psutil이 없으면 os.popen 등으로 tasklist를 읽어서 죽임
    import subprocess
    output = subprocess.check_output("tasklist /FI \"IMAGENAME eq python.exe\" /FO CSV", shell=True).decode('cp949', errors='ignore')
    lines = output.strip().split('\n')
    for line in lines[1:]:
        parts = line.split(',')
        if len(parts) > 1:
            pid_str = parts[1].strip('"')
            try:
                pid = int(pid_str)
                if pid != current_pid:
                    os.kill(pid, signal.SIGTERM)
                    print(f"Killed process {pid}")
            except Exception as e:
                pass
    sys.exit(0)

for proc in psutil.process_iter(['pid', 'name']):
    try:
        if proc.info['name'] == 'python.exe' and proc.info['pid'] != current_pid:
            proc.kill()
            print(f"Killed python process: {proc.info['pid']}")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
