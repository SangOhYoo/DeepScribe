import json
import os
from datetime import datetime, timedelta

log_path = r"C:\Users\SangO\.gemini\antigravity\brain\95221eaf-33b6-4474-a4d6-3084be1a2db2\.system_generated\logs\overview.txt"
with open(log_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            if data.get('type') == 'PLANNER_RESPONSE' and 'tool_calls' in data:
                created_at_utc = data.get('created_at')
                dt_utc = datetime.strptime(created_at_utc, "%Y-%m-%dT%H:%M:%SZ")
                dt_kst = dt_utc + timedelta(hours=9)
                
                if dt_kst < datetime(2026, 6, 9, 20, 0, 0):
                    for tc in data['tool_calls']:
                        func_name = tc.get('name')
                        if func_name in ['replace_file_content', 'write_to_file', 'multi_replace_file_content']:
                            args = tc.get('args', {})
                            target_file = args.get('TargetFile', args.get('AbsolutePath', ''))
                            if 'ui.py' in target_file:
                                # check if TargetContent or ReplacementContent is truncated
                                target = args.get('TargetContent', '')
                                replacement = args.get('ReplacementContent', '')
                                content = args.get('CodeContent', '')
                                is_t = '<truncated' in str(target) or '<truncated' in str(replacement) or '<truncated' in str(content)
                                print(f"Line {i+1}: KST={dt_kst.strftime('%Y-%m-%d %H:%M:%S')}, tool={func_name}, truncated={is_t}")
                                if is_t:
                                    print(f"  Target length: {len(target)}, Replacement length: {len(replacement)}, Content length: {len(content)}")
                                    print(f"  Instruction: {args.get('Instruction')}")
                                    print(f"  Description: {args.get('Description')}")
        except Exception as e:
            pass
