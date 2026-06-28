import json
import os
from datetime import datetime, timedelta

log_path = r"C:\Users\SangO\.gemini\antigravity\brain\95221eaf-33b6-4474-a4d6-3084be1a2db2\.system_generated\logs\overview.txt"
if os.path.exists(log_path):
    print("Log file found.")
    with open(log_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                if data.get('type') == 'PLANNER_RESPONSE' and 'tool_calls' in data:
                    for tc in data['tool_calls']:
                        func_name = tc.get('name')
                        args = tc.get('args', {})
                        target_file = args.get('TargetFile', args.get('AbsolutePath', ''))
                        if func_name in ['replace_file_content', 'write_to_file', 'multi_replace_file_content']:
                            created_at_utc = data.get('created_at')
                            # convert to KST (+9 hours)
                            dt_utc = datetime.strptime(created_at_utc, "%Y-%m-%dT%H:%M:%SZ")
                            dt_kst = dt_utc + timedelta(hours=9)
                            print(f"KST={dt_kst.strftime('%Y-%m-%d %H:%M:%S')}, file={target_file}, tool={func_name}")
            except Exception as e:
                pass
else:
    print("Log file not found.")
