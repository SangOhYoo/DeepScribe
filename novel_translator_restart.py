import os
import subprocess
import time

def main():
    app_path = r"d:\DeepScribe\novel_translator\app.py"
    
    try:
        with open(app_path, "rb") as f:
            content_bytes = f.read()
        
        # Clean up null bytes if any, then decode with ignore
        content_bytes = content_bytes.replace(b'\x00', b'')
        content = content_bytes.decode("utf-8", errors="ignore")
        print("Successfully decoded app.py")
        
        start_token = 'gb_register_status = gr.Markdown("", elem_id="gb-register-status")ister_status = gr.Markdown("", elem_id="gb-register-status")'
        
        if start_token in content:
            print("Found duplicate block!")
            idx_start = content.find(start_token)
            
            end_token = 'progress_text = gr.Markdown("", elem_id="progress-status")'
            idx_end = content.find(end_token, idx_start)
            
            if idx_end != -1:
                end_of_line = content.find("\n", idx_end + len(end_token))
                if end_of_line == -1:
                    end_of_line = idx_end + len(end_token)
                
                duplicate_block = content[idx_start:end_of_line]
                content = content.replace(duplicate_block, "")
                print("Successfully removed duplicate block from app.py")
            else:
                print("Could not find the end of the duplicate block.")
        else:
            print("Duplicate block start_token not found.")
            
        with open(app_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Wrote clean app.py")
        
    except Exception as e:
        print(f"Error clean app.py: {e}")
        
    print("Restarting Novel Translator...")
    try:
        out_bytes = subprocess.check_output('netstat -ano', shell=True)
        try:
            out = out_bytes.decode('cp949')
        except Exception:
            out = out_bytes.decode('utf-8', errors='ignore')
        pids = set()
        for line in out.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 5:
                local_addr = parts[1]
                pid = parts[-1]
                if local_addr.endswith(':7862') or '[::]:7862' in local_addr:
                    pids.add(pid)
        for pid in pids:
            print(f"Killing process {pid} on port 7862")
            subprocess.call(f'taskkill /F /PID {pid}', shell=True)
    except Exception as e:
        print(f"Error finding/killing process on port 7862: {e}")
        
    time.sleep(1)
    
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        subprocess.Popen(
            [r"d:\DeepScribe\.venv\Scripts\python.exe", "-m", "novel_translator.app"],
            cwd=r"d:\DeepScribe",
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        print("Started new server successfully")
    except Exception as e:
        print(f"Error starting new server: {e}")

if __name__ == '__main__':
    main()
