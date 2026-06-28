import json
import os
import shutil
import sys
import subprocess
from datetime import datetime, timedelta

# Define files to restore
files_to_restore = [
    r"abyss_writer/ui.py",
    r"abyss_writer/main.py",
    r"run_abyss_writer.bat",
    r"ncs_writer/client.py",
    r"ncs_writer/generator.py",
    r"ncs_writer/ui.py",
    r"ncs_writer/main.py",
    r"run_ncs_writer.bat"
]

# Paths to the log files
log_paths = [
    # Session 2 (today)
    r"C:\Users\SangO\.gemini\antigravity\brain\95221eaf-33b6-4474-a4d6-3084be1a2db2\.system_generated\logs\overview.txt"
]

# Create a temp directory for the dry run
temp_dir = r"d:\DeepScribe\dry_run_temp"
if os.path.exists(temp_dir):
    shutil.rmtree(temp_dir)
os.makedirs(temp_dir)

# Reset the actual repo files to clean HEAD first so we can copy them
repo_root = r"d:\DeepScribe"
for rel_path in files_to_restore:
    dest_path = os.path.join(temp_dir, rel_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    src_path = os.path.join(repo_root, rel_path)
    try:
        subprocess.run(["git", "checkout", "HEAD", "--", rel_path], cwd=repo_root, capture_output=True)
        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_path)
            print(f"Copied clean HEAD version of {rel_path} to dry-run temp")
        else:
            print(f"{rel_path} does not exist in HEAD (will be created by write_to_file)")
    except Exception as e:
         print(f"Git checkout failed for {rel_path}: {e}")

# Helper to decode double-serialized values
def decode_val(val):
    if not isinstance(val, str):
        return val
    val = val.strip()
    if val.startswith('"') and val.endswith('"'):
        try:
            return json.loads(val)
        except Exception:
            return val[1:-1].replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\').replace('\\"', '"')
    return val

# Read and parse the logs
events = []
for log_idx, log_path in enumerate(log_paths):
    if not os.path.exists(log_path):
        print(f"Log not found: {log_path}")
        continue
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f):
            try:
                data = json.loads(line)
                if data.get('type') == 'PLANNER_RESPONSE' and 'tool_calls' in data:
                    created_at_utc = data.get('created_at')
                    dt_utc = datetime.strptime(created_at_utc, "%Y-%m-%dT%H:%M:%SZ")
                    dt_kst = dt_utc + timedelta(hours=9)
                    
                    # Check if it's before 20:00 today (June 9)
                    # Note: Yesterday's events (June 8) are always before 20:00 today.
                    if dt_kst < datetime(2026, 6, 9, 20, 0, 0):
                        for tc in data['tool_calls']:
                            func_name = tc.get('name')
                            if func_name in ['replace_file_content', 'write_to_file', 'multi_replace_file_content']:
                                args = tc.get('args', {})
                                target_file = decode_val(args.get('TargetFile', args.get('AbsolutePath', '')))
                                events.append({
                                    "kst": dt_kst,
                                    "tool": func_name,
                                    "args": args,
                                    "file": target_file,
                                    "log_idx": log_idx + 1,
                                    "line_num": line_num + 1
                                })
            except Exception as e:
                pass

# Sort events chronologically
events.sort(key=lambda x: x['kst'])

print(f"\nFound {len(events)} events before 20:00 KST in total.")

# Replay events on the dry-run copies
for ev in events:
    tool = ev['tool']
    args = ev['args']
    log_file = ev['file']
    
    # Extract relative path from D:\DeepScribe\abyss_writer\ui.py
    rel_file = log_file.replace("d:\\DeepScribe\\", "").replace("d:/DeepScribe/", "").replace("\\", "/")
    
    temp_file_path = os.path.normpath(os.path.join(temp_dir, rel_file))
    print(f"[{ev['kst']}] Log {ev['log_idx']} L{ev['line_num']}: Replaying {tool} on {rel_file}")
    
    if tool == 'write_to_file':
        content = decode_val(args.get('CodeContent'))
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  -> Wrote {len(content)} characters successfully.")
        
    elif tool == 'replace_file_content':
        target = decode_val(args.get('TargetContent'))
        replacement = decode_val(args.get('ReplacementContent'))
        
        if not os.path.exists(temp_file_path):
            print(f"  ERROR: File {temp_file_path} does not exist!")
            sys.exit(1)
            
        with open(temp_file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
            
        if target not in file_content:
            print("  ERROR: TargetContent not found in file!")
            print("  TargetContent (first 200 chars):", repr(target[:200]))
            sys.exit(1)
            
        # Perform replacement
        occurrences = file_content.count(target)
        allow_mult = str(args.get('AllowMultiple', 'false')).lower() == 'true'
        if occurrences > 1 and not allow_mult:
            print(f"  ERROR: Multiple occurrences of TargetContent found ({occurrences}) but AllowMultiple is false!")
            sys.exit(1)
            
        file_content = file_content.replace(target, replacement)
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
        print(f"  -> Replaced successfully ({occurrences} occurrence(s)).")
        
    elif tool == 'multi_replace_file_content':
        chunks = args.get('ReplacementChunks', [])
        if isinstance(chunks, str):
            chunks = json.loads(decode_val(chunks))
            
        with open(temp_file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
            
        for chunk in chunks:
            target = decode_val(chunk.get('TargetContent'))
            replacement = decode_val(chunk.get('ReplacementContent'))
            if target not in file_content:
                print("  ERROR in multi-replace: TargetContent not found!")
                sys.exit(1)
            file_content = file_content.replace(target, replacement)
            
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
        print("  -> Multi-replaced successfully.")

print("\nDry run completed successfully! All replacements found and applied.")
